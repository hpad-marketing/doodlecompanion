"""Bambi 3D: build the per-frame shot.json for ds_bridge (30 fps, 9:16)."""
import json, math, numpy as np, os
HERE=os.path.dirname(os.path.abspath(__file__))
FPS=30; N=528; DUR=N/FPS
B0=0.2728; BEAT=60/137.1; BAR=4*BEAT
bar=lambda k: B0+(k-1)*BAR          # start time of bar k (1-based)
_LIB=[q for q in ('/mnt/user-data/uploads/Documents/Talking Character App/blender-library/motions/performance.json',
                   os.path.expanduser('~/Documents/Talking Character App/blender-library/motions/performance.json'),
                   r'C:\Users\Sushant\Documents\Talking Character App\blender-library\motions\performance.json') if os.path.exists(q)][0]
M=json.load(open(_LIB))['motions']
FACE_KEYS={'expression','mouth','gaze','blink','camFov','camZoom','view'}

def clip_frames(name):
    m=M[name]; P=m['poses']; lin=set(m.get('linearTracks',[]))
    tracks=sorted({t for _,p in P for t in p}-FACE_KEYS)
    out=[]
    for f in range(m['frames']):
        row={}
        for t in tracks:
            ks=[(fr,p[t]) for fr,p in P if t in p]
            if f<=ks[0][0]: row[t]=ks[0][1]; continue
            if f>=ks[-1][0]: row[t]=ks[-1][1]; continue
            for (a,va),(b,vb) in zip(ks,ks[1:]):
                if a<=f<=b:
                    u=(f-a)/(b-a); u=u if t in lin else u*u*(3-2*u); row[t]=va+(vb-va)*u; break
        out.append(row)
    return out
CL={}
def sample(name,ct):
    if name not in CL: CL[name]=clip_frames(name)
    fr=CL[name]; i=min(max(ct,0),len(fr)-1); i0=int(i); i1=min(i0+1,len(fr)-1); u=i-i0
    return {k:fr[i0].get(k,0)*(1-u)+fr[i1].get(k,0)*u for k in fr[i0]}

# (clip, start time, start frame inside clip, end time) ; end overlaps next start for crossfade
SEQ=[('perf-rap-l-hand',      0.00,-6, 2.10),
     ('perf-rap-two-step',    2.02, 0, 3.90),
     ('perf-rap-hand-chop-r', 3.77, 0, 4.35),
     ('perf-rap-lean-back',   4.15, 0, 5.60),
     ('perf-rap-chest-tap',   5.52, 0, 7.40),
     ('stage-high-top-down-count',7.30,0,9.10),
     ('perf-rap-shrug',       8.96, 0, 10.10),
     ('HOLD',                 10.00,0,10.90),
     ('perf-rap-walk-up',     10.78,0,11.85),
     ('perf-rap-point-to-lens',11.75,26,12.75),
     ('perf-rap-woah',        12.62,0,13.50),
     ('perf-rap-lean-in',     13.40,0,14.40),
     ('perf-rap-two-step',    14.28,0,16.10),
     ('perf-rap-adlib-side-eye',16.03,0,DUR)]
XF=0.2  # crossfade seconds
def body_at(t):
    w=[]; 
    for i,(name,s,f0,e) in enumerate(SEQ):
        if s-1e-9<=t<=e+1e-9:
            if name=='HOLD': v=body_at(s-1/FPS)
            else: v=sample(name,f0+(t-s)*FPS)
            fin=min(1,(t-s)/XF) if i>0 else 1
            w.append((fin,v))
    if not w: return {}
    acc={}; tot=0
    for k,(wt,v) in enumerate(w):
        wt=wt if k==len(w)-1 else 1  # newest fades in over older
        for kk,vv in v.items():
            acc[kk]=acc.get(kk,vv)*(1-wt)+vv*wt if kk in acc else vv
    return acc

# faces: (start time, expression id)
# v002/v003: 61, 65 and 60 read heavy-lidded and 23 is unchecked, so only faces confirmed open-eyed in the v001 stills
FACES=[(0,12),(1.3,2),(2.0,23),(3.0,15),(3.77,2),(4.65,23),(5.52,12),(6.3,15),(7.28,20),(8.0,2),
       (9.03,23),(10.0,15),(10.78,20),(12.1,2),(12.53,23),(13.4,15),(14.0,2),(14.35,12),(16.0,23)]
