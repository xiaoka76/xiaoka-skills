// Minimal ZIP reader/writer built on node:zlib only.
// The skill must work on machines without the `zip`/`unzip` binaries
// (Windows has neither in PATH by default), so the DOCX package is
// assembled and inspected here instead of by shelling out.
//
// Scope: ZIP32 only. DOCX packages are a handful of small XML parts, so
// ZIP64, encryption, multi-disk and data descriptors are deliberately absent.

import fs from "node:fs";
import path from "node:path";
import zlib from "node:zlib";

const MAX_ENTRIES = 0xffff;
const MAX_UINT32 = 0xffffffff;

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

// DOS timestamps are normally local time. SOURCE_DATE_EPOCH switches to UTC so
// the same input produces byte-identical archives (reproducible builds).
function dosTimestamp() {
  const epoch = process.env.SOURCE_DATE_EPOCH;
  let fields;
  if (epoch !== undefined && epoch !== "") {
    const seconds = Number(epoch);
    if (!Number.isFinite(seconds) || seconds < 0) throw new Error("SOURCE_DATE_EPOCH must be a non-negative number");
    // DOS time cannot represent anything before 1980; clamp instead of wrapping
    // the 7-bit year field into 2098.
    const date = new Date(Math.max(seconds, 315532800) * 1000); // 1980-01-01T00:00:00Z
    fields = [date.getUTCFullYear(), date.getUTCMonth() + 1, date.getUTCDate(), date.getUTCHours(), date.getUTCMinutes(), date.getUTCSeconds()];
  } else {
    const date = new Date();
    fields = [date.getFullYear(), date.getMonth() + 1, date.getDate(), date.getHours(), date.getMinutes(), date.getSeconds()];
  }
  const [year, month, day, hours, minutes, seconds] = fields;
  const time = ((hours & 0x1f) << 11) | ((minutes & 0x3f) << 5) | (Math.floor(seconds / 2) & 0x1f);
  const date = (((year - 1980) & 0x7f) << 9) | ((month & 0x0f) << 5) | (day & 0x1f);
  return { time, date };
}

function walkFiles(dir, base = dir, out = []) {
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) walkFiles(full, base, out);
    else out.push(path.relative(base, full).split(path.sep).join("/"));
  }
  return out;
}

function localHeader({ method, time, date, crc, compSize, plainSize, nameBuf }) {
  const header = Buffer.alloc(30);
  header.writeUInt32LE(0x04034b50, 0);
  header.writeUInt16LE(20, 4); // version needed to extract
  header.writeUInt16LE(0x0800, 6); // general purpose flag: UTF-8 names
  header.writeUInt16LE(method, 8);
  header.writeUInt16LE(time, 10);
  header.writeUInt16LE(date, 12);
  header.writeUInt32LE(crc, 14);
  header.writeUInt32LE(compSize, 18);
  header.writeUInt32LE(plainSize, 22);
  header.writeUInt16LE(nameBuf.length, 26);
  header.writeUInt16LE(0, 28); // extra field length
  return header;
}

function centralHeader({ method, time, date, crc, compSize, plainSize, nameBuf, offset }) {
  const header = Buffer.alloc(46);
  header.writeUInt32LE(0x02014b50, 0);
  header.writeUInt16LE(20, 4); // version made by
  header.writeUInt16LE(20, 6); // version needed
  header.writeUInt16LE(0x0800, 8); // UTF-8 names
  header.writeUInt16LE(method, 10);
  header.writeUInt16LE(time, 12);
  header.writeUInt16LE(date, 14);
  header.writeUInt32LE(crc, 16);
  header.writeUInt32LE(compSize, 20);
  header.writeUInt32LE(plainSize, 24);
  header.writeUInt16LE(nameBuf.length, 28);
  header.writeUInt16LE(0, 30); // extra field length
  header.writeUInt16LE(0, 32); // comment length
  header.writeUInt16LE(0, 34); // disk number start
  header.writeUInt16LE(0, 36); // internal attributes
  header.writeUInt32LE(0, 38); // external attributes
  header.writeUInt32LE(offset, 42); // relative offset of local header
  return header;
}

