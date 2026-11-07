"""Gamepad reading on Windows with nothing to install (shared with the droid kit).

Xbox pads through XInput; DualSense / DualShock and other HID pads through the
Windows joystick API (winmm). read_pad() returns None when no pad is connected
or on other systems, so callers fall back to the keyboard.

Buttons use one layout: on a DualSense Cross = A, Circle = B, Square = X,
Triangle = Y, L1 = LB, R1 = RB, Options = START, Create = BACK.
"""
import ctypes
import sys as _sys
from mathutils import Vector

_XI = {'dll': None, 'tried': False}

class _XPad(ctypes.Structure):
    _fields_ = [('wButtons', ctypes.c_ushort), ('bLeftTrigger', ctypes.c_ubyte), ('bRightTrigger', ctypes.c_ubyte),
                ('sThumbLX', ctypes.c_short), ('sThumbLY', ctypes.c_short), ('sThumbRX', ctypes.c_short), ('sThumbRY', ctypes.c_short)]

class _XState(ctypes.Structure):
    _fields_ = [('dwPacketNumber', ctypes.c_uint), ('Gamepad', _XPad)]

XB = dict(UP=0x1, DOWN=0x2, LEFT=0x4, RIGHT=0x8, START=0x10, BACK=0x20, L3=0x40, R3=0x80, LB=0x100, RB=0x200,
          A=0x1000, B=0x2000, X=0x4000, Y=0x8000, PS=0x10000, PAD=0x20000)

# ---- DualSense / DualShock / other HID pads through the Windows joystick API (winmm), no driver or install
class _JoyInfoEx(ctypes.Structure):
    _fields_ = [(n, ctypes.c_uint32) for n in ('dwSize', 'dwFlags', 'dwXpos', 'dwYpos', 'dwZpos', 'dwRpos', 'dwUpos',
                                              'dwVpos', 'dwButtons', 'dwButtonNumber', 'dwPOV', 'dwReserved1', 'dwReserved2')]

_JOY = {'dll': None, 'tried': False, 'id': None, 'next_scan': 0.0, 'map': None, 'name': ''}
SONY_PIDS = {0x0CE6: 'DualSense', 0x0DF2: 'DualSense Edge', 0x05C4: 'DualShock 4', 0x09CC: 'DualShock 4'}
# DirectInput button order on Sony pads -> the shared layout (Cross = A, Circle = B, Square = X, Triangle = Y)
SONY_BTN = {0: 'X', 1: 'A', 2: 'B', 3: 'Y', 4: 'LB', 5: 'RB', 8: 'BACK', 9: 'START', 10: 'L3', 11: 'R3', 12: 'PS', 13: 'PAD'}
GENERIC_BTN = {0: 'A', 1: 'B', 2: 'X', 3: 'Y', 4: 'LB', 5: 'RB', 6: 'BACK', 7: 'START', 8: 'L3', 9: 'R3'}


def _joy_name(dll, jid):
    buf = ctypes.create_string_buffer(1024)
    if dll.joyGetDevCapsW(jid, buf, 728) != 0: return 0, 0, ''
    mid, pid = int.from_bytes(buf.raw[0:2], 'little'), int.from_bytes(buf.raw[2:4], 'little')
    name = buf.raw[4:68].decode('utf-16-le', 'ignore').split('\x00')[0]
    return mid, pid, name


def read_joy():
    import time as _t
    if not _JOY['tried']:
        _JOY['tried'] = True
        if _sys.platform == 'win32':
            try: _JOY['dll'] = ctypes.windll.winmm
            except OSError: pass
    dll = _JOY['dll']
    if not dll: return None
    ji = _JoyInfoEx(); ji.dwSize = ctypes.sizeof(_JoyInfoEx); ji.dwFlags = 0xFF
    if _JOY['id'] is None:
        if _t.time() < _JOY['next_scan']: return None
        _JOY['next_scan'] = _t.time() + 2.0
        for jid in range(16):
            if dll.joyGetPosEx(jid, ctypes.byref(ji)) == 0:
                mid, pid, name = _joy_name(dll, jid)
                _JOY.update(id=jid, sony=(mid == 0x054C or pid in SONY_PIDS), name=SONY_PIDS.get(pid, name or 'Gamepad'))
                # triggers rest at the bottom of their range, sticks rest in the middle: tell them apart once
                rest = {'Z': ji.dwZpos, 'R': ji.dwRpos, 'U': ji.dwUpos, 'V': ji.dwVpos}
                trig = [k for k in 'ZRUV' if rest[k] < 6000]
                stick = [k for k in 'ZRUV' if k not in trig]
                _JOY['map'] = dict(rx=stick[0] if stick else 'Z', ry=stick[1] if len(stick) > 1 else 'R',
                                   lt=trig[0] if trig else 'U', rt=trig[1] if len(trig) > 1 else 'V')
                break
        else:
            return None
    if dll.joyGetPosEx(_JOY['id'], ctypes.byref(ji)) != 0:
        _JOY['id'] = None; return None
    ax = {'X': ji.dwXpos, 'Y': ji.dwYpos, 'Z': ji.dwZpos, 'R': ji.dwRpos, 'U': ji.dwUpos, 'V': ji.dwVpos}
    def c(v): return (v - 32767.5) / 32767.5
    def stick(a, b):
        v = Vector((a, b)); m = v.length
        if m < 0.15: return 0.0, 0.0
        v = v * (min(1.0, (m - 0.15) / 0.85) / m); return v.x, v.y
    M = _JOY['map']
    lx, ly = stick(c(ax['X']), -c(ax['Y'])); rx, ry = stick(c(ax[M['rx']]), -c(ax[M['ry']]))
    bmap = SONY_BTN if _JOY['sony'] else GENERIC_BTN
    b = 0
    for bit, name in bmap.items():
        if ji.dwButtons & (1 << bit): b |= XB[name]
    pov = ji.dwPOV
    if pov != 0xFFFF and pov <= 36000:
        d = pov / 100.0
        if d >= 315 or d <= 45: b |= XB['UP']
        if 45 <= d <= 135: b |= XB['RIGHT']
        if 135 <= d <= 225: b |= XB['DOWN']
        if 225 <= d <= 315: b |= XB['LEFT']
    return dict(lx=lx, ly=ly, rx=rx, ry=ry, lt=ax[M['lt']] / 65535, rt=ax[M['rt']] / 65535, b=b, pad=_JOY['id'],
                name=_JOY['name'], sony=_JOY['sony'])


def read_pad():
    if not _XI['tried']:
        _XI['tried'] = True
        if _sys.platform == 'win32':
            for n in ('xinput1_4', 'xinput1_3', 'xinput9_1_0'):
                try: _XI['dll'] = ctypes.windll.LoadLibrary(n); break
                except OSError: pass
    x = _XI['dll']
    if not x: return read_joy()
    for i in range(4):
        st = _XState()
        if x.XInputGetState(i, ctypes.byref(st)) == 0:
            g = st.Gamepad
            def stick(a, b):
                v = Vector((a / 32767, b / 32767)); m = v.length
                if m < 0.22: return 0.0, 0.0
                v = v * (min(1.0, (m - 0.22) / 0.78) / m); return v.x, v.y
            lx, ly = stick(g.sThumbLX, g.sThumbLY); rx, ry = stick(g.sThumbRX, g.sThumbRY)
            return dict(lx=lx, ly=ly, rx=rx, ry=ry, lt=g.bLeftTrigger / 255, rt=g.bRightTrigger / 255, b=g.wButtons, pad=i,
                        name='Xbox controller', sony=False)
    return read_joy()

