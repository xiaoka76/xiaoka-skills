// Minimal ZIP reader/writer built on node:zlib only.
// The skill must work on machines without the `zip`/`unzip` binaries
// (Windows has neither in PATH by default), so the DOCX package is
// assembled and inspected here instead of by shelling out.

import fs from "node:fs";
import path from "node:path";
import zlib from "node:zlib";

const CRC_TABLE = (() => {
  const table = new Int32Array(256);
  for (let i = 0; i < 256; i += 1) {
    let c = i;
    for (let k = 0; k < 8; k += 1) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
    table[i] = c;
  }
  return table;
})();

export function crc32(buf) {
  let c = -1;
  for (let i = 0; i < buf.length; i += 1) c = CRC_TABLE[(c ^ buf[i]) & 0xff] ^ (c >>> 8);
  return (c ^ -1) >>> 0;
}

function dosDateTime(date = new Date()) {
  const time = ((date.getHours() & 0x1f) << 11) | ((date.getMinutes() & 0x3f) << 5) | ((date.getSeconds() / 2) & 0x1f);
  const day = (((date.getFullYear() - 1980) & 0x7f) << 9) | (((date.getMonth() + 1) & 0x0f) << 5) | (date.getDate() & 0x1f);
  return { time, day };
}

function walkFiles(dir, base = dir, out = []) {
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) walkFiles(full, base, out);
    else out.push(path.relative(base, full).split(path.sep).join("/"));
  }
  return out;
}

// Writes every file under srcDir into a deflate-compressed ZIP archive.
// [Content_Types].xml is placed first, matching what OPC consumers expect.
export function writeZipFromDir(srcDir, output) {
  const { time, day } = dosDateTime();
  const names = walkFiles(srcDir).sort((a, b) => {
    if (a.startsWith("[") !== b.startsWith("[")) return a.startsWith("[") ? -1 : 1;
    return a < b ? -1 : a > b ? 1 : 0;
  });
  const localParts = [];
  const centralParts = [];
  let offset = 0;
  for (const name of names) {
    const data = fs.readFileSync(path.join(srcDir, name));
    const crc = crc32(data);
    const deflated = zlib.deflateRawSync(data, { level: 9 });
    const useDeflate = deflated.length < data.length;
    const body = useDeflate ? deflated : data;
    const method = useDeflate ? 8 : 0;
    const nameBuf = Buffer.from(name, "utf8");

    const local = Buffer.alloc(30);
    local.writeUInt32LE(0x04034b50, 0);
    local.writeUInt16LE(20, 4); // version needed
    local.writeUInt16LE(0x0800, 6); // UTF-8 names
    local.writeUInt16LE(method, 8);
    local.writeUInt16LE(time, 10);
    local.writeUInt16LE(day, 12);
    local.writeUInt32LE(crc, 14);
    local.writeUInt32LE(body.length, 18);
    local.writeUInt32LE(data.length, 22);
    local.writeUInt16LE(nameBuf.length, 26);
    local.writeUInt16LE(0, 28);
    localParts.push(local, nameBuf, body);

    const central = Buffer.alloc(46);
    central.writeUInt32LE(0x02014b50, 0);
    central.writeUInt16LE(20, 4); // version made by
    central.writeUInt16LE(20, 6); // version needed
    central.writeUInt16LE(0x0800, 8); // UTF-8 names
    central.writeUInt16LE(method, 10);
    central.writeUInt16LE(time, 12);
    central.writeUInt16LE(day, 14);
    central.writeUInt32LE(crc, 16);
    central.writeUInt32LE(body.length, 20);
    central.writeUInt32LE(data.length, 24);
    central.writeUInt16LE(nameBuf.length, 28);
    central.writeUInt16LE(0, 30); // extra
    central.writeUInt16LE(0, 32); // comment
    central.writeUInt16LE(0, 34); // disk start
    central.writeUInt16LE(0, 36); // internal attrs
    central.writeUInt32LE(0, 38); // external attrs
    central.writeUInt32LE(offset, 42);
    centralParts.push(central, nameBuf);

    offset += local.length + nameBuf.length + body.length;
  }
  const centralBuf = Buffer.concat(centralParts);
  const eocd = Buffer.alloc(22);
  eocd.writeUInt32LE(0x06054b50, 0);
  eocd.writeUInt16LE(0, 4);
  eocd.writeUInt16LE(0, 6);
  eocd.writeUInt16LE(names.length, 8);
  eocd.writeUInt16LE(names.length, 10);
  eocd.writeUInt32LE(centralBuf.length, 12);
  eocd.writeUInt32LE(offset, 16);
  eocd.writeUInt16LE(0, 20);
  fs.writeFileSync(output, Buffer.concat([...localParts, centralBuf, eocd]));
}

function findEndOfCentralDirectory(buf) {
  const min = Math.max(0, buf.length - 22 - 0xffff);
  for (let i = buf.length - 22; i >= min; i -= 1) {
    if (buf.readUInt32LE(i) === 0x06054b50) return i;
  }
  throw new Error("not a ZIP archive: end of central directory not found");
}

// Reads a DOCX package once and exposes its parts by name.
export function openZip(file) {
  const buf = fs.readFileSync(file);
  const eocd = findEndOfCentralDirectory(buf);
  const count = buf.readUInt16LE(eocd + 10);
  const entries = new Map();
  let ptr = buf.readUInt32LE(eocd + 16);
  for (let i = 0; i < count; i += 1) {
    if (buf.readUInt32LE(ptr) !== 0x02014b50) throw new Error("corrupt central directory");
    const method = buf.readUInt16LE(ptr + 10);
    const crc = buf.readUInt32LE(ptr + 16);
    const compSize = buf.readUInt32LE(ptr + 20);
    const plainSize = buf.readUInt32LE(ptr + 24);
    const nameLen = buf.readUInt16LE(ptr + 28);
    const extraLen = buf.readUInt16LE(ptr + 30);
    const commentLen = buf.readUInt16LE(ptr + 32);
    const localOffset = buf.readUInt32LE(ptr + 42);
    const name = buf.subarray(ptr + 46, ptr + 46 + nameLen).toString("utf8");
    entries.set(name, { method, crc, compSize, plainSize, localOffset });
    ptr += 46 + nameLen + extraLen + commentLen;
  }

  function body(entry, name) {
    if (buf.readUInt32LE(entry.localOffset) !== 0x04034b50) throw new Error(`corrupt local header: ${name}`);
    const start = entry.localOffset + 30 + buf.readUInt16LE(entry.localOffset + 26) + buf.readUInt16LE(entry.localOffset + 28);
    return buf.subarray(start, start + entry.compSize);
  }

  return {
    names: [...entries.keys()],
    read(name, optional = false) {
      const entry = entries.get(name);
      if (!entry) {
        if (optional) return "";
        throw new Error(`missing part: ${name}`);
      }
      const raw = body(entry, name);
      const data = entry.method === 0 ? raw : zlib.inflateRawSync(raw);
      if (data.length !== entry.plainSize || crc32(data) !== entry.crc) throw new Error(`corrupt part: ${name}`);
      return data.toString("utf8");
    },
    // Equivalent of `unzip -t`: every entry's size and CRC must match.
    verify() {
      for (const [name, entry] of entries) {
        const raw = body(entry, name);
        const data = entry.method === 0 ? raw : zlib.inflateRawSync(raw);
        if (data.length !== entry.plainSize) throw new Error(`size mismatch: ${name}`);
        if (crc32(data) !== entry.crc) throw new Error(`CRC mismatch: ${name}`);
      }
      return entries.size;
    },
  };
}
