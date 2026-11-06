// Transcriber: the scene voice to timed words, then to timed captions. Whisper runs in a worker
// (transcribe-worker.js). captionsFrom makes short lines that follow the caption rules.
export const LANGUAGES = [['auto', 'Detect'], ['english', 'English'], ['hindi', 'Hindi']];
const MAX_WORDS = 6, GAP = 0.45;

// channels at any rate -> one 16 kHz channel, what Whisper reads
export function to16k(channels, sr) {
  const n = channels[0].length, m = Math.floor(n * 16000 / sr), out = new Float32Array(m), k = sr / 16000, w = Math.max(1, Math.floor(k));
  for (let i = 0; i < m; i++) {
    const a = Math.floor(i * k); let v = 0;
    for (let j = 0; j < w; j++) for (const c of channels) v += c[a + j] || 0;
    out[i] = v / (w * channels.length);
  }
  return out;
}
export function transcribe(samples, { language = 'auto', onStatus = () => {} } = {}) {
  return new Promise((resolve, reject) => {
    const w = new Worker(new URL('./transcribe-worker.js', import.meta.url), { type: 'module' });
    const end = () => w.terminate();
    w.onmessage = ({ data: d }) => {
      if (d.kind === 'status') onStatus(d.text + '…');
      else if (d.kind === 'progress') onStatus(`Downloading the speech model once: ${Math.round(d.done / 1048576)} of ${Math.round(d.total / 1048576)} MB`);
      else if (d.kind === 'error') { end(); reject(Error(d.message)); }
      else if (d.kind === 'done') { end(); resolve({ text: d.text, words: d.words }); }
    };
    w.onerror = e => { end(); reject(Error(e.message || 'The transcriber stopped')); };
    w.postMessage({ samples, language }, [samples.buffer]);
  });
}
// words [{ text, t0, t1 }] in seconds -> caption lines: a new one at sentence ends, at a pause,
// or at six words
export function captionsFrom(words) {
  const out = []; let cur = null;
  for (const w of words) {
    if (!w.text) continue;
    if (cur && (cur.n >= MAX_WORDS || w.t0 - cur.t1 > GAP || /[.!?।]$/.test(cur.text))) { out.push(cur); cur = null; }
    if (!cur) cur = { text: w.text, t0: w.t0, t1: w.t1, n: 1 };
    else { cur.text += ' ' + w.text; cur.t1 = w.t1; cur.n++; }
  }
  if (cur) out.push(cur);
  return out.map(({ text, t0, t1 }) => ({ text, t0, t1 }));
}
