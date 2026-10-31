// Lip sync over a beat: a synthetic rap mix (voiced syllables at known times, centred, over
// a kick, snare, hats and a bass line) must change the mouth on every syllable and open it on
// the syllables, not on the drums. The classic reader is measured too, to show the difference.
const fs = require('fs'), os = require('os'), path = require('path');
const ok = (c, m) => { if (!c) { console.log('FAIL', m); process.exitCode = 1; } else console.log('ok  ', m); };

function rng(seed) { let s = seed >>> 0; return () => ((s = (s * 1664525 + 1013904223) >>> 0) / 4294967296); }

function mix(seed, { drums = 1, seconds = 12 } = {}) {
  const sr = 44100, n = sr * seconds, L = new Float32Array(n), R = new Float32Array(n), rand = rng(seed);
  const syll = [];
  // syllables: rap pacing, 3-6 per second in phrases with breaths between
  for (let t = 0.4; t < seconds - 0.6;) {
    const phrase = 4 + Math.floor(rand() * 6);
    for (let i = 0; i < phrase && t < seconds - 0.6; i++) {
      const dur = 0.1 + rand() * 0.12;
      syll.push({ t, dur, f0: 120 + rand() * 60, vowel: Math.floor(rand() * 3) });
      t += dur + 0.04 + rand() * 0.12;
    }
    t += 0.35 + rand() * 0.4;
  }
  const FORM = [[730, 1090], [270, 2290], [570, 840]];
  for (const s of syll) {
    const a = Math.floor(s.t * sr), b = Math.floor((s.t + s.dur) * sr), [F1, F2] = FORM[s.vowel];
    for (let i = a; i < b; i++) {
      const u = (i - a) / sr, env = Math.min(1, u / 0.012) * Math.min(1, (b - i) / sr / 0.03);
      let v = 0;
      for (let h = 1; h * s.f0 < 4500; h++) {
        const f = h * s.f0, g = Math.exp(-(((f - F1) / 160) ** 2)) + 0.6 * Math.exp(-(((f - F2) / 220) ** 2)) + 0.05;
        v += g * Math.sin(2 * Math.PI * f * u) / Math.sqrt(h);
      }
      L[i] += 0.12 * env * v; R[i] += 0.12 * env * v;
    }
  }
  if (drums) {
    const bpm = 92, beat = 60 / bpm;
    for (let t = 0; t < seconds; t += beat / 4) {
      const step = Math.round(t / (beat / 4)) % 16, a = Math.floor(t * sr);
      const hit = (len, fn, pan = 0) => { for (let i = 0; i < len * sr && a + i < n; i++) { const v = drums * fn(i / sr); L[a + i] += v * (1 - pan); R[a + i] += v * (1 + pan); } };
      if (step === 0 || step === 7 || step === 10) hit(0.35, u => 0.9 * Math.sin(2 * Math.PI * (50 + 90 * Math.exp(-u * 30)) * u) * Math.exp(-u * 9));          // kick
      if (step === 4 || step === 12) hit(0.2, u => (0.5 * (rand() * 2 - 1) + 0.4 * Math.sin(2 * Math.PI * 190 * u)) * Math.exp(-u * 18));                        // snare
      if (step % 2 === 0 || rand() < 0.3) hit(0.04, u => 0.25 * (rand() * 2 - 1) * Math.exp(-u * 90), 0.3);                                                    // hats
    }
    // bass line, sustained under everything
    for (let i = 0; i < n; i++) { const u = i / sr, f = [55, 55, 65.4, 49][Math.floor(u / (4 * beat)) % 4]; const v = 0.25 * (Math.sin(2 * Math.PI * f * u) + 0.3 * Math.sin(4 * Math.PI * f * u)); L[i] += v; R[i] += v; }
  }
  return { L, R, sr, syll };
}

