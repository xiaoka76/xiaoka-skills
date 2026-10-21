#!/usr/bin/env node
// Package a directory into a ZIP with the bundled pure-Node writer.
// Used by install.sh so packaging needs no external zip binary.
import { writeZipFromDir } from "./zip.mjs";

const [src, output] = process.argv.slice(2);
if (!src || !output) {
  console.error("Usage: node pack_zip.mjs <src-dir> <out.zip>");
  process.exit(2);
}
writeZipFromDir(src, output);
