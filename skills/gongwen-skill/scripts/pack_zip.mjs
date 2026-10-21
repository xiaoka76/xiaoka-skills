#!/usr/bin/env node
// Package a directory into a ZIP with the bundled pure-Node writer.
// Used by install.sh so packaging needs no external zip binary.
//
// Usage: node pack_zip.mjs <src-dir> <out.zip> [--require <entry> ...]
// After writing, the archive is read back and verified; every --require entry
// must be present, so a partial package fails loudly instead of shipping.

import fs from "node:fs";
import { writeZipFromDir, openZip } from "./zip.mjs";

const argv = process.argv.slice(2);
const positional = [];
const required = [];
for (let i = 0; i < argv.length; i += 1) {
  if (argv[i] === "--require") {
    const entry = argv[i + 1];
    if (!entry) {
      console.error("pack_zip: --require needs an entry name");
      process.exit(2);
    }
    required.push(entry);
    i += 1;
  } else if (argv[i].startsWith("--")) {
    console.error(`pack_zip: unknown option ${argv[i]}`);
    process.exit(2);
  } else {
    positional.push(argv[i]);
  }
}
const [src, output] = positional;
if (!src || !output) {
  console.error("Usage: node pack_zip.mjs <src-dir> <out.zip> [--require <entry> ...]");
  process.exit(2);
}

writeZipFromDir(src, output);
const pkg = openZip(output);
pkg.verify();
const missing = required.filter((entry) => !pkg.names.includes(entry));
if (missing.length) {
  // Never leave a package that looks importable but lacks required entries.
  fs.rmSync(output, { force: true });
  console.error(`pack_zip: archive is missing required entries: ${missing.join(", ")}`);
  process.exit(1);
}
console.log(`packed ${pkg.names.length} entries -> ${output}`);
