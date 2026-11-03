// Reel templates and script to first-draft scene.
// Both end in the same plan: one beat per shot, each with its words, speaker, face, a gesture,
// a camera framing (+ move), captions, an optional key-word headline and a fill-in note.
// main.js (reelBuild) turns a plan into a scene: shots, camera keys, face and pose keys,
// co-stars, babble voice with lip sync (or captions alone), headlines and markers.
// Everything here is pure, so it is tested in Node (tools/test_reels.cjs).

// ---------------------------------------------------------------- gestures (control values)
// Arms stay below and beside the head, hands never cross the face, so the built-in rules
// (arm in front, face clear) have nothing to fix. Verified with the app's rule check.
export const GESTURES = {
  rest:    { armL: 6, armR: 6, armLForward: 8, armRForward: 8, elbowL: 14, elbowR: 14, torsoBow: 0, rot: 0, headNod: 0 },
  open:    { armL: 38, armR: 38, armLForward: 34, armRForward: 34, elbowL: 46, elbowR: 46, torsoBow: 0, rot: 0, headNod: -2 },
  point:   { armL: 8, armR: 30, armLForward: 10, armRForward: 78, elbowL: 16, elbowR: 8, torsoBow: 4, rot: 0, headNod: 2 },
  chest:   { armL: 14, armR: 8, armLForward: 52, armRForward: 10, elbowL: 100, elbowR: 16, torsoBow: 0, rot: 0, headNod: 0 },
  shrug:   { armL: 26, armR: 26, armLForward: 12, armRForward: 12, elbowL: 58, elbowR: 58, torsoBow: 0, rot: 0, headNod: 0 },
  cheer:   { armL: 50, armR: 50, armLForward: 0, armRForward: 0, elbowL: 18, elbowR: 18, torsoBow: -2, rot: 0, headNod: -3 },
  count:   { armL: 8, armR: 36, armLForward: 10, armRForward: 50, elbowL: 16, elbowR: 40, torsoBow: 0, rot: 0, headNod: 0 },
  lean:    { armL: 10, armR: 10, armLForward: 30, armRForward: 30, elbowL: 40, elbowR: 40, torsoBow: 8, rot: 0, headNod: 4 },
  stop:    { armL: 8, armR: 34, armLForward: 10, armRForward: 66, elbowL: 16, elbowR: 36, torsoBow: -3, rot: 0, headNod: -4 },
  slump:   { armL: 2, armR: 2, armLForward: 4, armRForward: 4, elbowL: 6, elbowR: 6, torsoBow: 8, rot: 0, headNod: 4 },
};
export const GESTURE_IDS = [...new Set(Object.values(GESTURES).flatMap(Object.keys))];

