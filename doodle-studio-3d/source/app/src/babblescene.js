// Babble lines in a scene: typed dialogue that the characters "speak" as cute gibberish.
// scene.babble = [{ id, shot (uid), f (frame in the shot), text, who ('lead', co-star index or 'voice:<character>'), mood }]
// scene.voices = { bunny: { style, pitch, speed, range, breath, croak }, ... } (the user's dials)
// Rebuilding renders every line into one voice track (mixed over the recorded voice, if any),
// keys the speaker's mouth from the syllables it made and writes timed captions.
import { speak, voiceFor, captionChunks, wav, VISEME } from './babble.js';

export const linesOf = scene => (scene.babble ||= []);
export const dialsOf = (scene, char) => ((scene.voices ||= {})[char] ||= {});
let nextId = () => 'b' + Date.now().toString(36) + Math.floor(Math.random() * 1e4).toString(36);

// the character a line's speaker is ('lead' = the scene's character)
export function speakerChar(scene, shot, who, leadChar) {
  if (who == null || who === 'lead') return leadChar;
  if (String(who).startsWith('voice:')) return String(who).slice(6);   // off screen: heard, no mouth to move
  const c = (shot.costars || [])[Number(who)];
  if (!c) throw Error(`No co-star ${who} in shot ${shot.code}`);
  return c.character || 'bunny';
}
export function render(scene, line, leadChar, sr = 48000) {
  const shot = scene.shots.find(s => s.uid === line.shot);
  const char = speakerChar(scene, shot, line.who, leadChar), d = dialsOf(scene, char);
  return { char, r: speak(line.text, voiceFor(char, d, line.mood), { sr, style: line.style || d.style }) };
}
export function addLine(scene, shot, f, text, { who = 'lead', mood = 'neutral', style } = {}) {
  text = String(text || '').trim();
  if (!text) throw Error('Type the line first');
  if (!/[A-Za-z0-9À-ɏ]/.test(text)) throw Error('The line needs at least one letter or number');
  const line = { id: nextId(), shot: shot.uid, f: Math.max(0, Math.min(shot.length - 1, Math.round(f))), text, who, mood };
  if (style) line.style = style;
  linesOf(scene).push(line);
  return line;
}
export function removeLine(scene, id) {
  const l = linesOf(scene), i = l.findIndex(x => x.id === id);
  if (i < 0) throw Error('No babble line ' + id);
  return l.splice(i, 1)[0];
}

// mouth keys for one line on its speaker's track (lead or co-star), replacing only the keys
// inside the line's span so a recorded-voice lip sync elsewhere in the shot stays
export function keyMouth(shot, line, vis, setKey) {
  const tracks = line.who == null || line.who === 'lead' ? shot.tracks : ((shot.costars || [])[Number(line.who)] || {}).tracks;
  if (!tracks) return 0;
  const p = { tracks, length: shot.length, fps: shot.fps, stepped: shot.stepped };
  const a = line.f, b = Math.min(shot.length, line.f + vis.length);
  tracks.mouth = (tracks.mouth || []).filter(k => k.f < a || k.f > b);
  let n = 0, last = -1;
  for (let f = a; f < b; f++) { const m = vis[f - a]; if (m !== last) { setKey(p, 'mouth', f, m, 'hold'); last = m; n++; } }
  if (b < shot.length) { setKey(p, 'mouth', b, VISEME.rest, 'hold'); n++; }
  return n;
}

// the whole rebuild; ctx: { leadChar, fps, setKey, base (Float32Array[] channels or null), sr }
export function build(scene, ctx) {
  const { fps, setKey, leadChar } = ctx, sr = ctx.sr || 48000;
  const starts = {}; let n = 0;
  for (const s of scene.shots) { starts[s.uid] = n; n += s.length; }
  // lines whose shot was deleted go too
  scene.babble = linesOf(scene).filter(l => starts[l.shot] != null);
  const rendered = scene.babble.map(l => ({ l, ...render(scene, l, leadChar, sr) }));
  const sceneSec = n / fps, baseLen = ctx.base ? ctx.base[0].length : 0;
  const end = Math.max(Math.ceil(sceneSec * sr), baseLen, ...rendered.map(({ l, r }) => Math.ceil(((starts[l.shot] + l.f) / fps) * sr) + r.samples.length));
  const ch = ctx.base ? ctx.base.length : 1, out = [...Array(ch)].map(() => new Float32Array(end));
  if (ctx.base) ctx.base.forEach((c, i) => out[i].set(c));
  const gain = ctx.base ? 0.8 : 1, report = [];
  let keys = 0;
  // captions made by babble are tagged, so a rebuild replaces only its own
  const caps = scene.captions;
  // (in place: ctx.captionTrack is one of these arrays)
  if (caps) for (const t of Object.values(caps.tracks)) for (let i = t.length - 1; i >= 0; i--) if (t[i].babble) t.splice(i, 1);
  for (const { l, r, char } of rendered) {
    const shot = scene.shots.find(s => s.uid === l.shot), at = Math.round(((starts[l.shot] + l.f) / fps) * sr);
    for (let c = 0; c < ch; c++) { const o = out[c]; for (let i = 0; i < r.samples.length && at + i < end; i++) o[at + i] += r.samples[i] * gain; }
    const vis = r.visemes(fps);
    keys += keyMouth(shot, l, vis, setKey);
    if (ctx.captions !== false) {
      const t = ctx.captionTrack;
      if (t) for (const c of captionChunks(r.words)) {
        const f = l.f + Math.floor(c.t0 * fps), to = Math.min(shot.length, l.f + Math.ceil(c.t1 * fps) + Math.round(fps * 0.25));
        if (f < shot.length) t.push({ shot: shot.uid, f, to: Math.max(f + 1, to), text: c.text, babble: l.id });
      }
    }
    report.push({ id: l.id, shot: shot.code, frame: l.f, char, seconds: +r.seconds.toFixed(2), frames: vis.length, pastShotEnd: l.f + vis.length > shot.length });
  }
  // stop any clip: soft limit only where the sum goes over
  for (const o of out) for (let i = 0; i < o.length; i++) { const x = o[i]; if (x > 0.95 || x < -0.95) o[i] = Math.sign(x) * (0.95 + 0.05 * Math.tanh((Math.abs(x) - 0.95) / 0.05)); }
  return { channels: out, sr, lines: report, keys };
}

// interleaved 16-bit WAV of several channels, base64
export function wavChannelsBase64(channels, sr) {
  const ch = channels.length, n = channels[0].length;
  const d = new DataView(new ArrayBuffer(44 + n * ch * 2)), w = (o, t) => [...t].forEach((c, i) => d.setUint8(o + i, c.charCodeAt(0)));
  w(0, 'RIFF'); d.setUint32(4, 36 + n * ch * 2, true); w(8, 'WAVEfmt '); d.setUint32(16, 16, true); d.setUint16(20, 1, true); d.setUint16(22, ch, true);
  d.setUint32(24, sr, true); d.setUint32(28, sr * ch * 2, true); d.setUint16(32, ch * 2, true); d.setUint16(34, 16, true); w(36, 'data'); d.setUint32(40, n * ch * 2, true);
  for (let i = 0; i < n; i++) for (let c = 0; c < ch; c++) d.setInt16(44 + (i * ch + c) * 2, Math.max(-1, Math.min(1, channels[c][i])) * 32767, true);
  const bytes = new Uint8Array(d.buffer);
  let s = '';
  for (let i = 0; i < bytes.length; i += 0x8000) s += String.fromCharCode(...bytes.subarray(i, i + 0x8000));
  return btoa(s);
}
export { wav };
