"""Writes previews/hero_ship/manifest.json for the sitcom studio's preview pane.

The pane reads this file without importing hero_ship; it only calls
hero_ship.build() and hero_ship.presets.apply() when the user clicks Load.
"""
import json
import os
from . import presets, VERSION, ROOT_NAME


def data(rel="previews/hero_ship"):
    return {
        "name": "Hero Ship",
        "version": ".".join(map(str, VERSION)),
        "root": ROOT_NAME,
        "module": "hero_ship",
        "build": "hero_ship.build(collection=None, wear=1.0, seed=1)",
        "apply": "hero_ship.presets.apply(root, preset_id, frame_start=1, camera=True, build_stage=True)",
        "thumb": f"{rel}/ship/thumb.jpg",
        "stills": [f"{rel}/ship/{n}.jpg" for n in ("three_quarter", "rear", "side", "underside", "nose")],
        "blend": "DeepInDoodles/Ship/HeroShip/HeroShip.blend",
        "presets": [
            {"id": p["id"], "label": p["label"], "frames": p["frames"], "fps": presets.FPS,
             "needs_stage": p["needs_stage"], "about": p["about"],
             "thumb": f"{rel}/{p['id']}/thumb.jpg", "mp4": f"{rel}/{p['id']}/preview.mp4"}
            for p in presets.PRESETS
        ],
        "rig_props": {k: {"default": v[0], "min": v[1], "max": v[2]}
                      for k, v in __import__("hero_ship.parts", fromlist=["PROPS"]).PROPS.items()},
    }


def write(repo_root):
    path = os.path.join(repo_root, "previews", "hero_ship", "manifest.json")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data(), f, indent=2)
    return path