// ---------------------------------------------------------------- moods: face (library name), babble mood, gesture
// faces are found by name in the face library, so a renumbered library still works
export const MOODS = {
  neutral:  { face: '00 Neutral', voice: 'neutral', gesture: 'open' },
  happy:    { face: '01 Happy', voice: 'happy', gesture: 'open' },
  excited:  { face: 'Starry eyes', voice: 'happy', gesture: 'cheer' },
  proud:    { face: 'Proud beam', voice: 'happy', gesture: 'chest' },
  smug:     { face: 'Side-eye smirk', voice: 'neutral', gesture: 'chest' },
  sly:      { face: 'Scheming grin', voice: 'neutral', gesture: 'lean' },
  shocked:  { face: 'Jaw drop', voice: 'shocked', gesture: 'stop' },
  scared:   { face: 'Pinpoint panic', voice: 'shocked', gesture: 'stop' },
  confused: { face: '"Huh?" squint', voice: 'neutral', gesture: 'shrug' },
  thinking: { face: 'Mouth-to-side thinking', voice: 'neutral', gesture: 'count' },
  idea:     { face: 'Lightbulb', voice: 'happy', gesture: 'point' },
  sad:      { face: '06 Sad', voice: 'sad', gesture: 'slump' },
  angry:    { face: 'Steaming mad', voice: 'angry', gesture: 'stop' },
  annoyed:  { face: 'Eye roll', voice: 'angry', gesture: 'shrug' },
  tired:    { face: '16 Exhausted', voice: 'sleepy', gesture: 'slump' },
  love:     { face: '22 Love', voice: 'happy', gesture: 'chest' },
  cringe:   { face: 'Teeth-clench cringe', voice: 'neutral', gesture: 'shrug' },
  deadpan:  { face: '24 Deadpan', voice: 'neutral', gesture: 'rest' },
  determined: { face: '20 Determined', voice: 'neutral', gesture: 'point' },
};
// words in a line (or its [stage directions]) that set the mood; first match wins, most specific first
const MOOD_WORDS = [
  ['shocked', /\b((can'?t|won'?t|will not|wouldn'?t) believe|what\?!|wait,? what|no way|shock(ed|ing)?|surpris\w*|jaw|whoa|omg|plot twist|turns out)\b/i],
  ['scared', /\b(scar(y|ed)|afraid|terrif\w*|panic\w*|horror|creepy|nightmare|help)\b/i],
  ['angry', /\b(angry|furious|hate|rage|mad at|so annoying|unbelievable)\b/i],
  ['annoyed', /\b(ugh|annoy\w*|seriously|eye ?roll|whatever|again\?)\b/i],
  ['sad', /\b(sad|cry\w*|miss(ed)? (him|her|you|it)|lonely|lost|broke(n)?|sorry)\b/i],
  ['tired', /\b(tired|exhaust\w*|sleep\w*|yawn|monday)\b/i],
  ['love', /\b(love|cute|adore|heart|aww+)\b/i],
  ['cringe', /\b(cringe|awkward|embarrass\w*|oops)\b/i],
  ['excited', /\b(excit\w*|amazing|awesome|best|let'?s go|yay|finally|wow)\b/i],
  ['idea', /\b(idea|trick|hack|secret|tip|here'?s (how|why)|the answer)\b/i],
  ['proud', /\b(proud|i did it|nailed|won|made it)\b/i],
  ['smug', /\b(told you|obviously|of course|easy|actually)\b/i],
  ['sly', /\b(psst|between us|don'?t tell|nobody knows)\b/i],
  ['thinking', /\b(think|wonder|maybe|first|second|third|step \d|number \d|reason)\b/i],
  ['confused', /\?$|\b(why|huh|confus\w*|how come)\b/i],
  ['happy', /!$|\b(happy|glad|fun|nice|great|good news|haha|lol)\b/i],
];
export function moodOf(text, acts = []) {
  for (const a of acts) { const m = String(a).toLowerCase().trim(); if (MOODS[m]) return m; }
  const hay = [...acts, text].join(' . ');
  for (const [m, re] of MOOD_WORDS) if (re.test(hay)) return m;
  return 'neutral';
}
// stage directions that pick a gesture outright
const GESTURE_WORDS = [['point', /\bpoint\w*\b/i], ['shrug', /\bshrug\w*\b/i], ['cheer', /\b(cheer\w*|arms up|celebrat\w*)\b/i], ['chest', /\b(hand on (his |her )?chest|me\b)/i], ['lean', /\b(lean\w*|whisper\w*)\b/i], ['count', /\b(count\w*|list)\b/i], ['stop', /\b(stop|halt|hold on)\b/i], ['slump', /\b(slump\w*|sigh\w*)\b/i], ['open', /\b(open arms|present\w*)\b/i], ['rest', /\b(still|freeze|deadpan)\b/i]];
export function gestureOf(text, acts, mood) {
  for (const a of acts) for (const [g, re] of GESTURE_WORDS) if (re.test(a)) return g;
  if (/^(you|your)\b/i.test(text) || /\byou (need|should|have to|can)\b/i.test(text)) return 'point';
  if (/^(i|i'm|my|me)\b/i.test(text) && mood === 'neutral') return 'chest';
  return MOODS[mood]?.gesture || 'open';
}

// ---------------------------------------------------------------- camera
// Bunny is mostly head, so the reel framings start from the Camera tab's "Full" preset and
// back off: the key-word headline sits above his ears, the caption below his face, and he
// stays centred and standing on the floor. Eye level, no roll; a low angle only on a hero ending.
// Moves are keyed on the camera distance or lens and stay gentle, so the face never reaches the
// caption line (y 0.77 in reels).
export const CAPTION_Y = 0.77;
export const FRAMINGS = { wide: 1.8, full: 1.55, medium: 1.35 };
export const MOVES = {
  'push-in': { id: 'cam.dist', to: 0.9, frames: null, ease: 'ease' },     // the whole shot
  'pull-out': { id: 'cam.dist', to: 1.12, frames: null, ease: 'ease' },
  'crash-push': { id: 'cam.dist', to: 0.88, frames: 8, ease: 'snap' },     // a quick lunge on the hook
  'snap-zoom': { id: 'cam.lens', to: 1.15, frames: 6, ease: 'snap' },     // a comic hit on the key word
};
const CAM_WORDS = [['medium', /\b(extreme close|ecu|close[- ]?up|cu|mcu|medium|ms)\b/i], ['full', /\b(full shot|full body|fs)\b/i], ['wide', /\b(wide|ws)\b/i]];
const MOVE_WORDS = [['crash-push', /\b(crash|smash) ?(push|in)\b/i], ['snap-zoom', /\bsnap ?zoom\b/i], ['push-in', /\b(push|zoom) ?in\b/i], ['pull-out', /\b(pull ?(out|back)|reveal)\b/i]];
export function cameraFor(beat, i, n, prevSize) {
  const acts = beat.acts || [];
  let size = null, move = null, angle = 'eye';
  for (const a of acts) { for (const [s, re] of CAM_WORDS) if (!size && re.test(a)) size = s; for (const [m, re] of MOVE_WORDS) if (!move && re.test(a)) move = m; if (/\bextreme close|\becu\b/i.test(a)) move ||= 'snap-zoom'; if (/\blow angle\b/i.test(a)) angle = 'low'; }
  if (!size) {
    if (i === 0) { size = 'full'; move ||= 'crash-push'; }
    else if (['shocked', 'scared', 'angry'].includes(beat.mood)) { size = 'medium'; move ||= 'snap-zoom'; }
    else if (i === n - 1) { size = 'full'; move ||= 'push-in'; }
    else size = ['full', 'medium', 'wide', 'full', 'medium'][i % 5];
    if (size === prevSize && !move) size = size === 'full' ? 'medium' : 'full';
  }
  if (i === n - 1 && i > 0 && ['proud', 'determined', 'smug'].includes(beat.mood)) angle = 'low';   // a hero beat to end on
  // the opening shot of a two-hander shows everyone; after that the camera finds whoever talks
  const target = beat.costars && i === 0 ? 'group' : beat.speaker !== 'lead' && beat.speaker != null ? 'costar' + beat.speaker : 'bunny';
  // a single on someone in a two-hander is a medium, so the other character stays out of the frame
  if (target !== 'group' && beat.costars && size !== 'medium') size = 'medium';
  return { size, angle, move, target };
}

// ---------------------------------------------------------------- words
const STOP = new Set('a an the and or but so to of in on at for with is are was were be been it its it\'s this that these those i you he she we they me my your our their his her them us do does did not no yes just really very so then than there here what when where who how why if as by from up out about into over can could would should will shall may might must have has had im i\'m youre you\'re dont don\'t thats that\'s okay ok like get got'.split(' '));
// the key word of a line: what the user marked (*word* or ALL CAPS), else the longest content word
export function keyWords(text) {
  const marked = [...String(text).matchAll(/\*([^*]+)\*/g)].map(m => m[1].trim());
  if (marked.length) return marked;
  const caps = String(text).split(/\s+/).map(w => w.replace(/[^A-Za-z0-9']/g, '')).filter(w => w.length > 1 && w === w.toUpperCase() && /[A-Z]/.test(w));
  if (caps.length) return caps;
  const words = String(text).split(/\s+/).map(w => w.replace(/[^A-Za-z0-9']/g, '')).filter(w => w.length > 2 && !STOP.has(w.toLowerCase()));
  return words.length ? [words.reduce((a, b) => (b.length > a.length ? b : a))] : [];
}
export const plainText = t => String(t).replace(/\*([^*]+)\*/g, '$1').replace(/\s+/g, ' ').trim();
// captions: condensed chunks of up to 6 words, broken at punctuation first (1-3 words stay one line in post.js)
export function captionChunks(text, maxWords = 6) {
  const out = [];
  // sentence by sentence, each cut into even chunks so no word is left alone on a caption
  for (const sen of plainText(text).match(/[^.!?]+[.!?]+["')]*|[^.!?]+$/g) || []) {
    const w = sen.trim().split(' ').filter(Boolean);
    if (!w.length) continue;
    const n = Math.ceil(w.length / maxWords), per = Math.ceil(w.length / n);
    for (let i = 0; i < w.length; i += per) out.push(w.slice(i, i + per).join(' '));
  }
  // a one-word sentence ("Wait.") joins the next caption when they fit together
  for (let i = 0; i < out.length - 1; i++) if (out[i].split(' ').length === 1 && out[i + 1].split(' ').length < maxWords) { out.splice(i, 2, out[i] + ' ' + out[i + 1]); }
  return out;
}
// talking time of a line, a little slower than the babble so a shot never cuts a word
export const speechSeconds = text => { const n = plainText(text).split(' ').filter(Boolean).length; return n ? Math.max(1.2, n / 2.6 + 0.35) : 0; };

// ---------------------------------------------------------------- script parsing
// Lines: "# Heading" (a section; becomes a marker), "KOALA: line" (speaker), [stage directions] or
// (directions) anywhere, *key word* for the headline, "HEADLINE: TEXT" for a headline of its own,
// "---" or a blank line between beats. A long line with several sentences splits into shots.
export const CAST_NAMES = { bunny: 'bunny', koala: 'koala', frog: 'frog' };
export function parseScript(text) {
  const beats = [];
  let section = null, headline = null;
  for (let raw of String(text || '').replace(/\r/g, '').split('\n')) {
    raw = raw.trim();
    if (!raw || /^-{3,}$/.test(raw)) continue;
    if (/^#+\s*/.test(raw)) { section = raw.replace(/^#+\s*/, '').trim(); continue; }
    const hl = /^headline\s*:\s*(.+)$/i.exec(raw);
    if (hl) { headline = hl[1].trim(); continue; }
    const acts = [...raw.matchAll(/[[(]([^\])]+)[\])]/g)].map(m => m[1].trim());
    let say = raw.replace(/[[(][^\])]+[\])]/g, ' ').replace(/\s+/g, ' ').trim();
    // a speaker is a NAME IN CAPS or a cast name ("Koala:"), so "Hot take: ..." stays a line
    let who = /^([A-Za-z][A-Za-z ]{0,20}):\s*/.exec(say);
    if (who && !(who[1] === who[1].toUpperCase() || CAST_NAMES[who[1].toLowerCase()] || /^(narrator|vo)$/i.test(who[1]))) who = null;
    if (who) say = say.slice(who[0].length).trim();
    // split a long line at sentence ends so every shot stays short and readable
    const parts = [];
    for (const sen of plainText(say).split(' ').length > 16 ? (say.match(/[^.!?]+[.!?]+["')]*|[^.!?]+$/g) || [say]).map(x => x.trim()).filter(Boolean) : [say]) {
      const n = x => plainText(x).split(' ').filter(Boolean).length;
      // short sentences ride along with their neighbour (no one-word shots), up to 16 words a shot
      if (parts.length && (n(parts[parts.length - 1]) < 4 || n(parts[parts.length - 1]) + n(sen) <= 16)) parts[parts.length - 1] += ' ' + sen; else parts.push(sen);
    }
    // one sentence still over 16 words breaks at its comma nearest the middle
    for (let k = 0; k < parts.length; k++) {
      const w = parts[k].split(' ');
      if (plainText(parts[k]).split(' ').length <= 16) continue;
      const cuts = w.map((x, j) => (/,$/.test(x) && j > 2 && j < w.length - 3 ? j : -1)).filter(j => j >= 0);
      if (!cuts.length) continue;
      const j = cuts.reduce((a, b) => (Math.abs(b - w.length / 2) < Math.abs(a - w.length / 2) ? b : a));
      parts.splice(k, 1, w.slice(0, j + 1).join(' '), w.slice(j + 1).join(' '));
      k--;
    }
    parts.forEach((p, k) => {
      beats.push({ who: who ? who[1].trim() : null, text: p, acts: k === 0 ? acts : [], section: k === 0 ? section : null, headline: k === 0 ? headline : null });
    });
    section = null; headline = null;
  }
  return beats.filter(b => b.text || b.acts.length);
}

// ---------------------------------------------------------------- the plan
// beats: [{ who, text, acts, section, headline, mood?, gesture?, cam?, seconds?, label?, fill? }]
// opts: { lead: 'bunny' | 'koala' | 'frog', fps, headlines: 'hook' | 'marked' | 'all' | 'off' }
export function plan(beats, { lead = 'bunny', fps = 30, headlines = 'marked', name } = {}) {
  // speakers: the lead is the first speaker whose name is a cast member, else the scene's character;
  // everyone else becomes a co-star (koala / frog / bunny by name, else the next free character)
  const names = [...new Set(beats.map(b => b.who).filter(Boolean).map(w => w.toLowerCase()))];
  const leadName = names.find(n => CAST_NAMES[n] === lead) || names.find(n => CAST_NAMES[n] && !['narrator', 'vo'].includes(n)) || names[0] || null;
  const leadChar = (leadName && CAST_NAMES[leadName]) || lead;
  const free = ['bunny', 'koala', 'frog'].filter(c => c !== leadChar);
  const costars = [];
  for (const n of names) {
    if (n === leadName || n === 'narrator' || n === 'vo') continue;
    const ch = CAST_NAMES[n] && CAST_NAMES[n] !== leadChar && !costars.some(c => c.character === CAST_NAMES[n]) ? CAST_NAMES[n] : free.find(c => !costars.some(x => x.character === c)) || free[0];
    if (costars.length < 2) costars.push({ name: n, character: ch });
  }
  const out = [];
  let prevSize = null;
  beats.forEach((b, i) => {
    const text = b.text || '', acts = b.acts || [];
    const mood = b.mood || moodOf(plainText(text), acts);
    const whoName = b.who ? b.who.toLowerCase() : leadName;
    const co = costars.findIndex(c => c.name === whoName);
    const speaker = co >= 0 ? co : 'lead';
    const beat = { ...b, mood, speaker, costars: costars.length > 0 };
    const cam = { ...cameraFor(beat, i, beats.length, prevSize), ...(b.cam || {}) };
    prevSize = cam.size;
    const talk = speechSeconds(text);
    const seconds = Math.max(b.seconds || 0, talk + 0.6, b.minSeconds || 1.5);
    const keys = keyWords(text);
    let head = b.headline || null;
    if (!head && headlines !== 'off' && keys.length && (headlines === 'all' || (headlines === 'hook' && i === 0) || (headlines === 'marked' && (i === 0 || /\*[^*]+\*/.test(text))))) head = keys.join(' ');
    out.push({
      index: i, label: (b.label || b.section || plainText(text).split(' ').slice(0, 4).join(' ') || 'Beat ' + (i + 1)).slice(0, 40),
      who: b.who || null, speaker, text: plainText(text), mood, face: MOODS[mood].face, voice: MOODS[mood].voice,
      gesture: b.gesture || gestureOf(plainText(text), acts, mood), cam, frames: Math.round(seconds * fps), talkFrames: Math.round(talk * fps),
      captions: captionChunks(text), headline: head ? plainText(head).toUpperCase() : null, section: b.section || null, fill: b.fill || null, acts,
    });
  });
  return { name: name || (out[0] ? out[0].label : 'Script draft'), lead: leadChar, costars: costars.map(c => ({ ...c })), fps, beats: out, seconds: +(out.reduce((a, b) => a + b.frames, 0) / fps).toFixed(1) };
}
export const fromScript = (text, opts = {}) => {
  const beats = parseScript(text);
  if (!beats.length) throw Error('Paste a script first: one line per beat, "KOALA: line" for a co-star, [directions] in brackets, *key word* for the headline');
  return plan(beats, opts);
};

// ---------------------------------------------------------------- five ready-to-fill reel templates (9:16)
// Each slot is a line to fill. Unfilled slots keep their example line, so the draft plays at once,
// and a "Fill:" marker shows what to write there.
export const REELS = [
  { id: 'reel-storytime', name: 'Storytime: hook to twist', blurb: 'A short story that opens on its most surprising moment, builds, twists, and loops back to the start.',
    slots: [
      { key: 'hook', label: 'Hook', hint: 'The most surprising moment, said first (under 8 words)', example: 'I accidentally adopted a *ghost*.', mood: 'shocked', cam: { size: 'full', move: 'crash-push' }, headline: true },
      { key: 'setup', label: 'Setup', hint: 'Where and when it started', example: 'It started with a cold spot on my couch.', mood: 'thinking', cam: { size: 'wide' } },
      { key: 'build', label: 'Build', hint: 'It gets stranger: one detail that raises the stakes', example: 'Then my snacks started disappearing. Only the crunchy ones.', mood: 'confused', cam: { size: 'full', move: 'push-in' } },
      { key: 'twist', label: 'Twist', hint: 'The reveal', example: 'Turns out the ghost was my *roommate*.', mood: 'shocked', cam: { size: 'medium', move: 'snap-zoom' }, headline: true },
      { key: 'payoff', label: 'Payoff', hint: 'How it ended, with a line that leads back into the hook', example: 'Anyway, that is why I accidentally adopted a ghost.', mood: 'smug', cam: { size: 'full', angle: 'low', move: 'push-in' } },
    ] },
  { id: 'reel-three-things', name: '3 things you did not know', blurb: 'A countdown of three facts or tips, each in its own shot, ending on the best one.',
    slots: [
      { key: 'hook', label: 'Hook', hint: '"3 things about X nobody tells you"', example: '3 things about *doodling* nobody tells you.', mood: 'sly', cam: { size: 'full', move: 'crash-push' }, headline: true },
      { key: 'one', label: 'Thing 1', hint: 'The good one', example: 'One. Bad lines are just early lines.', mood: 'thinking', gesture: 'count', cam: { size: 'full' }, headline: 'ONE' },
      { key: 'two', label: 'Thing 2', hint: 'The better one', example: 'Two. Draw it ten times and it gets easy.', mood: 'idea', gesture: 'count', cam: { size: 'wide' }, headline: 'TWO' },
      { key: 'three', label: 'Thing 3', hint: 'The best one, saved for last', example: 'Three. Nobody is grading your sketchbook.', mood: 'excited', gesture: 'cheer', cam: { size: 'medium', move: 'push-in' }, headline: 'THREE' },
      { key: 'ask', label: 'Ask', hint: 'One ask: save, follow or comment a word', example: 'Save this for your next blank page.', mood: 'happy', gesture: 'point', cam: { size: 'full' } },
    ] },
  { id: 'reel-myth-fact', name: 'Myth vs fact', blurb: 'Bunny says a common belief with confidence, catches himself, then gives the real answer.',
    slots: [
      { key: 'myth', label: 'Myth', hint: 'The common belief, said confidently', example: 'Everyone knows bunnies love *carrots*.', mood: 'smug', cam: { size: 'full', move: 'push-in' }, headline: 'MYTH' },
      { key: 'catch', label: 'Catch', hint: 'The double take (2-4 words)', example: 'Wait. What?!', mood: 'shocked', cam: { size: 'medium', move: 'snap-zoom' } },
      { key: 'fact', label: 'Fact', hint: 'What is actually true', example: 'Actually, carrots are a treat. We mostly eat hay.', mood: 'idea', cam: { size: 'medium' }, headline: 'FACT' },
      { key: 'kicker', label: 'Kicker', hint: 'A funny last line', example: 'Hay is the real main character.', mood: 'proud', cam: { size: 'full', angle: 'low', move: 'push-in' } },
    ] },
  { id: 'reel-pov-skit', name: 'POV skit with a co-star', blurb: 'A two-character skit under a POV headline, ending on a reaction shot.',
    slots: [
      { key: 'pov', label: 'POV headline', hint: 'The situation, on screen only (not spoken)', example: 'POV: your friend says "one more episode"', headlineOnly: true, mood: 'deadpan', cam: { size: 'wide' } },
      { key: 'line1', label: 'Co-star line', hint: 'The co-star (Koala) starts it', example: 'KOALA: Just one more episode, I promise.', mood: 'happy', cam: { size: 'full' } },
      { key: 'line2', label: 'Bunny reply', hint: 'Bunny pushes back', example: 'BUNNY: You said that four hours ago.', mood: 'annoyed', cam: { size: 'medium' } },
      { key: 'line3', label: 'Co-star comeback', hint: 'The twist line', example: 'KOALA: This is a different one more.', mood: 'smug', cam: { size: 'full' } },
      { key: 'react', label: 'Reaction', hint: 'Bunny\'s reaction (a few words or [no words])', example: 'BUNNY: [deadpan] Fair.', mood: 'deadpan', cam: { size: 'medium', move: 'snap-zoom' } },
    ] },
  { id: 'reel-hot-take', name: 'Hot take', blurb: 'A bold opinion, one reason, the "but", and a mic-drop line that loops.',
    slots: [
      { key: 'take', label: 'The take', hint: 'The bold opinion, in one sentence', example: 'Hot take: *naps* are a skill.', mood: 'determined', cam: { size: 'full', move: 'crash-push' }, headline: true },
      { key: 'why', label: 'Why', hint: 'One reason', example: 'Twenty minutes and I am a new bunny.', mood: 'proud', cam: { size: 'full' } },
      { key: 'but', label: 'The but', hint: 'Admit the catch', example: 'Two hours though? That is a coma.', mood: 'cringe', cam: { size: 'wide' } },
      { key: 'drop', label: 'Mic drop', hint: 'The last line, leading back into the take', example: 'Practice your naps. It is a skill.', mood: 'smug', gesture: 'point', cam: { size: 'full', angle: 'low', move: 'push-in' } },
    ] },
];
export const reelById = id => {
  const t = REELS.find(r => r.id === id);
  if (!t) throw Error('No reel template ' + id + '. Templates: ' + REELS.map(r => r.id).join(', '));
  return t;
};
// fills: { slotKey: 'line' } (a line can start with "KOALA:" and hold [directions] like any script line)
export function fromTemplate(id, fills = {}, opts = {}) {
  const t = reelById(id), beats = [];
  let headline = null;
  for (const s of t.slots) {
    const given = fills[s.key] != null && String(fills[s.key]).trim() ? String(fills[s.key]).trim() : null;
    const line = given || s.example;
    if (s.headlineOnly) { headline = plainText(line).toUpperCase(); continue; }
    const [b] = parseScript(line);
    if (!b) continue;
    // the slot's direction wins unless the filled line names its own
    const own = b.acts.length > 0;
    beats.push({ ...b, label: s.label, mood: own ? undefined : s.mood, gesture: own ? undefined : s.gesture, cam: s.cam, minSeconds: 1.5,
      headline: headline || (typeof s.headline === 'string' ? s.headline : null), fill: given ? null : s.hint });
    if (s.headline === true && !headline && !/\*[^*]+\*/.test(b.text)) beats[beats.length - 1].headline = keyWords(b.text).join(' ') || null;
    headline = null;
  }
  const p = plan(beats, { ...opts, headlines: 'marked' });
  // only the slots that ask for a headline keep one
  p.beats.forEach((b, i) => { const s = t.slots.filter(x => !x.headlineOnly)[i]; if (s && !s.headline && !beats[i].headline) b.headline = null; });
  p.template = t.id; p.name = opts.name || t.name;
  p.unfilled = t.slots.filter(s => !(fills[s.key] && String(fills[s.key]).trim())).map(s => s.key);
  return p;
}
