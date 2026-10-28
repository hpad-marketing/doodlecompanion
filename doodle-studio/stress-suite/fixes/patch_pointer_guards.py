"""Idempotent fix: `g?.pointer!==e.pointerId` lets a pointer event with no pointerId through when no gesture
is active (undefined!==undefined is false), then crashes on g.pointer. Found by the stress suite.
Run from the source root: python tools/patch_pointer_guards.py   (or pass the src folder)."""
import re,sys,pathlib
src=pathlib.Path(sys.argv[1] if len(sys.argv)>1 else 'src')
pat=re.compile(r'([A-Za-z_]+)\?\.pointer(Id)?!==([A-Za-z_]+)\.pointerId')
n=0
for f in ['character-strip.js','timeline-context.js','voice-editor.js']:
    p=src/f
    if not p.exists(): continue
    s=p.read_text(encoding='utf-8');t,k=pat.subn(lambda m:f'!{m[1]}||{m[1]}.pointer{m[2] or ""}!=={m[3]}.pointerId',s)
    if k: p.write_text(t,encoding='utf-8');n+=k;print(f,k)
print('patched',n)
