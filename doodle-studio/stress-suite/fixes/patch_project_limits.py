"""Opening a hostile project could overflow the stack on Windows (2,000-deep nesting, or a
track with 200,000 keys), and when the overflow happened after the swap the open project
was left replaced by the refused file. Now the file is refused up front with a plain
reason, and any failure while switching restores the project that was open.
Usage: python patch_project_limits.py <src folder or built HTML>."""
import sys,os
A_OLD="if(!p||!p.keys||!Array.isArray(p.clips)||!Array.isArray(p.cues))throw Error('Not a Bunny project');"
A_NEW=A_OLD+"/*project-limits*/{const stack=[[p,0]];while(stack.length){const [v,d]=stack.pop();if(!v||typeof v!=='object')continue;if(d>64)throw Error('Project file is nested too deeply to open');for(const k in v)if(Object.prototype.hasOwnProperty.call(v,k)&&v[k]&&typeof v[k]==='object')stack.push([v[k],d+1]);}for(const [id,list] of Object.entries(p.keys))if(Array.isArray(list)&&list.length>20000)throw Error('Track '+String(id).slice(0,40)+' has too many keys to open ('+list.length+')');}"
B_OLD="if(recordUndo)pushUndo();proj=incoming;preview={};sel.clear();stopPlayback();if(bundle.audio){const blob=await(await fetch(bundle.audio)).blob();audioBlob=blob;proj.audio=proj.audio||{id:'take-'+crypto.randomUUID(),offset:0,ms:0};await assetPut(proj.audio.id,blob);await loadTake();}else{audioBlob=null;recordedUrl=null;take=null;}changed();applyPose(playhead);}"
B_NEW="if(recordUndo)pushUndo();/*accept-restores*/const prior={proj,audioBlob,recordedUrl,take};try{proj=incoming;preview={};sel.clear();stopPlayback();if(bundle.audio){const blob=await(await fetch(bundle.audio)).blob();audioBlob=blob;proj.audio=proj.audio||{id:'take-'+crypto.randomUUID(),offset:0,ms:0};await assetPut(proj.audio.id,blob);await loadTake();}else{audioBlob=null;recordedUrl=null;take=null;}changed();applyPose(playhead);}catch(error){proj=prior.proj;audioBlob=prior.audioBlob;recordedUrl=prior.recordedUrl;take=prior.take;preview={};sel.clear();try{changed();applyPose(playhead);}catch{}throw error;}}"
t=sys.argv[1];p=os.path.join(t,'features.js') if os.path.isdir(t) else t
s=open(p,encoding='utf-8').read()
for old,new in((A_OLD,A_NEW),(B_OLD,B_NEW)):
  if new in s:print('already patched');continue
  assert s.count(old)==1,(old[:60],s.count(old));s=s.replace(old,new);print('patched',p)
open(p,'w',encoding='utf-8').write(s)
