"""Action pads left the Animate tab row in the UX pass, and the release notes say they
still open from the menus, but nothing opened them: no menu item, no Find entry, and
Studio.openMenu('action-pads') did nothing. This adds Animate > Action pads... to the
menu bar, a 'tool:action-pads' Find entry, and lets openMenu reach the parked panel.
Usage: python patch_action_pads_entry.py <src folder or built HTML>."""
import sys,os
MARK='/*action-pads-entry*/'
def edits():
    return [
     ("contextual-workspaces.js",
      "function open(id){if(id==='animation-tools'){",
      "function open(id){"+MARK+"if(id==='action-pads'&&local['action-pads'])return show('animate','action-pads',{manual:true});if(id==='animation-tools'){"),
     ("contextual-workspaces.js",
      "d.heading.textContent=groups[workspace].find(x=>x[0]===id)?.[1]||N.tools[id]?.title||id;",
      "d.heading.textContent=groups[workspace].find(x=>x[0]===id)?.[1]||N.tools[id]?.title||(id==='action-pads'?'Action pads':id);"),
     ("commands.js",
      "clips:['Clips, Blank keys and SVG effects','noise build easing blank vector import']};",
      "clips:['Clips, Blank keys and SVG effects','noise build easing blank vector import'],'action-pads':['Action pads','quick motion pads gestures tap perform']};"+MARK),
     ("commands.js",
      "takes:['animate'],perform:['animate']};",
      "takes:['animate'],perform:['animate'],'action-pads':['animate']};"),
     ("keymap-menu.js",
      "  ['anim:takes','animate','My motions…',[],'any',cmd('tool:takes')],",
      "  ['anim:takes','animate','My motions…',[],'any',cmd('tool:takes')],\n  ['anim:pads','animate','Action pads…',[],'any',cmd('tool:action-pads')],"+MARK.replace('/*','//').replace('*/','')),
    ]
target=sys.argv[1]
if os.path.isdir(target):
    for f,a,b in edits():
        p=os.path.join(target,f);s=open(p,encoding='utf-8').read()
        if b in s:continue
        assert s.count(a)==1,(f,a[:60]);open(p,'w',encoding='utf-8').write(s.replace(a,b))
    print('patched folder',target)
else:
    s=open(target,encoding='utf-8').read()
    for f,a,b in edits():
        if b in s:continue
        assert s.count(a)==1,(f,a[:60],s.count(a));s=s.replace(a,b)
    open(target,'w',encoding='utf-8').write(s);print('patched',target)
