"""Voice > Takes showed a blank page when the shot had no takes: its only line is the intro
paragraph, which the tool shelves hide as a first-child caption. An empty state now says
what goes there. Usage: python patch_voice_takes_empty.py <src folder or built HTML>."""
import sys,os
OLD="row.querySelector('[data-voice-choose]').onclick=S.run(()=>{chooseTake(take.uid);S.menu.close();});takes.append(row);}});"
NEW="row.querySelector('[data-voice-choose]').onclick=S.run(()=>{chooseTake(take.uid);S.menu.close();});takes.append(row);}if(!takes.querySelector('.motion-take'))takes.append(S.create('p',{className:'empty-state',textContent:'No voice takes in this shot yet. Every voice recording you keep lands here.'}));});"
t=sys.argv[1];p=os.path.join(t,'audio.js') if os.path.isdir(t) else t
s=open(p,encoding='utf-8').read()
if NEW in s:print('already patched');sys.exit()
assert s.count(OLD)==1,s.count(OLD);open(p,'w',encoding='utf-8').write(s.replace(OLD,NEW));print('patched',p)
