"""Idempotent speed fix for depth masks (depth.js). Output is bit-identical.
mask() samples up to 97x97 points and, for every point, front() rebuilt the same camera ray once per body part
(and the fish-eye cache keyed it with toFixed strings each time). The ray depends only on (x, z), so compute it once
per sample and share it across every subject/occluder part. Array reduce/map in the lens branch are unrolled in
the same evaluation order, so every float is the same.
Run from the source root: python patch_depth_ray_reuse.py src"""
import sys,pathlib
src=pathlib.Path(sys.argv[1] if len(sys.argv)>1 else 'src');p=src/'depth.js';s=p.read_text(encoding='utf-8')
MARK='/*ray-reuse*/'
if MARK in s: print('already patched');sys.exit()
old_front="function front(prep,x,z){if(prep.lens?.active){const ray=Perspective.ray(prep.lens,x,z),o=ray.origin,v=ray.direction;let lo=prep.lens.near,hi=Infinity;if(prep.centre){const q=o.map((n,i)=>n-prep.centre[i]),a=v.reduce((s,n)=>s+n*n,0),b=2*v.reduce((s,n,i)=>s+n*q[i],0),c=q.reduce((s,n)=>s+n*n,0)-prep.part.radius**2,d=b*b-4*a*c;if(d<0)return Infinity;const t=(-b-Math.sqrt(d))/(2*a);return t>=lo?o[1]+t:Infinity;}for(const p of prep.planes){const rest=p.d-p.n.reduce((s,n,i)=>s+n*o[i],0),slope=p.n.reduce((s,n,i)=>s+n*v[i],0);"
new_front=MARK+"function front(prep,x,z,given){if(prep.lens?.active){const ray=given||Perspective.ray(prep.lens,x,z),o=ray.origin,v=ray.direction;let lo=prep.lens.near,hi=Infinity;if(prep.centre){const C=prep.centre,q0=o[0]-C[0],q1=o[1]-C[1],q2=o[2]-C[2],a=0+v[0]*v[0]+v[1]*v[1]+v[2]*v[2],b=2*(0+v[0]*q0+v[1]*q1+v[2]*q2),c=0+q0*q0+q1*q1+q2*q2-prep.part.radius**2,d=b*b-4*a*c;if(d<0)return Infinity;const t=(-b-Math.sqrt(d))/(2*a);return t>=lo?o[1]+t:Infinity;}for(const p of prep.planes){const n=p.n,rest=p.d-(0+n[0]*o[0]+n[1]*o[1]+n[2]*o[2]),slope=0+n[0]*v[0]+n[1]*v[1]+n[2]*v[2];"
old_gs="function groupSample(list,x,z){let distance=-Infinity,depth=Infinity;for(const part of list){const d=signedDistance(part,x,z);distance=Math.max(distance,d);if(d>=-.000001)depth=Math.min(depth,front(part,x,z));}return {distance,depth};}"
new_gs="function groupSample(list,x,z,ray){let distance=-Infinity,depth=Infinity;for(const part of list){const d=signedDistance(part,x,z);distance=Math.max(distance,d);if(d>=-.000001)depth=Math.min(depth,front(part,x,z,ray));}return {distance,depth};}"
old_loop="for(let j=0;j<=nz;j++)for(let i=0;i<=nx;i++){const x=minX+i*dx,z=minZ+j*dz,s=groupSample(subject,x,z),o=groupSample(occluder,x,z);"
new_loop="const lens=subject[0].lens,shared=lens?.active&&subject.every(p=>p.lens===lens)&&occluder.every(p=>p.lens===lens);for(let j=0;j<=nz;j++)for(let i=0;i<=nx;i++){const x=minX+i*dx,z=minZ+j*dz,ray=shared?Perspective.ray(lens,x,z):undefined,s=groupSample(subject,x,z,ray),o=groupSample(occluder,x,z,ray);"
for a,b in [(old_front,new_front),(old_gs,new_gs),(old_loop,new_loop)]:
    if s.count(a)!=1: sys.exit('pattern not found in depth.js: '+a[:60])
    s=s.replace(a,b)
p.write_text(s,encoding='utf-8');print('patched')
