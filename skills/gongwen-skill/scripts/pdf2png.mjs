#!/usr/bin/env node
// Render PDF pages to PNG for visual layout checks.
//
// Two engines:
//   builtin - the vendored PDFium WebAssembly build (works on any OS, no native binary)
//   poppler - the system `pdftoppm` command
// `--engine auto` prefers builtin and falls back to poppler.

import fs from "node:fs";
import path from "node:path";
import zlib from "node:zlib";
import { execFileSync } from "node:child_process";
import { fileURLToPath, pathToFileURL } from "node:url";
import { crc32 } from "./zip.mjs";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const VENDOR = path.join(HERE, "..", "vendor", "pdfium");

function usage() {
  console.log(`Usage:
  node pdf2png.mjs --input file.pdf [--prefix out/name] [--outdir dir] [--dpi 110] [--engine auto|builtin|poppler]

Notes:
  - Writes <prefix>-1.png, <prefix>-2.png ... one file per page.
  - builtin engine uses the bundled PDFium WebAssembly build; no poppler, no LibreOffice.
  - poppler engine uses pdftoppm from poppler-utils when it is installed.
  - --engine auto (default) uses builtin when vendor/pdfium exists, otherwise poppler.`);
}

function parseArgs(argv) {
  const args = {};
  for (let i = 2; i < argv.length; i += 1) {
    const key = argv[i];
    if (!key.startsWith("--")) continue;
    const name = key.slice(2);
    if (name === "help") { args.help = true; continue; }
    const value = argv[i + 1];
    if (value === undefined || value.startsWith("--")) throw new Error(`--${name} requires a value`);
    args[name] = value;
    i += 1;
  }
  return args;
}

function pngChunk(type, data) {
  const length = Buffer.alloc(4);
  length.writeUInt32BE(data.length, 0);
  const body = Buffer.concat([Buffer.from(type, "ascii"), data]);
  const crc = Buffer.alloc(4);
  crc.writeUInt32BE(crc32(body), 0);
  return Buffer.concat([length, body, crc]);
}

function encodePng(width, height, rgba) {
  const stride = width * 4;
  const raw = Buffer.alloc((stride + 1) * height);
  for (let y = 0; y < height; y += 1) {
    raw[y * (stride + 1)] = 0; // filter type: none
    raw.set(rgba.subarray(y * stride, (y + 1) * stride), y * (stride + 1) + 1);
  }
  const ihdr = Buffer.alloc(13);
  ihdr.writeUInt32BE(width, 0);
  ihdr.writeUInt32BE(height, 4);
  ihdr[8] = 8; // bit depth
  ihdr[9] = 6; // colour type: RGBA
  return Buffer.concat([
    Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]),
    pngChunk("IHDR", ihdr),
    pngChunk("IDAT", zlib.deflateSync(raw, { level: 6 })),
    pngChunk("IEND", Buffer.alloc(0)),
  ]);
}

function builtinAvailable() {
  return fs.existsSync(path.join(VENDOR, "index.esm.js")) && fs.existsSync(path.join(VENDOR, "pdfium.wasm"));
}

async function renderBuiltin(input, prefix, dpi) {
  if (!builtinAvailable()) throw new Error(`builtin engine unavailable: ${VENDOR}`);
  const { PDFiumLibrary } = await import(pathToFileURL(path.join(VENDOR, "index.esm.js")).href);
  const library = await PDFiumLibrary.init();
  const document = await library.loadDocument(new Uint8Array(fs.readFileSync(input)));
  const written = [];
  try {
    let index = 0;
    for (const page of document.pages()) {
      index += 1;
      // "BGRA" is accepted by PDFium v2 and v3; both return RGBA byte order.
      const { data, width, height } = await page.render({ scale: dpi / 72, colorSpace: "BGRA" });
      const output = `${prefix}-${index}.png`;
      fs.writeFileSync(output, encodePng(width, height, data));
      written.push(output);
      if (typeof page.close === "function") page.close();
    }
  } finally {
    if (typeof document.destroy === "function") document.destroy();
    if (typeof library.destroy === "function") library.destroy();
  }
  return written;
}

function renderPoppler(input, prefix, dpi) {
  try {
    execFileSync("pdftoppm", ["-png", "-r", String(dpi), input, prefix], { stdio: ["ignore", "ignore", "pipe"] });
  } catch (error) {
    if (error.code === "ENOENT") throw new Error("pdftoppm not found (install poppler-utils)");
    const detail = String(error.stderr ?? "").trim();
    throw new Error(`pdftoppm failed (exit ${error.status ?? "?"})${detail ? `: ${detail}` : ""}`);
  }
  const dir = path.dirname(prefix);
  const base = path.basename(prefix);
  return fs
    .readdirSync(dir)
    .filter((name) => name.startsWith(`${base}-`) && name.endsWith(".png"))
    .sort()
    .map((name) => path.join(dir, name));
}

const args = parseArgs(process.argv);
if (args.help || !args.input) {
  usage();
  process.exit(args.help ? 0 : 1);
}
if (!fs.existsSync(args.input)) {
  console.error(`PDF2PNG ERROR: input not found: ${args.input}`);
  process.exit(2);
}
const engine = args.engine ?? "auto";
if (!["auto", "builtin", "poppler"].includes(engine)) {
  console.error("PDF2PNG ERROR: --engine must be auto, builtin or poppler");
  process.exit(2);
}
const dpi = Number(args.dpi ?? 110);
if (!Number.isFinite(dpi) || dpi <= 0) {
  console.error("PDF2PNG ERROR: --dpi must be a positive number");
  process.exit(2);
}
const outdir = path.resolve(args.outdir ?? path.dirname(args.input));
const prefix = path.resolve(args.prefix ?? path.join(outdir, path.basename(args.input, path.extname(args.input))));
fs.mkdirSync(path.dirname(prefix), { recursive: true });

const started = performance.now();
let files = [];
try {
  if (engine === "builtin" || (engine === "auto" && builtinAvailable())) {
    files = await renderBuiltin(args.input, prefix, dpi);
  } else if (engine === "poppler") {
    files = renderPoppler(args.input, prefix, dpi);
  } else {
    files = renderPoppler(args.input, prefix, dpi);
  }
} catch (error) {
  if (engine === "auto") {
    try {
      files = renderPoppler(args.input, prefix, dpi);
    } catch (fallback) {
      console.error(`PDF2PNG ERROR: no usable engine. builtin=${builtinAvailable() ? "failed" : "absent"}; poppler=${fallback.message}`);
      console.error("  Install poppler-utils, or restore vendor/pdfium (see vendor/pdfium/README.md).");
      process.exit(1);
    }
  } else {
    console.error(`PDF2PNG ERROR: ${error.message}`);
    process.exit(1);
  }
}
if (!files.length) {
  console.error("PDF2PNG ERROR: no pages rendered");
  process.exit(1);
}
for (const file of files) console.log(`${file}  ${(fs.statSync(file).size / 1024).toFixed(0)} KB`);
console.log(`Rendered ${files.length} page(s) at ${dpi} dpi in ${((performance.now() - started) / 1000).toFixed(2)}s (engine: ${engine === "auto" ? (builtinAvailable() ? "builtin" : "poppler") : engine})`);
