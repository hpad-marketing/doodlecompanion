# patch_eye_size.py <app lib folder>: idempotent. In motion-face-profiles.json, every "00 Neutral" face key
# (small eyes) becomes "01 Happy" eyes with a resting mouth, so eye size stays constant inside every motion.
import json, sys, shutil, os
f = os.path.join(sys.argv[1], 'motion-face-profiles.json')
fp = json.load(open(f)); n = 0
for prof in fp['profiles'].values():
    for _, pose in prof.get('poses', []):
        if pose.get('expression') == '00 Neutral':
            pose['expression'] = '01 Happy'
            if not pose.get('mouth'): pose['mouth'] = 1
            n += 1
if n:
    if not os.path.exists(f + '.before-eye-fix'): shutil.copy2(f, f + '.before-eye-fix')
    json.dump(fp, open(f, 'w', newline='\n'), indent=2)
print('face keys changed', n)
