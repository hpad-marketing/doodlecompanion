"""Write the one-page STATUS.md for a droid folder from its settings + checks.
DROID=<id> python3 status.py <droid_folder> [--version vN --note "what changed"] [--names report.json]"""
import sys, os, json, datetime
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'kit'))
import kit
a = sys.argv[1:]; folder = a[0]
opt = {a[i]: a[i + 1] for i in range(1, len(a) - 1) if a[i].startswith('--')}
S = kit.settings(); H = S.get('hooks', {})
names = json.load(open(opt['--names'])) if '--names' in opt and os.path.exists(opt['--names']) else None
log = os.path.join(folder, 'work', 'versions', 'CHANGES.md')
if '--version' in opt:
    os.makedirs(os.path.dirname(log), exist_ok=True)
    with open(log, 'a') as f: f.write(f"- {datetime.date.today()} {opt['--version']}: {opt.get('--note', '')}\n")
changes = open(log).read().strip().splitlines()[-5:] if os.path.exists(log) else []
L = [f"# {S.get('name', '?')} status", '',
     f"- **Locked:** {'yes' if S.get('locked') else 'no, waiting on the model-lock sheet'}",
     f"- **Current file:** {S.get('current_file', '?')} (old versions in work\\versions)",
     f"- **Kit:** droid-kit {kit.VERSION}, settings droids/{S.get('id')}.json",
     f"- **Rig:** {S.get('rig')}, faces {S.get('facing')}",
     f"- **Names check:** " + ('not run' if names is None else ('pass' if names['pass'] else 'FAIL: ' + '; '.join(names['missing_or_wrong'][:6]))),
     '', '## Hooks for the sitcom add-on',
     f"- LEDs: {', '.join(H.get('leds', [])) or '-'}",
     f"- Glow materials: {', '.join(H.get('glow_materials', [])) or '-'} (node '{H.get('glow_node', 'Glow')}')",
     f"- Eye: {H.get('eye') or '-'}; antenna bones: {', '.join(H.get('antenna_chains', [])) or '-'}",
     '- Controls: ' + ', '.join(f'{k} = {v}' for k, v in H.get('controls', {}).items()),
     '', '## Shared files',
     '- Materials: ..\\_shared\\RB_Materials.blend (shader groups linked)',
     '- Textures: ..\\_shared\\textures (relative paths)',
     '', '## Recent changes'] + (changes or ['- none yet']) + ['', '## Open issues'] + [f'- {x}' for x in S.get('open_issues', [])] + ([] if S.get('open_issues') else ['- none'])
open(os.path.join(folder, 'STATUS.md'), 'w').write('\n'.join(L) + '\n'); print('STATUS ->', os.path.join(folder, 'STATUS.md'))
