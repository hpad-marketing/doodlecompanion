"""python3 test_stations.py -- <tmp root>: register the add-on, start an episode, draw every
station through a checking layout (icons, operators, properties must exist) and run the
quick operators."""
import os, sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
import bpy
bpy.ops.wm.read_factory_settings(use_empty=True)
import ship_builder as SB
SB.register()
from ship_builder import stations as S, episode_flow as F

root = sys.argv[sys.argv.index('--') + 1] if '--' in sys.argv else '/tmp/st_root'
os.makedirs(root, exist_ok=True)
S.root = lambda: root

ICONS = {e.identifier for e in bpy.types.UILayout.bl_rna.functions["prop"].parameters["icon"].enum_items}
BAD = []


class Op:
    def __init__(self, idname):
        self.__dict__["_id"] = idname
        mod, name = idname.split(".")
        try:
            rna = getattr(getattr(bpy.ops, mod), name).get_rna_type()
            self.__dict__["_props"] = {p.identifier for p in rna.properties}
        except (AttributeError, KeyError):
            self.__dict__["_props"] = None
            BAD.append(f"operator {idname}")

    def __setattr__(self, k, v):
        if self._props is not None and k not in self._props:
            BAD.append(f"{self._id}.{k}")


class Lay:
    def __getattr__(self, name):
        if name in ("scale_x", "scale_y", "enabled", "active", "alert", "use_property_split", "use_property_decorate", "alignment", "ui_units_x"):
            return 1
        return self._any

    def __setattr__(self, k, v):
        pass

    def _icon(self, kw):
        ic = kw.get("icon")
        if ic and ic not in ICONS:
            BAD.append(f"icon {ic}")

    def _any(self, *a, **kw):
        self._icon(kw)
        return Lay()

    def operator(self, idname, **kw):
        self._icon(kw)
        return Op(idname)

    def prop(self, data, name, **kw):
        self._icon(kw)
        if data is not None and not hasattr(data, name) and name not in getattr(data, "bl_rna", bpy.types.ID.bl_rna).properties:
            BAD.append(f"prop {type(data).__name__}.{name}")

    def prop_enum(self, data, name, value, **kw):
        return self.prop(data, name, **kw)

    def template_icon(self, **kw):
        return Lay()


class Ctx:
    def __init__(self):
        self.window_manager = bpy.context.window_manager
        self.scene = bpy.context.scene
        self.area = None
        self.space_data = None
        self.region = None
        self.preferences = bpy.context.preferences
        self.mode = "OBJECT"


ctx = Ctx()
s = S.st(ctx)


def draw_all(tag):
    for k in S.DRAW:
        s.station = k
        try:
            S.draw_bar(Lay(), ctx)
            S.draw_station(Lay(), ctx)
        except Exception as e:
            import traceback; traceback.print_exc()
            BAD.append(f"{tag} draw {k}: {e!r}")


draw_all("no-episode")
s.new_title = "The Leak"
print("ep_new", bpy.ops.ship.ep_new(template="blank"))
e = S.ep()
assert e is not None
e.script = """INT. COMMAND CENTRE
COMPUTER: Minor anomaly detected.
HAZARD: (happy) Minor means fine!
RX-07: (worried) It is dripping. [points at the ceiling]
INT. ENGINE ROOM
HAZARD: (annoyed) Who touched the valve?
RX-07: (calm) You did.
"""
e.parse(); F.voice_lines(e); F.retime(e); F.coverage(e)
S.save()
draw_all("episode")
for opname, kw in (("ep_emotion", {}), ("ep_event", {}), ("ep_approve", {})):
    op = getattr(bpy.ops.ship, opname)
    try:
        print(opname, op.poll(), )
    except Exception as ex:
        BAD.append(f"poll {opname}: {ex!r}")
print("youtube.ready", __import__("ship_builder.youtube", fromlist=["x"]).ready(root))
print("publish_at", __import__("ship_builder.youtube", fromlist=["x"]).publish_at("2026-11-10 18:00"))
# the library: every tab draws (pictures, controls, poses, moves, scene list)
Std = __import__("ship_builder.studio", fromlist=["x"])
Cat = __import__("ship_builder.catalog", fromlist=["x"])


class Reg:
    width = 560


ctx.region = Reg()
s.station = "LIBRARY"
for c, _l, _i in Cat.CATEGORIES:
    Std.state(ctx).cat = c
    try:
        Std.SHIP_PT_library.draw(type("P", (), {"layout": Lay()})(), ctx)
    except Exception as e:
        import traceback; traceback.print_exc()
        BAD.append(f"library {c}: {e!r}")
SB.unregister()
print("STATIONS", "OK" if not BAD else "BAD", sorted(set(BAD)))