def face_at(t): return [e for s,e in FACES if s<=t][-1]
BLINKS=[0.9,3.4,6.9,9.6,11.3,15.2,16.9]   # avoid cuts and faces with closed eyes
def blink_at(t):
    for b in BLINKS:
        k=int(round((t-b)*FPS))
        if 0<=k<5: return [1,3,3,2,1][k]
    return 0

# lip sync from the song: vocal-band envelope + centroid, 2-frame steps, closed outside the rap
env=np.load(os.path.join(HERE,'venv.npy')); cen=np.load(os.path.join(HERE,'cent.npy'))
VON,VOFF=0.35,14.35
lo,hi=np.percentile(env[int(VON*FPS):int(VOFF*FPS)],[20,90]); lvl=np.clip((env-lo)/(hi-lo),0,1)
mouths=[]; prev=1
for i in range(0,N,2):
    t=i/FPS
    if not(VON<=t<VOFF): m=1
    else:
        l=lvl[i]; c=cen[i]; d=lvl[i]-lvl[max(i-2,0)]
        if l<0.18: m=7 if prev!=7 else 1          # MBP / rest on dips
        elif l>0.7: m=2 if c>1500 else 4           # AI wide, O round
        elif l>0.45: m=3 if c>1700 else (10 if c>1300 else 5)   # E / etc / U
        else: m=9 if d>0 else 8 if c>2200 else 6   # L / FV / WQ
        if m==prev and l>0.18: m={2:3,3:10,10:9,4:5,5:6,9:3,8:9,6:5}.get(m,m)
    mouths+=[m,m]; prev=m
mouths=mouths[:N]

# camera: shots of keyed states, smoothstep between keys inside a shot, cuts between shots
FACE_Z=0.49
def cam_state(yaw=0,pitch=2,H=1.9,lens=35,roll=0,band=0.44,shake=0,tx=0,ty=0):
    return dict(yaw=yaw,pitch=pitch,H=H,lens=lens,roll=roll,band=band,shake=shake,tx=tx,ty=ty)
SHOTS=[  # (start, [(t, state)...])
 (0.00,[(0.0,cam_state(H=3.2,lens=24,pitch=6,yaw=-18)),(1.45,cam_state(H=1.65)),(1.62,cam_state(H=1.7,pitch=16,lens=30)),(2.05,cam_state(H=1.7,pitch=16,lens=30)),
        (2.45,cam_state(H=1.6,pitch=3)),(3.25,cam_state(yaw=-28,H=1.6,pitch=4)),(3.42,cam_state(yaw=-30,H=1.35,pitch=4,band=0.47)),(4.649,cam_state(yaw=-33,H=1.4,pitch=4,band=0.46))]),
 (4.649,[(4.649,cam_state(yaw=8,pitch=1,H=1.75,lens=22,band=0.43)),(5.524,cam_state(yaw=12,pitch=1,H=1.65,lens=22,band=0.43))]),
 (5.524,[(5.524,cam_state(H=1.5,lens=24)),(6.40,cam_state(H=1.5,lens=50)),(6.60,cam_state(H=1.32,lens=50,band=0.46)),(6.85,cam_state(H=1.5,lens=50)),(7.275,cam_state(H=1.5,lens=50))]),
 (7.275,[(7.275,cam_state(pitch=16,H=2.0,lens=26,band=0.42)),(8.85,cam_state(pitch=17,H=1.95,lens=26,roll=6,band=0.42)),(9.025,cam_state(yaw=55,pitch=16,H=1.95,lens=26,roll=6,band=0.42))]),
 (9.025,[(9.025,cam_state(yaw=-60,pitch=18,H=1.6,lens=28,roll=10)),(9.20,cam_state(yaw=-12,pitch=18,H=1.6,lens=28,roll=10)),(10.0,cam_state(yaw=-12,pitch=18,H=1.55,lens=28,roll=10)),(10.62,cam_state(yaw=-12,pitch=18,H=1.4,lens=28,roll=10,band=0.46)),(10.776,cam_state(yaw=40,pitch=12,H=1.4,lens=28,roll=6,band=0.46))]),
 (10.776,[(10.776,cam_state(yaw=-45,pitch=3,H=2.8,lens=24)),(10.95,cam_state(yaw=-10,pitch=3,H=2.7,lens=24)),(11.85,cam_state(yaw=0,pitch=3,H=1.9,lens=35)),
          (12.05,cam_state(yaw=6,pitch=-8,H=1.75,lens=20,band=0.42)),(12.526,cam_state(yaw=8,pitch=-9,H=1.7,lens=20,band=0.42))]),
 (12.526,[(12.526,cam_state(pitch=-8,H=1.8,lens=16,shake=1,band=0.45)),(12.85,cam_state(pitch=-8,H=1.8,lens=16,shake=1,band=0.45)),(13.0,cam_state(pitch=-8,H=1.6,lens=16,shake=1,band=0.46)),
          (13.6,cam_state(pitch=-8,H=1.8,lens=16,shake=1,band=0.44)),(14.28,cam_state(pitch=-8,H=1.8,lens=16,shake=1,band=0.44)),
          (15.2,cam_state(yaw=10,pitch=-2,H=1.85,lens=28,band=0.44)),(17.58,cam_state(yaw=22,pitch=-2,H=1.85,lens=28,band=0.44))]),
]
CUTS=[s for s,_ in SHOTS[1:]]
ss=lambda u:u*u*(3-2*u)
def cam_at(t):
    keys=[k for s,k in SHOTS if s<=t+1e-9][-1]
    if t<=keys[0][0]: st=keys[0][1]
    elif t>=keys[-1][0]: st=keys[-1][1]
    else:
        for (a,A),(b,Bk) in zip(keys,keys[1:]):
            if a<=t<=b:
                u=(t-a)/(b-a)
                # whip-out / whip-in segments are short: ease-in only (out) or ease-out only (in)
                u=u*u if b-a<0.2 and b in CUTS else (1-(1-u)**2 if b-a<0.2 and a in CUTS else ss(u))
                st={k:A[k]+(Bk[k]-A[k])*u for k in A}; break
    tan=18/st['lens']; dist=(st['H']/2)/tan
    tz=FACE_Z-(0.5-st['band'])*st['H']*math.cos(math.radians(st['pitch']))
    return dict(yaw=st['yaw'],pitch=st['pitch'],dist=round(dist,4),lens=round(st['lens'],3),roll=st['roll'],tz=round(tz,4),
                tx=st['tx'],ty=st['ty'],shake=int(st['shake']>0.5),props=0)

