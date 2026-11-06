// The palette file readers, on small files made here: .ase, .aco, .gpl, .pal, .hex, .json.
// Run: node tools/test_palettes.mjs
import { parsePalette, parseText, fromColours } from '../app/src/palettes.js';
const ok = (c, m) => { if (!c) { console.log('FAIL', m); process.exitCode = 1; } else console.log('ok  ', m); };
const text = s => new TextEncoder().encode(s).buffer;
const same = (a, b) => JSON.stringify(a) === JSON.stringify(b);

function ase(cols) {
  const parts = [];
  const u16 = v => [v >> 8, v & 255], u32 = v => [(v >>> 24) & 255, (v >>> 16) & 255, (v >>> 8) & 255, v & 255];
  const f32 = v => { const d = new DataView(new ArrayBuffer(4)); d.setFloat32(0, v); return [...new Uint8Array(d.buffer)]; };
  for (const [model, vals] of cols) {
    const name = [...u16(2), 0, 65, 0, 0], body = [...name, ...[...model.padEnd(4)].map(c => c.charCodeAt(0)), ...vals.flatMap(f32), 0, 0];
    parts.push(...u16(1), ...u32(body.length), ...body);
  }
  return new Uint8Array([...'ASEF'].map(c => c.charCodeAt(0)).concat(u16(1), u16(0), u32(cols.length), parts)).buffer;
}
ok(same(parsePalette('a.ase', ase([['RGB', [1, 0, 0]], ['CMYK', [0, 0, 0, 1]], ['Gray', [1]]])), ['#FF0000', '#000000', '#FFFFFF']), '.ase RGB, CMYK and grey');

const aco = new DataView(new ArrayBuffer(4 + 10 * 2));
aco.setUint16(0, 1); aco.setUint16(2, 2);
aco.setUint16(4, 0); aco.setUint16(6, 65535); aco.setUint16(8, 0); aco.setUint16(10, 0);
aco.setUint16(14, 0); aco.setUint16(16, 0); aco.setUint16(18, 0); aco.setUint16(20, 65535);
ok(same(parsePalette('b.aco', aco.buffer), ['#FF0000', '#0000FF']), '.aco RGB');

ok(same(parsePalette('c.gpl', text('GIMP Palette\nName: x\nColumns: 4\n#\n255 0 0 Red\n  0 255 0\tGreen\n')), ['#FF0000', '#00FF00']), '.gpl');
ok(same(parsePalette('d.pal', text('JASC-PAL\n0100\n2\n255 0 0\n0 0 255\n')), ['#FF0000', '#0000FF']), '.pal');
ok(same(parsePalette('e.hex', text('ff0000\n00FF00\n')), ['#FF0000', '#00FF00']), '.hex');
ok(same(parsePalette('f.json', text('{"colors":["#112233","#abc"]}')), ['#112233', '#AABBCC']), '.json');
ok(same(parseText('use #1B998B, #E84855 and 0xFFFD82 here'), ['#1B998B', '#E84855', '#FFFD82']), 'pasted hex in a sentence');
const p = fromColours('Mine', ['#111111', '#EEEEEE', '#FF0000', '#00AA88', '#336699']);
ok(p.floor === '#111111' && p.ceiling === '#EEEEEE' && p.accent === '#FF0000' && p.pieces.length >= 2, 'a colour list becomes a whole palette');
ok(fromColours('Two', ['#111111', '#EEEEEE']).pieces.length === 2, 'two colours are still a palette');
