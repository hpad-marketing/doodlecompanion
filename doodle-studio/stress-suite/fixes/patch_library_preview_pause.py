"""Idempotent fix (performance.js): Motion library previews kept rendering in idle callbacks after the library was
closed (they walk all ~370 motions, two full rig renders per pose), which slowed playback for the rest of the session.
Now the builder pauses while the library is not on screen and resumes when it is visible again (IntersectionObserver).
Run from the source root: python patch_library_preview_pause.py src"""
import sys,pathlib
src=pathlib.Path(sys.argv[1] if len(sys.argv)>1 else 'src');p=src/'performance.js';s=p.read_text(encoding='utf-8')
MARK='/*preview-pause*/'
if MARK in s: print('already patched');sys.exit()
a="let previewQueue=[],previewJob=null,previewTimer=0;"
b=a+MARK+"let previewPaused=false,previewWatch=null;const libraryHost=()=>window.BunnyStudio?.menuSections?.library,libraryVisible=()=>{const h=libraryHost();return !!h&&h.isConnected&&h.getClientRects().length>0;};function watchLibrary(){const h=libraryHost();if(previewWatch||!h||!window.IntersectionObserver)return;previewWatch=new IntersectionObserver(list=>{if(previewPaused&&list.some(e=>e.isIntersecting)){previewPaused=false;schedulePreview();}});previewWatch.observe(h);}"
c="previewTimer=0;previewQueue=previewQueue.filter(job=>job.image.isConnected);"
d="previewTimer=0;watchLibrary();if(!libraryVisible()){previewPaused=true;return;}previewQueue=previewQueue.filter(job=>job.image.isConnected);"
for x,y in [(a,b),(c,d)]:
    if s.count(x)!=1: sys.exit('pattern not found in performance.js: '+x[:50])
    s=s.replace(x,y)
p.write_text(s,encoding='utf-8');print('patched')