// Writes every file under srcDir into a deflate-compressed ZIP archive.
// [Content_Types].xml is placed first, matching what OPC consumers expect.
// Entries are streamed one at a time so peak memory stays at one part.
export function writeZipFromDir(srcDir, output) {
  const { time, date } = dosTimestamp();
  const names = walkFiles(srcDir).sort((a, b) => {
    if (a.startsWith("[") !== b.startsWith("[")) return a.startsWith("[") ? -1 : 1;
    return a < b ? -1 : a > b ? 1 : 0;
  });
  // 0xffff is reserved as the ZIP64 sentinel in the EOCD entry count, so a
  // ZIP32 archive can hold at most 65534 entries.
  if (names.length > MAX_ENTRIES - 1) throw new Error(`ZIP32 limit: ${names.length} entries (max ${MAX_ENTRIES - 1})`);
  if (new Set(names).size !== names.length) throw new Error("duplicate entry names in source directory");

  const fd = fs.openSync(output, "w");
  const records = [];
  let offset = 0;
  try {
    for (const name of names) {
      const nameBuf = Buffer.from(name, "utf8");
      if (nameBuf.length > MAX_ENTRIES) throw new Error(`ZIP32 limit: entry name too long (${name})`);
      const data = fs.readFileSync(path.join(srcDir, name));
      if (data.length > MAX_UINT32) throw new Error(`ZIP32 limit: ${name} exceeds 4 GiB`);
      const crc = crc32(data);
      const deflated = zlib.deflateRawSync(data, { level: 9 });
      const useDeflate = deflated.length < data.length;
      const body = useDeflate ? deflated : data;
      const record = { method: useDeflate ? 8 : 0, time, date, crc, compSize: body.length, plainSize: data.length, nameBuf, offset };
      const header = localHeader(record);
      if (offset + header.length + nameBuf.length + body.length > MAX_UINT32) throw new Error("ZIP32 limit: archive exceeds 4 GiB");
      fs.writeSync(fd, header);
      fs.writeSync(fd, nameBuf);
      fs.writeSync(fd, body);
      records.push(record);
      offset += header.length + nameBuf.length + body.length;
    }

    const centralStart = offset;
    let centralSize = 0;
    for (const record of records) {
      const header = centralHeader(record);
      fs.writeSync(fd, header);
      fs.writeSync(fd, record.nameBuf);
      centralSize += header.length + record.nameBuf.length;
    }
    if (centralStart + centralSize > MAX_UINT32) throw new Error("ZIP32 limit: central directory exceeds 4 GiB");

    const eocd = Buffer.alloc(22);
    eocd.writeUInt32LE(0x06054b50, 0);
    eocd.writeUInt16LE(0, 4); // disk number
    eocd.writeUInt16LE(0, 6); // disk with central directory
    eocd.writeUInt16LE(records.length, 8);
    eocd.writeUInt16LE(records.length, 10);
    eocd.writeUInt32LE(centralSize, 12);
    eocd.writeUInt32LE(centralStart, 16);
    eocd.writeUInt16LE(0, 20); // comment length
    fs.writeSync(fd, eocd);
  } catch (error) {
    // Streaming writes are not atomic: never leave a truncated archive behind.
    // Only unlink a regular file, so an odd output path (e.g. /dev/full) is not
    // destroyed while cleaning up.
    fs.closeSync(fd);
    try {
      if (fs.statSync(output).isFile()) fs.rmSync(output, { force: true });
    } catch {
      // best effort: the original error is the useful one
    }
    throw error;
  }
  fs.closeSync(fd);
}

