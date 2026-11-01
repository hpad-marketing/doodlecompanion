#!/usr/bin/env node
// Runs every Doodle Studio 3D test suite (tools/test_*.cjs and tools/test_*.mjs) one after another
// and prints one summary. Used by CI on every pull request and by hand:
//
//   node tools/run_tests.cjs                    every suite this machine can run
//   node tools/run_tests.cjs --only=mcp,batch1  just these (names without test_ and the extension)
//   node tools/run_tests.cjs --shard=2/4        the 2nd quarter of the list (CI splits the work)
//   node tools/run_tests.cjs --no-skip          run even the suites whose needs look missing
//   node tools/run_tests.cjs --list             the suites, what each one needs, and whether it would run
//
// A suite passes when it exits 0, prints no line starting with FAIL and reports no failed render
// (a NOTIFY line with state failed). Suites run one at a
// time because several share fixed local ports; each runs in its own process group, which is
// killed afterwards, so a dev server a suite left behind can't poison the next one.
//
// Some suites need things a bare machine doesn't have. They are skipped (and say why) unless:
//   library  DSL_LIBRARY points at a Doodle Library folder (one with library.json)
//   bpy      DS3D_BPY points at a Python that can `import bpy` (pip install bpy), standing in for Blender
//   audio    ffmpeg is on the PATH
//   electron ELECTRON points at the electron binary (the packaged smoke test)
// Set REQUIRE_ALL=1 to turn those skips into failures (a full run on the PC).
const { spawn, spawnSync } = require('node:child_process');
const fs = require('node:fs'), path = require('node:path');

const TOOLS = __dirname;
const NEEDS = {
  // filled in from full runs: what each suite reaches for beyond node + playwright (a suite that
  // renders a library set or prop needs the library even if it never names it)
  library: ['batch7', 'batch13', 'costar_frame', 'floor', 'library', 'lights', 'looks', 'mirror', 'rules_scene', 'squash', 'stage', 'stage_close', 'ux2d', 'visual_library'],
  bpy: ['carousel', 'costar_frame', 'floor', 'lights', 'looks', 'mirror', 'render', 'rules', 'rules_scene', 'scene', 'scene50', 'squash',
    'stage', 'stage_close', 'ux2d'],
  audio: ['vocals', 'babble'],
  electron: ['packaged'],
};
// longer than the default: whole scenes rendered through bpy
const SLOW = { scene50: 1500, scene: 900, render: 900, stage: 900, mirror: 900, lights: 900, materials: 900 };

const args = Object.fromEntries(process.argv.slice(2).map(a => { const [k, ...v] = a.replace(/^--/, '').split('='); return [k, v.length ? v.join('=') : true]; }));
const nameOf = f => f.replace(/^test_/, '').replace(/\.(c|m)?js$/, '');
let suites = fs.readdirSync(TOOLS).filter(f => /^test_.+\.(cjs|mjs)$/.test(f)).sort((a, b) => nameOf(a).localeCompare(nameOf(b), 'en', { numeric: true }));
if (args.only) { const want = String(args.only).split(',').map(s => s.trim()); suites = suites.filter(f => want.includes(nameOf(f))); }
if (args.shard) {
  const [i, n] = String(args.shard).split('/').map(Number);
  suites = suites.filter((_, k) => k % n === i - 1);
}

const have = {
  library: !!process.env.DSL_LIBRARY && fs.existsSync(path.join(process.env.DSL_LIBRARY, 'library.json')),
  bpy: !!process.env.DS3D_BPY && spawnSync(process.env.DS3D_BPY, ['-c', 'import bpy'], { stdio: 'ignore' }).status === 0,
  audio: spawnSync('ffmpeg', ['-version'], { stdio: 'ignore' }).status === 0,
  electron: !!process.env.ELECTRON && fs.existsSync(process.env.ELECTRON),
};
const missing = name => (args['no-skip'] ? [] : Object.keys(NEEDS).filter(k => NEEDS[k].includes(name) && !have[k]));

