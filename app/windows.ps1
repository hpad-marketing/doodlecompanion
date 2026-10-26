# Lists the visible app windows, top-most first, so Bunny can grab their top edges and sit on them.
# One JSON line every 400 ms: [[id,left,top,right,bottom],...] in physical pixels. Skips minimised, cloaked,
# tool and untitled windows, the desktop and the taskbar, and Bunny's own windows (process id in $args[0]).
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
  [DllImport("user32.dll")] static extern int GetWindowTextLength(IntPtr h);
  [DllImport("user32.dll")] public static extern IntPtr SetThreadDpiAwarenessContext(IntPtr c);
  [StructLayout(LayoutKind.Sequential)] public struct RECT{public int L,T,R,B;}
  [DllImport("dwmapi.dll")] static extern int DwmGetWindowAttribute(IntPtr h,int a,out RECT r,int s);
  [DllImport("dwmapi.dll")] static extern int DwmGetWindowAttribute(IntPtr h,int a,out int v,int s);
  public static string List(uint self){
    var sb=new StringBuilder("[");bool first=true;
    EnumWindows(delegate(IntPtr h,IntPtr l){
      if(!IsWindowVisible(h)||IsIconic(h))return true;
      if((GetWindowLong(h,-20)&0x80)!=0)return true;
      uint pid;GetWindowThreadProcessId(h,out pid);if(pid==self)return true;
      int cloaked;if(DwmGetWindowAttribute(h,14,out cloaked,4)==0&&cloaked!=0)return true;
      var c=new StringBuilder(64);GetClassName(h,c,64);var cn=c.ToString();
      if(cn=="Progman"||cn=="WorkerW"||cn=="Shell_TrayWnd"||cn=="Shell_SecondaryTrayWnd")return true;
      if(GetWindowTextLength(h)==0)return true;
      RECT r;if(DwmGetWindowAttribute(h,9,out r,16)!=0)return true;
      if(r.R-r.L<160||r.B-r.T<100||r.L<=-30000||r.T<=-30000)return true;
      sb.Append(first?"":",").Append("[").Append(h.ToInt64()).Append(",").Append(r.L).Append(",").Append(r.T).Append(",").Append(r.R).Append(",").Append(r.B).Append("]");first=false;
      return true;},IntPtr.Zero);
    return sb.Append("]").ToString();}
}
"@
[void][BunnyWins]::SetThreadDpiAwarenessContext([IntPtr](-4))
$self=[uint32]$args[0]
while($true){[Console]::Out.WriteLine([BunnyWins]::List($self));[Console]::Out.Flush();Start-Sleep -Milliseconds 500}
