"""Who weighs what and what everything is made of.

Nothing here touches Blender, so the sound engine can be tested without it.

DROIDS    one entry per cast member: mass, which share of it lands on a foot or
          a hand, and what its feet and fingers are made of.
MATERIALS how each surface rings: stiffness, ring time, how brightly it is
          struck, how much of the hit it turns into sound.
classify(material_name) -> a MATERIALS key, from the names the ship and the
          droid kit already use (SB Deck Plate, RB_polymer, SB Rug ...).
"""
import re

# --- the cast -------------------------------------------------------------
# mass_kg: whole droid. leg/arm: share of the mass behind a planted foot or a
# moving hand (a foot carries most of the body, a hand only the forearm).
# foot/hand: material of the sole and the fingertips. foot_size: sole length,
# which sets the pitch of the foot's own ring.
DROIDS = {
    "rx07": dict(label="RX-07", mass_kg=240.0, leg=0.55, arm=0.06,
                 foot="metal", foot_size=0.42, hand="metal", hand_size=0.12),
    "hazard": dict(label="Hazard droid", mass_kg=85.0, leg=0.5, arm=0.05,
                   foot="metal", foot_size=0.30, hand="metal", hand_size=0.09),
    "hover_drone": dict(label="Hover drone", mass_kg=9.0, leg=1.0, arm=0.04,
                        foot="metal_thin", foot_size=0.45, hand="metal", hand_size=0.04),
    "computer": dict(label="Ship's computer", mass_kg=400.0, leg=0.0, arm=0.03,
                     foot="metal", foot_size=0.5, hand="polymer", hand_size=0.06),
    "generic": dict(label="Droid", mass_kg=100.0, leg=0.5, arm=0.05,
                    foot="metal", foot_size=0.3, hand="metal", hand_size=0.08),
}


def droid_id(names):
    """Best profile for an armature, from its tags and name (any of them).
    The hazard droid and RX-07 share the rig name RobotRig, so the hazard tag
    is checked first and RobotRig falls through to RX-07."""
    text = " ".join(str(n) for n in names if n).lower()
    if "hazard" in text:
        return "hazard"
    if "drone" in text or "hover" in text:
        return "hover_drone"
    if "computer" in text or "mainframe" in text:
        return "computer"
    if re.search(r"rx[-_ ]?07|box ?mech|robotrig|robot_rig|robot_rx", text):
        return "rx07"
    return "generic"


# --- materials ------------------------------------------------------------
# k:        modal pitch constant, Hz x metres (bigger object -> lower ring)
# t60:      seconds for the ring to die away (lowest mode)
# hard:     stiffness of the hit; soft things smear the strike and sound dull
# radiate:  how much of the hit becomes sound
# density:  kg/m3 of the solid (props without a rigid-body mass use it)
# grit:     share of short scuff noise in the hit, and its centre (Hz)
# ratios:   modal pitch ratios (inharmonic for plates, few for soft stuff)
_PLATE = (1.0, 1.594, 2.136, 2.296, 2.653, 2.918, 3.156, 3.501, 4.06, 4.6, 5.2, 6.3)
_BAR = (1.0, 2.756, 5.404, 8.933)
_SOFT = (1.0, 1.8, 2.9)

MATERIALS = {
    "metal":      dict(k=140.0, t60=0.9,  hard=1.0,  radiate=1.0,  density=2400, grit=(0.25, 4200), ratios=_PLATE),
    "metal_thin": dict(k=110.0, t60=1.5,  hard=0.9,  radiate=1.1,  density=600,  grit=(0.2, 5200),  ratios=_PLATE),
    "deck":       dict(k=95.0,  t60=0.35, hard=1.0,  radiate=0.9,  density=7800, grit=(0.35, 3200), ratios=_PLATE),
    "grate":      dict(k=120.0, t60=0.5,  hard=0.95, radiate=1.0,  density=2000, grit=(0.5, 3800),  ratios=_BAR),
    "glass":      dict(k=260.0, t60=0.6,  hard=0.95, radiate=0.8,  density=2500, grit=(0.1, 6500),  ratios=_PLATE),
    "ceramic":    dict(k=220.0, t60=0.25, hard=0.9,  radiate=0.7,  density=2300, grit=(0.15, 5000), ratios=_BAR),
    "polymer":    dict(k=70.0,  t60=0.07, hard=0.45, radiate=0.6,  density=1200, grit=(0.3, 2600),  ratios=_SOFT),
    "rubber":     dict(k=40.0,  t60=0.03, hard=0.15, radiate=0.25, density=1100, grit=(0.25, 1400), ratios=_SOFT),
    "fabric":     dict(k=30.0,  t60=0.015, hard=0.08, radiate=0.15, density=300, grit=(0.6, 1800),  ratios=_SOFT),
    "stone":      dict(k=160.0, t60=0.05, hard=1.0,  radiate=0.5,  density=2300, grit=(0.45, 2800), ratios=_SOFT),
    "wood":       dict(k=90.0,  t60=0.12, hard=0.6,  radiate=0.7,  density=700,  grit=(0.25, 2400), ratios=_BAR),
}

# name pattern -> material; first match wins, so the specific ones come first
_RULES = (
    (r"rug|carpet|fabric|cloth|cushion|upholst|seat ?pad|mattress|pillow|blanket", "fabric"),
    (r"rubber|tyre|tire|mat\b|gasket|hose|cable|wire", "rubber"),
    (r"polymer|plastic|mug|datapad|abs\b|resin|nylon|helmet", "polymer"),
    (r"glass|lens|visor|screen|window|monitor|display", "glass"),
    (r"ceramic|tile|porcelain", "ceramic"),
    (r"wood|plank|crate_wood", "wood"),
    (r"concrete|stone|rock|cement|asphalt", "stone"),
    (r"grate|grille|mesh|vent|diamond", "grate"),
    (r"deck|floor|ground|walkway", "deck"),
    (r"can\b|oil ?can|tin|sheet|foil|duct|locker|toolbox|panel|hatch|crate", "metal_thin"),
    (r"metal|steel|iron|alu|chrome|brass|copper|pin|bolt|rivet|rb_|armour|armor|pipe|rail|bulkhead|hull|beam|frame", "metal"),
)


def classify(name, default="metal"):
    n = (name or "").lower()
    for pat, mat in _RULES:
        if re.search(pat, n):
            return mat
    return default