// share of syllables whose start the mouth visibly marks (a change within a frame of it)
function perSyllable(m, syll, fps) {
  let hit = 0;
  for (const s of syll) { const f = Math.round(s.t * fps); if ([f - 1, f, f + 1].some(k => k > 0 && m[k] !== m[k - 1])) hit++; }
  return +(hit / syll.length).toFixed(2);
}
function score(mouths, syll, fps) {
  const REST = 1, MBP = 7;
  const open = f => mouths[f] !== REST && mouths[f] !== MBP;
  const starts = [];
  for (let f = 1; f < mouths.length; f++) if (open(f) && !open(f - 1)) starts.push(f);
  const truth = [];   // word starts: a syllable after a gap the mouth can close in (>= 2 frames)
  syll.forEach((s, i) => { if (i === 0 || s.t - (syll[i - 1].t + syll[i - 1].dur) > 2 / fps) truth.push(Math.round(s.t * fps)); });
  const errs = truth.map(t => Math.min(99, ...starts.map(s => Math.abs(s - t))));
  const falses = starts.filter(s => !syll.some(x => s >= Math.round(x.t * fps) - 2 && s <= Math.round((x.t + x.dur) * fps) + 1)).length;
  // frames the mouth is open in true silence (> 2 frames from any syllable)
  let openSilent = 0, silent = 0;
  for (let f = 0; f < mouths.length; f++) {
    const near = syll.some(x => f >= Math.round(x.t * fps) - 2 && f <= Math.round((x.t + x.dur) * fps) + 2);
    if (!near) { silent++; if (open(f)) openSilent++; }
  }
  errs.sort((a, b) => a - b);
  return { words: truth.length, over2: errs.filter(e => e > 2).length, max: errs[errs.length - 1], p90: errs[Math.floor(errs.length * 0.9)], within1: +(errs.filter(e => e <= 1).length / errs.length).toFixed(2), falses, openInSilence: +(openSilent / Math.max(1, silent)).toFixed(2) };
}

(async () => {
  const tmp = path.join(os.tmpdir(), 'vocals-' + process.pid + '.mjs');
  fs.copyFileSync(path.join(__dirname, '..', 'app', 'src', 'vocals.js'), tmp);
  const V = await import('file://' + tmp);
  const fps = 30;
  for (const seed of [1, 2, 3]) {
    const m = mix(seed);
    const t0 = Date.now();
    const mouths = V.mouthsFor(m.L, m.R, m.sr, fps), ms = Date.now() - t0;
    const neu = score(mouths, m.syll, fps), old = score(V.mouthsFor(m.L, m.R, m.sr, fps, { engine: 'classic' }), m.syll, fps);
    const each = perSyllable(mouths, m.syll, fps);
    console.log(`mix ${seed}: classic ${JSON.stringify(old)}\n       syllables ${JSON.stringify(neu)} per-syllable ${each} (${ms} ms for 12 s)`);
    ok(each >= 0.9, `mix ${seed}: the mouth changes on ${Math.round(each * 100)}% of syllables (at least 90%)`);
    ok(neu.within1 >= 0.7 && neu.p90 <= 7, `mix ${seed}: word starts land on the vocal (70% within 1 frame)`);
    ok(neu.falses <= 1 && neu.openInSilence <= 0.05, `mix ${seed}: the beat doesn't open the mouth between words`);
    ok(neu.within1 > old.within1 && neu.openInSilence < old.openInSilence, `mix ${seed}: better than the classic reader`);
  }
  // a dry voice (no music) keeps working as before
  const dry = mix(4, { drums: 0 });
  ok(V.bedLevel(dry.L, dry.R, dry.sr, fps) < 0.06 && [1, 2, 3].every(k => V.bedLevel(...(m => [m.L, m.R, m.sr])(mix(k)), fps) > 0.06), 'music under the voice is detected, a dry voice is read as it is');
  const dm = V.mouthsFor(dry.L, dry.R, dry.sr, fps), d = score(dm, dry.syll, fps);
  console.log('dry voice', JSON.stringify(d), 'per-syllable', perSyllable(dm, dry.syll, fps));
  ok(d.max <= 1 && d.falses === 0 && perSyllable(dm, dry.syll, fps) >= 0.97, 'a dry voice syncs to the frame, a mouth change on every syllable');
  // a separated vocal handed in as the stem reads like the dry voice, whatever the mix carries
  const wet = mix(4), sm = V.mouthsFor(wet.L, wet.R, wet.sr, fps, { stem: { x: dry.L, sr: dry.sr } }), s2 = score(sm, dry.syll, fps);
  ok(s2.max <= 1 && perSyllable(sm, dry.syll, fps) >= 0.97, `with a vocal stem the mix is ignored and the stem syncs to the frame (${JSON.stringify(s2)})`);
  // no open-mouth holds through a run of syllables: the longest open run stays within one syllable
  let run = 0, worst = 0;
  for (let f = 1; f < dm.length; f++) { run = dm[f] === dm[f - 1] && dm[f] !== 1 && dm[f] !== 7 ? run + 1 : 0; worst = Math.max(worst, run); }
  ok(worst <= 8, `no long open holds on the dry voice (longest ${worst + 1} frames)`);
  fs.unlinkSync(tmp);
})();
