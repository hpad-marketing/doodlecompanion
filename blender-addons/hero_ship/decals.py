"""Painted markings: ship number and stencil text as flush geometry."""
import math
import bmesh
import bpy
from mathutils import Matrix, Vector
from . import geo, body as B


def _text_bm(txt, size, extrude=0.008):
    cu = bpy.data.curves.new("hs_txt", "FONT")
    cu.body = txt
    cu.size = size
    cu.extrude = extrude
    cu.align_x = "CENTER"
    cu.align_y = "CENTER"
    tmp = bpy.data.objects.new("hs_txt", cu)
    bpy.context.scene.collection.objects.link(tmp)
    dg = bpy.context.evaluated_depsgraph_get()
    me = tmp.evaluated_get(dg).to_mesh()
    bm = bmesh.new()
    bm.from_mesh(me)
    tmp.evaluated_get(dg).to_mesh_clear()
    bpy.data.objects.remove(tmp)
    bpy.data.curves.remove(cu)
    return bm


def apply(c, body, mats, hull):
    out = bmesh.new()
    items = []
    for s in (1, -1):
        # big hull number on the aft body side, above the glow line
        items.append(("07", 1.1, Vector((s * 4.605, -8.6, -1.12)), s, B.ACCENT))
        items.append(("DID-07  OUTBOUND", 0.22, Vector((s * 4.605, -8.6, -1.80)), s, B.DARK))
        items.append(("NO STEP", 0.16, Vector((s * 4.06, 8.6, 0.95)), s, B.DARK))
    for txt, size, p, s, mat in items:
        bm = _text_bm(txt, size)
        # text lies in XY facing +Z; stand it on the side wall facing +-X
        # text X -> along the hull (reads left to right from outside), text Y -> up
        rot = Matrix(((0, 0, s, 0), (s, 0, 0, 0), (0, 1, 0, 0), (0, 0, 0, 1)))
        bmesh.ops.transform(bm, matrix=Matrix.Translation(p) @ rot, verts=bm.verts)
        for f in bm.faces:
            f.material_index = mat
        me = bpy.data.meshes.new("t")
        bm.to_mesh(me)
        bm.free()
        out.from_mesh(me)
        bpy.data.meshes.remove(me)
    geo.box_uv(out)
    ob = geo.obj_from_bm("Hull Markings", out, c, parent=body, mats=mats, uv=False)
    ob["sb_piece"] = "hs_airframe"
    return ob
