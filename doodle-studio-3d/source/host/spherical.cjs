// Tag an equirectangular MP4 as 360 video (Spherical Video V1: a uuid box of XML in the video
// track), so YouTube, VLC and VR players open it as a sphere. Chunk offsets are shifted when the
// movie header sits before the media data. Returns { tagged } or { already }.
const fs = require('fs');

const UUID = Buffer.from('ffcc8263f8554a938814587a02521fdd', 'hex');
const XML = '<?xml version="1.0"?><rdf:SphericalVideo xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#" xmlns:GSpherical="http://ns.google.com/videos/1.0/spherical/">'
  + '<GSpherical:Spherical>true</GSpherical:Spherical><GSpherical:Stitched>true</GSpherical:Stitched>'
  + '<GSpherical:StitchingSoftware>Doodle Studio 3D</GSpherical:StitchingSoftware><GSpherical:ProjectionType>equirectangular</GSpherical:ProjectionType></rdf:SphericalVideo>';
const CONTAINERS = new Set(['moov', 'trak', 'mdia', 'minf', 'stbl', 'edts', 'dinf']);

function boxes(b, start, end) {
  const out = [];
  for (let p = start; p + 8 <= end;) {
    let size = b.readUInt32BE(p), hdr = 8;
    const type = b.toString('latin1', p + 4, p + 8);
    if (size === 1) { size = Number(b.readBigUInt64BE(p + 8)); hdr = 16; } else if (size === 0) size = end - p;
    if (size < hdr || p + size > end) break;
    out.push({ type, start: p, size, hdr });
    p += size;
  }
  return out;
}
const find = (b, box, type) => boxes(b, box.start + box.hdr, box.start + box.size).find(x => x.type === type);
function walk(b, box, fn) {
  for (const c of boxes(b, box.start + box.hdr, box.start + box.size)) { fn(c); if (CONTAINERS.has(c.type)) walk(b, c, fn); }
}
function grow(b, box, n) {
  if (box.hdr === 16) b.writeBigUInt64BE(BigInt(box.size + n), box.start + 8); else b.writeUInt32BE(box.size + n, box.start);
}

function tag360(file) {
  const b = fs.readFileSync(file), top = boxes(b, 0, b.length);
  const moov = top.find(x => x.type === 'moov'), mdat = top.find(x => x.type === 'mdat');
  if (!moov) throw Error('Not an MP4 movie: no moov box');
  let already = false;
  walk(b, moov, c => { if (c.type === 'uuid' && b.subarray(c.start + 8, c.start + 24).equals(UUID)) already = true; });
  if (already) return { already: true };
  const trak = boxes(b, moov.start + moov.hdr, moov.start + moov.size).filter(x => x.type === 'trak').find(t => {
    const hd = find(b, find(b, t, 'mdia') || t, 'hdlr');
    return hd && b.toString('latin1', hd.start + hd.hdr + 8, hd.start + hd.hdr + 12) === 'vide';
  });
  if (!trak) throw Error('No video track');
  const xml = Buffer.from(XML, 'utf8'), box = Buffer.alloc(24 + xml.length);
  box.writeUInt32BE(box.length, 0); box.write('uuid', 4, 'latin1'); UUID.copy(box, 8); xml.copy(box, 24);
  const n = box.length;
  // media data after the header moves by n: every chunk offset follows it
  if (mdat && moov.start < mdat.start) walk(b, moov, c => {
    const at = c.start + c.hdr + 4, count = c.type === 'stco' || c.type === 'co64' ? b.readUInt32BE(at) : 0;
    for (let i = 0; i < count; i++) {
      if (c.type === 'stco') b.writeUInt32BE(b.readUInt32BE(at + 4 + i * 4) + n, at + 4 + i * 4);
      else b.writeBigUInt64BE(b.readBigUInt64BE(at + 4 + i * 8) + BigInt(n), at + 4 + i * 8);
    }
  });
  grow(b, trak, n); grow(b, moov, n);
  const end = trak.start + trak.size;
  const tmp = file + '.360tmp';
  fs.writeFileSync(tmp, Buffer.concat([b.subarray(0, end), box, b.subarray(end)]));
  fs.renameSync(tmp, file);
  return { tagged: true, bytes: n };
}

module.exports = { tag360 };