function findEndOfCentralDirectory(buf) {
  if (buf.length < 22) throw new Error("not a ZIP archive: file is smaller than an end-of-central-directory record");
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
  const cdSize = buf.readUInt32LE(eocd + 12);
  const cdOffset = buf.readUInt32LE(eocd + 16);
  if (cdOffset + cdSize > buf.length) throw new Error("corrupt archive: central directory lies outside the file");
  if (count === 0xffff) throw new Error("ZIP64 archives are not supported");

  const entries = new Map();
  let ptr = cdOffset;
  for (let i = 0; i < count; i += 1) {
    if (ptr + 46 > buf.length) throw new Error("corrupt central directory: truncated record");
    if (buf.readUInt32LE(ptr) !== 0x02014b50) throw new Error("corrupt central directory: bad record signature");
    const flags = buf.readUInt16LE(ptr + 8);
    const method = buf.readUInt16LE(ptr + 10);
    const crc = buf.readUInt32LE(ptr + 16);
    const compSize = buf.readUInt32LE(ptr + 20);
    const plainSize = buf.readUInt32LE(ptr + 24);
    const nameLen = buf.readUInt16LE(ptr + 28);
    const extraLen = buf.readUInt16LE(ptr + 30);
    const commentLen = buf.readUInt16LE(ptr + 32);
    const localOffset = buf.readUInt32LE(ptr + 42);
    if (ptr + 46 + nameLen > buf.length) throw new Error("corrupt central directory: truncated name");
    const name = buf.subarray(ptr + 46, ptr + 46 + nameLen).toString("utf8");
    entries.set(name, { flags, method, crc, compSize, plainSize, localOffset });
    ptr += 46 + nameLen + extraLen + commentLen;
  }

  // Validates the local header against the central directory, then returns the
  // decompressed bytes. Every reader path goes through here.
  function decode(name, entry) {
    const { localOffset } = entry;
    if (localOffset + 30 > buf.length) throw new Error(`corrupt local header: ${name}`);
    if (buf.readUInt32LE(localOffset) !== 0x04034b50) throw new Error(`corrupt local header: ${name}`);
    const localNameLen = buf.readUInt16LE(localOffset + 26);
    const localExtraLen = buf.readUInt16LE(localOffset + 28);
    const start = localOffset + 30 + localNameLen + localExtraLen;
    if (start + entry.compSize > buf.length) throw new Error(`truncated data: ${name}`);
    const localName = buf.subarray(localOffset + 30, localOffset + 30 + localNameLen).toString("utf8");
    if (localName !== name) throw new Error(`name mismatch between local header and central directory: ${name}`);
    if ((entry.flags & 0x08) === 0) {
      if (buf.readUInt16LE(localOffset + 8) !== entry.method) throw new Error(`compression method mismatch: ${name}`);
      if (buf.readUInt32LE(localOffset + 18) !== entry.compSize) throw new Error(`compressed size mismatch: ${name}`);
      if (buf.readUInt32LE(localOffset + 22) !== entry.plainSize) throw new Error(`uncompressed size mismatch: ${name}`);
    }
    if (entry.method !== 0 && entry.method !== 8) throw new Error(`unsupported compression method ${entry.method}: ${name}`);
    const raw = buf.subarray(start, start + entry.compSize);
    const data = entry.method === 0 ? raw : zlib.inflateRawSync(raw);
    if (data.length !== entry.plainSize) throw new Error(`size mismatch: ${name}`);
    if (crc32(data) !== entry.crc) throw new Error(`CRC mismatch: ${name}`);
    return data;
  }

  return {
    names: [...entries.keys()],
    read(name, optional = false) {
      const entry = entries.get(name);
      if (!entry) {
        if (optional) return "";
        throw new Error(`missing part: ${name}`);
      }
      return decode(name, entry).toString("utf8");
    },
    // Integrity check covering what `unzip -t` reports for a DOCX: readable
    // central directory, matching local headers, per-part size and CRC.
    verify() {
      for (const [name, entry] of entries) decode(name, entry);
      return entries.size;
    },
  };
}
