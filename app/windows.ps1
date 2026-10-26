# Tells Bunny what's on screen, one JSON line every 500 ms, in physical pixels:
#   {"w":[[id,left,top,right,bottom,"title","process"],...],"fg":{"t":"window title","p":"process name"},"pip":[id,left,top,right,bottom] or null}
# w lists the visible app windows, top-most first, so he can grab their top edges and sit on them. It skips minimised,
# cloaked, tool and untitled windows, the desktop, the taskbar, picture-in-picture players and Bunny's own windows
# (process id in $args[0]). fg is the window you're working in, so he can react to it. pip is a picture-in-picture video.
# Bunny can ask for a window to be moved (to carry a picture-in-picture video): main writes "move <id> <x> <y>" to the
# file in $args[1], checked every 120 ms. Nothing leaves this computer.
Add-Type @"
using System;using System.Text;using System.Runtime.InteropServices;
public static class BunnyWins{
  public delegate bool EnumProc(IntPtr h,IntPtr l);
  [DllImport("user32.dll")] static extern bool EnumWindows(EnumProc f,IntPtr l);
  [DllImport("user32.dll")] static extern bool IsWindowVisible(IntPtr h);
  [DllImport("user32.dll")] static extern bool IsIconic(IntPtr h);
  [DllImport("user32.dll")] static extern int GetWindowLong(IntPtr h,int i);
  [DllImport("user32.dll")] static extern uint GetWindowThreadProcessId(IntPtr h,out uint p);
  [DllImport("user32.dll",CharSet=CharSet.Unicode)] static extern int GetClassName(IntPtr h,StringBuilder s,int n);
  [DllImport("user32.dll",CharSet=CharSet.Unicode)] static extern int GetWindowText(IntPtr h,StringBuilder s,int n);
  [DllImport("user32.dll")] static extern int GetWindowTextLength(IntPtr h);
  [DllImport("user32.dll")] static extern IntPtr GetForegroundWindow();
  [DllImport("user32.dll")] static extern bool SetWindowPos(IntPtr h,IntPtr after,int x,int y,int cx,int cy,uint f);
  [DllImport("user32.dll")] static extern bool GetWindowRect(IntPtr h,out RECT r);
  [DllImport("user32.dll")] public static extern IntPtr SetThreadDpiAwarenessContext(IntPtr c);
  [StructLayout(LayoutKind.Sequential)] public struct RECT{public int L,T,R,B;}
  [DllImport("dwmapi.dll")] static extern int DwmGetWindowAttribute(IntPtr h,int a,out RECT r,int s);
  [DllImport("dwmapi.dll")] static extern int DwmGetWindowAttribute(IntPtr h,int a,out int v,int s);
  static string Title(IntPtr h){var t=new StringBuilder(256);GetWindowText(h,t,256);return t.ToString();}
  static string Esc(string s){var b=new StringBuilder();foreach(char c in s){if(c=='"'||c=='\\')b.Append('\\').Append(c);else if(c<32)b.Append(' ');else b.Append(c);}return b.ToString();}
  static bool IsPip(string t){t=t.ToLowerInvariant();return t.Contains("picture in picture")||t.Contains("picture-in-picture");}
  static string Rect(IntPtr h,RECT r){return "["+h.ToInt64()+","+r.L+","+r.T+","+r.R+","+r.B+"]";}
  // process names are cached by process id, so naming every window twice a second stays cheap
  static System.Collections.Generic.Dictionary<uint,string> procs=new System.Collections.Generic.Dictionary<uint,string>();
  static string Proc(uint pid){string n;if(procs.TryGetValue(pid,out n))return n;try{n=System.Diagnostics.Process.GetProcessById((int)pid).ProcessName;}catch{n="";}if(procs.Count>300)procs.Clear();procs[pid]=n;return n;}
  // a picture-in-picture video is moved by its window rect, which can sit a few pixels outside its visible frame
  public static void Move(long id,int x,int y){var h=new IntPtr(id);RECT vis,win;
    if(DwmGetWindowAttribute(h,9,out vis,16)!=0||!GetWindowRect(h,out win))return;
    SetWindowPos(h,IntPtr.Zero,x-(vis.L-win.L),y-(vis.T-win.T),0,0,0x0001|0x0004|0x0010);}
  public static string List(uint self){
    var sb=new StringBuilder("{\"w\":[");bool first=true;string pip="null";
    EnumWindows(delegate(IntPtr h,IntPtr l){
      if(!IsWindowVisible(h)||IsIconic(h))return true;
      uint pid;GetWindowThreadProcessId(h,out pid);if(pid==self)return true;
      int cloaked;if(DwmGetWindowAttribute(h,14,out cloaked,4)==0&&cloaked!=0)return true;
      if(GetWindowTextLength(h)==0)return true;
      RECT r;if(DwmGetWindowAttribute(h,9,out r,16)!=0)return true;
      if(r.L<=-30000||r.T<=-30000)return true;
      if(IsPip(Title(h))){if(pip=="null")pip=Rect(h,r);return true;}
      if((GetWindowLong(h,-20)&0x80)!=0)return true;
      var c=new StringBuilder(64);GetClassName(h,c,64);var cn=c.ToString();
      if(cn=="Progman"||cn=="WorkerW"||cn=="Shell_TrayWnd"||cn=="Shell_SecondaryTrayWnd")return true;
      if(r.R-r.L<160||r.B-r.T<100)return true;
      var t=Title(h);if(t.Length>120)t=t.Substring(0,120);
      sb.Append(first?"":",").Append("["+h.ToInt64()+","+r.L+","+r.T+","+r.R+","+r.B+",\""+Esc(t)+"\",\""+Esc(Proc(pid))+"\"]");first=false;
      return true;},IntPtr.Zero);
    string ft="",fp="";var fg=GetForegroundWindow();
    if(fg!=IntPtr.Zero){ft=Title(fg);uint fpid;GetWindowThreadProcessId(fg,out fpid);
      if(fpid!=self)fp=Proc(fpid);else ft="";}
    return sb.Append("],\"fg\":{\"t\":\"").Append(Esc(ft)).Append("\",\"p\":\"").Append(Esc(fp)).Append("\"},\"pip\":").Append(pip).Append("}").ToString();}
}
"@
[void][BunnyWins]::SetThreadDpiAwarenessContext([IntPtr](-4))
$self=[uint32]$args[0];$cmd=$args[1];$n=0
while($true){
  if($cmd -and (Test-Path -LiteralPath $cmd)){
    try{$lines=Get-Content -LiteralPath $cmd;Remove-Item -LiteralPath $cmd -Force
      foreach($l in $lines){$p=$l -split ' ';if($p[0] -eq 'move' -and $p.Count -ge 4){[BunnyWins]::Move([int64]$p[1],[int]$p[2],[int]$p[3])}}}catch{}}
  if($n%4 -eq 0){[Console]::Out.WriteLine([BunnyWins]::List($self));[Console]::Out.Flush()}
  $n++;Start-Sleep -Milliseconds 120}