frames=[]; last_depth=0.0
for i in range(N):
    t=i/FPS; v=body_at(t); c=cam_at(t)
    if 'depth' in v: last_depth=v['depth']
    else: v['depth']=last_depth
    c['ty']=last_depth*0.125
    # keep Bunny playing to the lens: part of the camera yaw goes to body turn and head
    # in the top-down shot Bunny looks up into the lens (negative nod = look up)
    if 7.275<=t<9.025: v['headNod']=max(-14,v.get('headNod',0)-10)
    # v002: lean-back nod under a low camera folded the ears out of view (bear-ear look); cap the look-up
    if c['pitch']<0: v['headNod']=max(-3,v.get('headNod',0)); v['torsoBow']=max(-5,v.get('torsoBow',0))
    v['turn']=v.get('turn',0)+0.35*c['yaw']; v['headYaw']=v.get('headYaw',0)+0.3*c['yaw']
    # v001 check: small eased lift around the woah rise (kept so the script matches the rendered JSON)
    lift=max(0.0,1-abs(i-399.5)/9.0); v['bodyY']=v.get('bodyY',0)-1.0*lift*lift*(3-2*lift)
    # v002 check: the woah side lean (bodyTilt 7) pivots one stub foot 1.3-1.7 mm under the floor; 4.5 keeps both feet on it
    # v003 stills: a 17 deg forward bow put the hands behind the head in the 16 mm shot
    v['torsoBow']=min(10,v.get('torsoBow',0))
    if 'bodyTilt' in v: v['bodyTilt']=max(-4.5,min(4.5,v['bodyTilt']))
    v.update(expression=face_at(t),gaze=0,mouth=mouths[i],blink=blink_at(t),cam=c)
    frames.append(v)
# round 2 (user, 2026-10-30): plain hoodie (no outfit); set and props from the 3D Doodle Library through the
# app's stage (rap studio set, its stand mic swapped for a handheld mic in Bunny's right hand)
shot={'fps':FPS,'width':1080,'height':1920,'frames':frames,'cuts':CUTS,'settings':{'boil_step':3}}
json.dump(shot,open(os.path.join(HERE,'bambi_shot.json'),'w'))
ch=sum(mouths[i]!=mouths[i-1] for i in range(int(VON*FPS)+1,int(VOFF*FPS)))/(int(VOFF*FPS)-int(VON*FPS))
print('frames',N,'cuts',CUTS,'mouth change rate per frame',round(ch,3),'per 2f step',round(ch*2,3))