if (args.list) {
  for (const f of suites) { const m = missing(nameOf(f)); console.log(nameOf(f).padEnd(16), m.length ? 'skip (needs ' + m.join(', ') + ')' : 'run'); }
  process.exit(0);
}

function runOne(file) {
  const name = nameOf(file), limit = (Number(args.timeout) || SLOW[name] || 420) * 1000;
  return new Promise(resolve => {
    const t0 = Date.now();
    // own process group (detached) so the whole tree, dev servers included, can be killed afterwards
    const child = spawn(process.execPath, [path.join(TOOLS, file)], { cwd: path.join(TOOLS, '..'), detached: true, stdio: ['ignore', 'pipe', 'pipe'] });
    let out = '';
    child.stdout.on('data', d => { out += d; if (args.verbose) process.stdout.write(d); });
    child.stderr.on('data', d => { out += d; if (args.verbose) process.stderr.write(d); });
    let timedOut = false;
    const timer = setTimeout(() => { timedOut = true; try { process.kill(-child.pid, 'SIGKILL'); } catch {} }, limit);
    child.on('close', code => {
      clearTimeout(timer);
      try { process.kill(-child.pid, 'SIGKILL'); } catch {}
      // older render suites print NOTIFY <job> <state> instead of ok/FAIL: a failed render is a failure
      const fails = out.split('\n').filter(l => /^FAIL\b/.test(l) || /^NOTIFY .* failed\b/.test(l));
      const passed = code === 0 && !fails.length && !timedOut;
      resolve({ name, passed, code, timedOut, seconds: Math.round((Date.now() - t0) / 1000), fails, tail: out.split('\n').slice(-25).join('\n'), oks: out.split('\n').filter(l => /^ok\b/.test(l)).length });
    });
  });
}

(async () => {
  const results = [];
  for (const f of suites) {
    const name = nameOf(f), m = missing(name);
    if (m.length) {
      const r = { name, skipped: true, why: 'needs ' + m.join(', ') };
      if (process.env.REQUIRE_ALL) Object.assign(r, { skipped: false, passed: false, fails: ['FAIL missing ' + m.join(', ')] });
      results.push(r); console.log((r.skipped ? 'skip ' : 'FAIL ') + name.padEnd(16) + r.why); continue;
    }
    const r = await runOne(f);
    results.push(r);
    console.log((r.passed ? 'pass ' : 'FAIL ') + name.padEnd(16) + `${r.seconds}s, ${r.oks ? r.oks + ' checks' : 'output only'}` + (r.timedOut ? ', timed out' : '') + (r.passed ? '' : `, exit ${r.code}`));
    if (!r.passed) console.log('     ' + (r.fails.length ? r.fails.slice(0, 8).join('\n     ') : r.tail.split('\n').join('\n     ')));
  }
  const pass = results.filter(r => r.passed).length, fail = results.filter(r => !r.skipped && !r.passed), skip = results.filter(r => r.skipped);
  const line = `${pass} passed, ${fail.length} failed, ${skip.length} skipped of ${results.length} suites`;
  console.log('\n' + line + (fail.length ? '\nFailed: ' + fail.map(r => r.name).join(', ') : ''));
  const out = args.json || process.env.DS3D_TEST_JSON;
  if (out) fs.writeFileSync(out, JSON.stringify({ line, results }, null, 1));
  if (process.env.GITHUB_STEP_SUMMARY) {
    const rows = results.map(r => `| ${r.name} | ${r.skipped ? 'skipped (' + r.why + ')' : r.passed ? 'pass' : '**FAIL**'} | ${r.seconds ?? ''} | ${r.oks ?? ''} |`);
    fs.appendFileSync(process.env.GITHUB_STEP_SUMMARY, `### Test suites${args.shard ? ' (shard ' + args.shard + ')' : ''}\n\n${line}\n\n| suite | result | seconds | checks |\n|---|---|---|---|\n${rows.join('\n')}\n\n`);
  }
  process.exit(fail.length ? 1 : 0);
})();
