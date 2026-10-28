"""Opening Doodle Studio.exe a second time started a second host and a second window. PrepareWindowStartup
treated a live host for the same data folder as "taken" and moved the new launch into a fresh
window-sessions\\<time-guid> folder (its own storage, port and Electron profile, which is also why the
window's single-instance lock never fired). A normal launch that finds a live host for the same data
folder and the same editor build now focuses that host's window, or opens the one window for it, and
exits 0 without a second listener. A different running version still gets its own session folder as
before, and Tray > New window (--new-window) still opens an independent window.
Usage: python patch_relaunch_reuses_host.py <windows source folder or Bunny.cs>."""
import sys,os
MARK='/*relaunch-reuses-host*/'
OLD=("                bool existing=false;\n"
"                try{existing=ExistingStudio(rememberedPort);}catch(OpenVersionException){if(service)throw;existing=true;}\n"
"                if(!existing)return false;\n"
"                if(service)return true;\n")
NEW=("                bool existing=false,otherVersion=false;\n"
"                try{existing=ExistingStudio(rememberedPort);}catch(OpenVersionException){if(service)throw;existing=true;otherVersion=true;}\n"
"                if(!existing)return false;\n"
"                if(service)return true;\n"
"                "+MARK+"if(!otherVersion){OpenEditor();return true;}\n")
t=sys.argv[1];p=os.path.join(t,'Bunny.cs') if os.path.isdir(t) else t
s=open(p,encoding='utf-8').read()
if MARK in s:print('already patched');sys.exit()
n=s.replace('\r\n','\n').count(OLD)
assert n==1,('anchor count',n)
crlf='\r\n' in s
s=s.replace('\r\n','\n').replace(OLD,NEW)
if crlf:s=s.replace('\n','\r\n')
open(p,'w',encoding='utf-8',newline='').write(s);print('patched',p)
