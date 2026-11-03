// Runs Whisper in the editor, off the main thread. The model downloads once on first use and
// the browser cache keeps it; the audio never leaves this PC.
import { pipeline, env } from '../vendor/hf/transformers.min.js';

const MODEL = 'onnx-community/whisper-base_timestamped';
env.allowLocalModels = false;
env.backends.onnx.wasm.wasmPaths = new URL('../vendor/hf/', import.meta.url).href;
let asr = null;
async function load() {
  if (asr) return asr;
  const progress = p => { if (p.status === 'progress' && p.total) postMessage({ kind: 'progress', file: p.file, done: p.loaded, total: p.total }); };
  // on the CPU on purpose: the graphics card path gave garbage text in the real app, and this
  // runs faster than the speech itself
  postMessage({ kind: 'status', text: 'Loading the speech model' });
  asr = await pipeline('automatic-speech-recognition', MODEL, { dtype: 'q8', progress_callback: progress });
  return asr;
}
onmessage = async e => {
  try {
    const run = await load();
    postMessage({ kind: 'status', text: 'Listening' });
    const language = e.data.language && e.data.language !== 'auto' ? e.data.language : undefined;
    const r = await run(e.data.samples, { return_timestamps: 'word', chunk_length_s: 30, stride_length_s: 5, task: 'transcribe', ...(language ? { language } : {}) });
    postMessage({ kind: 'done', text: r.text.trim(), words: (r.chunks || []).map(c => ({ text: c.text.trim(), t0: c.timestamp[0], t1: c.timestamp[1] ?? c.timestamp[0] })) });
  } catch (err) { postMessage({ kind: 'error', message: err.message || String(err) }); }
};
