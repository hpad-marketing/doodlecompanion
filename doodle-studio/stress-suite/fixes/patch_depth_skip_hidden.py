"""Idempotent speed fix for depth masks (depth.js), applied after patch_depth_ray_reuse.py. Output is bit-identical.
A grid point's depth term only matters when BOTH the subject and the occluder cover it (each group's signed distance
>= -1e-6); otherwise groupSample already yields depth=Infinity and the term is -1. So compute the cheap distances
first and only build the camera ray and run front() where both groups cover the point.
Run from the source root: python patch_depth_skip_hidden.py src"""
import sys,pathlib
src=pathlib.Path(sys.argv[1] if len(sys.argv)>1 else 'src');p=src/'depth.js';s=p.read_text(encoding='utf-8')
MARK='/*skip-hidden*/'
if MARK in s: print('already patched');sys.exit()
old="for(let j=0;j<=nz;j++)for(let i=0;i<=nx;i++){const x=minX+i*dx,z=minZ+j*dz,ray=shared?Perspective.ray(lens,x,z):undefined,s=groupSample(subject,x,z,ray),o=groupSample(occluder,x,z,ray);values.push(Math.min(s.distance,o.distance,Number.isFinite(s.depth)&&Number.isFinite(o.depth)?o.depth-s.depth-margin:-1));}"
new=MARK+"const reach=(list,x,z)=>{let d=-Infinity;for(const part of list)d=Math.max(d,signedDistance(part,x,z));return d;};for(let j=0;j<=nz;j++)for(let i=0;i<=nx;i++){const x=minX+i*dx,z=minZ+j*dz,sd=reach(subject,x,z),od=reach(occluder,x,z);if(sd<-.000001||od<-.000001){values.push(Math.min(sd,od,-1));continue;}const ray=shared?Perspective.ray(lens,x,z):undefined,s=groupSample(subject,x,z,ray),o=groupSample(occluder,x,z,ray);values.push(Math.min(s.distance,o.distance,Number.isFinite(s.depth)&&Number.isFinite(o.depth)?o.depth-s.depth-margin:-1));}"
if s.count(old)!=1: sys.exit('pattern not found in depth.js (apply patch_depth_ray_reuse.py first)')
p.write_text(s.replace(old,new),encoding='utf-8');print('patched')
