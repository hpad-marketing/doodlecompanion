// Scene audio (voice or music): imported once for the whole scene, played in sync with
// the timeline, drawn as a waveform under the shot, rendered into the scene video, and
// able to drive any control (music drives a bounce, the voice drives the ears...).

let ctxA = null, buf = null, bufPath = null, src = null, env = null, envKey = '';
const ac = () => (ctxA ||= new AudioContext());

export async function loadAudio(api, path) {
  if (!path) { buf = null; bufPath = null; return null; }
  if (bufPath === path && buf) return buf;
  const { data } = await api('read-audio', { path });
  const bytes = Uint8Array.from(atob(data), c => c.charCodeAt(0));
  buf = await ac().decodeAudioData(bytes.buffer);
  bufPath = path;
  env = null;
  return buf;
}
export const audioInfo = () => (buf ? { path: bufPath, seconds: +buf.duration.toFixed(2) } : null);

// loudness per video frame, 0..1 (RMS, normalised to the loudest frame)
export function envelope(fps) {
  if (!buf) return null;
  const key = bufPath + '|' + fps;
  if (env && envKey === key) return env;
  const ch = buf.getChannelData(0), per = buf.sampleRate / fps, n = Math.ceil(buf.duration * fps);
  const out = new Float32Array(n);
  let max = 1e-6;
  for (let f = 0; f < n; f++) {
    let s = 0;
    const a = Math.floor(f * per), b = Math.min(ch.length, Math.floor((f + 1) * per));
    for (let i = a; i < b; i++) s += ch[i] * ch[i];
    out[f] = Math.sqrt(s / Math.max(1, b - a));
    max = Math.max(max, out[f]);
  }
  for (let f = 0; f < n; f++) out[f] /= max;
  env = out; envKey = key;
  return env;
}

export function play(atSeconds) {
  stop();
  if (!buf || atSeconds >= buf.duration) return;
  src = ac().createBufferSource();
  src.buffer = buf;
  src.connect(ac().destination);
  src.start(0, Math.max(0, atSeconds));
}
// the scene audio as a live track, for the playblast recorder
export function streamFrom(atSeconds) {
  if (!buf) return null;
  ac().resume?.();
  const dest = ac().createMediaStreamDestination(), s = ac().createBufferSource();
  s.buffer = buf; s.connect(dest); s.start(0, Math.max(0, atSeconds));
  return { track: dest.stream.getAudioTracks()[0], stop: () => { try { s.stop(); } catch {} } };
}
// part of the scene audio (or a processed copy) as a 16-bit WAV, base64, for Shorts and voices
export function wavBase64(from = 0, to = buf ? buf.duration : 0, source = buf) {
  if (!source) return null;
  const sr = source.sampleRate, ch = Math.min(2, source.numberOfChannels), a = Math.max(0, Math.floor(from * sr)), b = Math.min(source.length, Math.ceil(to * sr)), n = Math.max(0, b - a);
  const d = new DataView(new ArrayBuffer(44 + n * ch * 2)), w = (o, t) => [...t].forEach((c, i) => d.setUint8(o + i, c.charCodeAt(0)));
  w(0, 'RIFF'); d.setUint32(4, 36 + n * ch * 2, true); w(8, 'WAVEfmt '); d.setUint32(16, 16, true); d.setUint16(20, 1, true); d.setUint16(22, ch, true);
  d.setUint32(24, sr, true); d.setUint32(28, sr * ch * 2, true); d.setUint16(32, ch * 2, true); d.setUint16(34, 16, true); w(36, 'data'); d.setUint32(40, n * ch * 2, true);
  const data = [...Array(ch)].map((_, c) => source.getChannelData(c));
  for (let i = 0; i < n; i++) for (let c = 0; c < ch; c++) d.setInt16(44 + (i * ch + c) * 2, Math.max(-1, Math.min(1, data[c][a + i])) * 32767, true);
  const bytes = new Uint8Array(d.buffer);
  let s = '';
  for (let i = 0; i < bytes.length; i += 0x8000) s += String.fromCharCode(...bytes.subarray(i, i + 0x8000));
  return btoa(s);
}
export function stop() { try { src?.stop(); } catch {} src = null; }

// waveform strip for one shot of the scene (scene frames from..from+length)
export function waveform(fps, from, length, ppf) {
  const e = envelope(fps);
  if (!e) return null;
  const c = document.createElement('canvas');
  c.width = Math.max(1, Math.round(length * ppf)); c.height = 22;
  c.className = 'wave';
  const g = c.getContext('2d');
  g.fillStyle = getComputedStyle(document.body).getPropertyValue('--fg') || '#1F1F1D';
  for (let f = 0; f < length; f++) {
    const v = e[from + f] || 0, hh = Math.max(1, v * 20);
    g.fillRect(f * ppf, 11 - hh / 2, Math.max(1, ppf - 1), hh);
  }
  return c;
}

// keys a control from the loudness: quiet = min, loud = max; every `step` frames, smoothed
export function audioDrive(project, from, id, min, max, { step = 2, smooth = 2, gate = 0.08 } = {}, setKey) {
  const e = envelope(project.fps);
  if (!e) throw Error('Import audio for the scene first (File › Import audio…)');
  let n = 0;
  for (let f = 0; f < project.length; f += step) {
    let s = 0, c = 0;
    for (let k = -smooth; k <= smooth; k++) { const v = e[from + f + k]; if (v != null) { s += v; c++; } }
    const v = c ? s / c : 0, t = v < gate ? 0 : (v - gate) / (1 - gate);
    setKey(project, id, f, +(min + (max - min) * t).toFixed(2), 'linear');
    n++;
  }
  return n;
}
