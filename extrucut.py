'''
Copyright (C) 2018 CG Cookie
http://cgcookie.com
hello@cgcookie.com

Created by Jonathan Denning

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program.  If not, see <http://www.gnu.org/licenses/>.
'''

import os
import math
import time

import bgl
import bpy
import bmesh
from mathutils import Vector
from mathutils.geometry import intersect_line_line
from bmesh.types import BMVert, BMEdge, BMFace

from .addon_common.cookiecutter.cookiecutter import CookieCutter
from .addon_common.common import ui
from .addon_common.common.bmesh_utils import BMeshSelectState, BMeshHideState
from .addon_common.common.maths import Point, Point2D, XForm
from .addon_common.common.decorators import PersistentOptions



'''

 +---+---+---+---+                       +-----------+
 |   |   |   |   |                       | \       / |
 +---X===X---+---+       +---+           |   +---+   +---+
 |   $   $   |   |       |   |           |   |   | /   / |
 +---X===X===X---+  ==>  +---+---+  ==>  +---+---+---+   |
 |   $   $   $   |       |   |   |       |   |   |   |   |
 +---X===X===X---+       +---+---+       |   +---+---+   |
 |   |   |   |   |                       | /     |     \ |
 +---+---+---+---+                       +-------+-------+

'''

@PersistentOptions()
class ExtruCutOptions:
    defaults = {
        'by': 'count',
        'count': 5,
        'length': 0.5,
        'position': 9,
    }


class VIEW3D_OT_extrucut(CookieCutter):
    bl_idname      = 'cgcookie.extrucut'
    bl_label       = 'ExtruCut'
    bl_description = 'Extrude + Loop Cut'
    bl_space_type  = 'VIEW_3D'
    bl_region_type = 'TOOLS'

    default_keymap = {
        'displace': {'LEFTMOUSE','CTRL+LEFTMOUSE'},
        'commit': {'RET',},
        'cancel': {'RIGHTMOUSE', 'ESC'},
    }

    @classmethod
    def can_start(cls, context):
        ''' Start only if editing a mesh '''
        ob = context.active_object
        return (ob and ob.type == 'MESH' and context.mode == 'EDIT_MESH')

    def start(self):
        ''' ExtruCut tool is starting '''

        bpy.ops.ed.undo_push()  # push current state to undo

        self.header_text_set('ExtruCut')
        self.cursor_modal_set('CROSSHAIR')
        self.manipulator_hide()

        self.segment_opts = ExtruCutOptions()
        self.segments = 1
        self.is_dirty = True
        self.extrude_verts = []
        self.extrude_edges = []
        self.extrude_sides = []
        self.extrude_faces = []
        self.join_verts = {}

        # collect working data
        self.obj = self.context.edit_object
        self.emesh = self.obj.data
        self.bmesh = bmesh.from_edit_mesh(self.emesh)
        self.xform = XForm(self.obj.matrix_world)
        self.hidden    = BMeshHideState(self.bmesh)
        # get all faces, edges, and verts involved in extrusion
        self.all_faces = { f for f in self.bmesh.faces if f.select }
        self.all_edges = { e for f in self.all_faces for e in f.edges }
        self.all_verts = { v for f in self.all_faces for v in f.verts }
        # get inner edges and verts
        self.inner_edges = { e for e in self.all_edges if len(e.link_faces) > 1 and all(f in self.all_faces for f in e.link_faces) }
        self.outer_edges = self.all_edges - self.inner_edges
        self.outer_verts = { v for e in self.outer_edges for v in e.verts}
        self.inner_verts = self.all_verts - self.outer_verts
        # hide extruded geometry
        for g in self.all_faces | self.inner_edges | self.inner_verts:
            g.hide = True
        # compute an extrusion direction
        self.extrude_dir = sum((f.normal for f in self.all_faces), Vector((0,0,0))).normalized()
        self.extrude_pt0 = sum((v.co for v in self.all_verts), Vector((0,0,0))) / len(self.all_verts)
        self.extrude_pt1 = self.extrude_pt0 + self.extrude_dir
        self.extrude_dist = 0.0

        def get_dist(): return self.extrude_dist
        def get_dist_print(): return '%0.4f' % self.extrude_dist
        def set_dist(v):
            self.extrude_dist = float(v)
            self.is_dirty = True
        def get_segcount(): return self.segment_opts['count']
        def set_segcount(v):
            self.segment_opts['count'] = max(1, int(v))
            self.segment_opts['by'] = 'count'
            self.is_dirty = True
        def get_seglen(): return self.segment_opts['length']
        def get_seglen_print(): return '%0.3f' % self.segment_opts['length']
        def set_seglen(v):
            self.segment_opts['length'] = max(0.001, float(v))
            self.segment_opts['by'] = 'length'
            self.is_dirty = True
        def get_segby(): return self.segment_opts['by']
        def set_segby(v):
            self.segment_opts['by'] = v.lower()
            self.is_dirty = True
        def fn_get_pos_wrap(v):
            if type(v) is int: return v
            return Point2D(v)
        def fn_set_pos_wrap(v):
            if type(v) is int: return v
            return tuple(v)
        fn_pos = self.segment_opts.gettersetter('position', fn_get_wrap=fn_get_pos_wrap, fn_set_wrap=fn_set_pos_wrap)
        win = self.wm.create_window('ExtruCut', {'fn_pos':fn_pos, 'movable':True})
        win.add(ui.UI_Number('Displace', get_dist, set_dist, fn_get_print_value=get_dist_print, fn_set_print_value=set_dist))
        ui_segments = win.add(ui.UI_Frame('Segments'))
        ui_segments.add(ui.UI_Number('Count', get_segcount, set_segcount))
        ui_segments.add(ui.UI_Number('Length', get_seglen, set_seglen, fn_get_print_value=get_seglen_print, fn_set_print_value=set_seglen))
        segby = ui_segments.add(ui.UI_Options(get_segby, set_segby, label='By: ', vertical=False))
        segby.add_option('count')
        segby.add_option('length')


    def end_commit(self):
        ''' Commit changes to mesh! '''

        # delete previously selected geometry
        for bmf in self.all_faces:   self.bmesh.faces.remove(bmf)
        for bme in self.inner_edges: self.bmesh.edges.remove(bme)
        for bmv in self.inner_verts: self.bmesh.verts.remove(bmv)

        # create new geometry
        def get_bmv(i, v):
            return self.join_verts[i] if i in self.join_verts else self.bmesh.verts.new(v)
        lbmv = [ get_bmv(i, v) for (i, v) in enumerate(self.extrude_verts) ]
        lbmf = [ self.bmesh.faces.new([lbmv[i_v] for i_v in liv]) for liv in self.extrude_sides ]
        lbmf += [ self.bmesh.faces.new([lbmv[i_v] for i_v in liv]) for liv in self.extrude_faces ]
        for bmf in lbmf:
            bmf.normal_update()
            bmf.select = True
        bmesh.update_edit_mesh(self.emesh)
        bpy.ops.mesh.normals_make_consistent()
        n_sides = len(self.extrude_sides)
        for bme in self.outer_edges: bme.select = False
        for bmv in self.outer_verts: bmv.select = False
        for i,bmf in enumerate(lbmf): bmf.select = (i >= n_sides)

        bpy.ops.object.mode_set(mode='OBJECT')
        bpy.ops.object.mode_set(mode='EDIT')

    def end_cancel(self):
        ''' Cancel changes '''
        bpy.ops.ed.undo()   # undo geometry hide

    def end(self):
        ''' Restore everything, because we're done '''
        self.manipulator_restore()
        self.header_text_restore()
        self.cursor_modal_restore()

    def update(self):
        ''' Check if we need to update any internal data structures '''
        self.segment_opts.clean()
        if not self.is_dirty: return

        # recompute
        self.is_dirty = False
        n = self.segment_opts['count'] if self.segment_opts['by'] == 'count' else math.floor(self.extrude_dist / self.segment_opts['length'])
        n = max(1, min(n, 100))
        v = self.extrude_dir * self.extrude_dist
        l = len(self.outer_verts) * (n + 1)
        self.segments = n
        extrude_map = {}
        extrude_map.update({ bmv:(i * (n + 1)) for (i, bmv) in enumerate(self.outer_verts) })
        extrude_map.update({ bmv:(l + i) for (i, bmv) in enumerate(self.inner_verts) })
        def m(v): return extrude_map[v]
        self.extrude_verts = [
            bmv.co + v * r / n
            for bmv in self.outer_verts
            for r in range(0, n+1)
        ] + [
            bmv.co + v
            for bmv in self.inner_verts
        ]
        self.join_verts = {
            (i * (n + 1)):bmv for i,bmv in enumerate(self.outer_verts)
        }
        self.extrude_edges = [
            tuple(m(bmv) + r for bmv in bme.verts)
            for bme in self.outer_edges
            for r in range(0, n+1)
        ] + [
            (m(bmv) + r + 0, m(bmv) + r + 1)
            for bmv in self.outer_verts
            for r in range(0, n)
        ] + [
            tuple(m(bmv) + (0 if bmv in self.inner_verts else n) for bmv in bme.verts)
            for bme in self.all_edges
        ]
        self.extrude_sides = [
            (m(bme.verts[0]) + r, m(bme.verts[0]) + r + 1, m(bme.verts[1]) + r + 1, m(bme.verts[1]) + r)
            for bme in self.outer_edges
            for r in range(0, n)
        ]
        self.extrude_faces = [
            tuple(m(bmv) + (0 if bmv in self.inner_verts else n) for bmv in bmf.verts)
            for bmf in self.all_faces
        ]

    @CookieCutter.FSM_State('main')
    def modal_main(self):
        self.cursor_modal_set('CROSSHAIR')

        if self.actions.pressed('commit'):
            self.done();
            return
        if self.actions.pressed('cancel'):
            self.done(cancel=True)
            return

        if self.actions.pressed('displace'):
            return 'displace'

    def closest_extrude_Point(self, p2D : Point2D) -> Point:
        r = self.drawing.Point2D_to_Ray(p2D)
        p,_ = intersect_line_line(
            self.extrude_pt0, self.extrude_pt1,
            r.o, r.o + r.d,
            )
        return Point(p)

    @CookieCutter.FSM_State('displace', 'enter')
    def modal_enter_displace(self):
        self.mousedown_p = self.closest_extrude_Point(self.actions.mouse)
        self.mousedown_dist = self.extrude_dist

    @CookieCutter.FSM_State('displace')
    def modal_displace(self):
        self.cursor_modal_set('HAND')

        if self.actions.released('displace'):
            return 'main'
        if self.actions.pressed('cancel'):
            self.extrude_dist = self.mousedown_dist
            self.is_dirty = True
            return 'main'

        if self.actions.mousemove:
            p = self.closest_extrude_Point(self.actions.mouse)
            off = self.extrude_dir.dot(p - self.mousedown_p)
            self.extrude_dist = self.mousedown_dist + off
            if self.actions.ctrl:
                self.extrude_dist = math.ceil(self.extrude_dist / self.segment_opts['length']) * self.segment_opts['length']
            self.is_dirty = True

    def glVertex(self, p : Point):
        bgl.glVertex3f(*self.xform.l2w_point(p))

    @CookieCutter.Draw('post3d')
    def draw_postview(self):
        if self.extrude_dist is None: return

        glv = self.glVertex
        bgl.glEnable(bgl.GL_BLEND)

        # draw extrusion line
        self.drawing.line_width(1.0)
        bgl.glBegin(bgl.GL_LINES)
        bgl.glColor4f(1.0, 0.0, 1.0, 0.25)
        glv(self.extrude_pt0 - self.extrude_dir*1000)
        glv(self.extrude_pt0)
        bgl.glColor4f(0.0, 1.0, 1.0, 0.25)
        glv(self.extrude_pt0)
        glv(self.extrude_pt0 + self.extrude_dir*1000)
        bgl.glEnd()

        # draw new geometry: points
        bgl.glDepthRange(0, 0.9999)
        self.drawing.point_size(3.0)
        bgl.glBegin(bgl.GL_POINTS)
        bgl.glColor4f(0.0, 0.2, 0.1, 1.0)
        for v in self.extrude_verts:
            glv(v)
        bgl.glEnd()
        bgl.glDepthRange(0, 1)

        # draw new geometry: edges
        bgl.glDepthRange(0, 0.9999)
        self.drawing.line_width(1.0)
        bgl.glBegin(bgl.GL_LINES)
        bgl.glColor4f(0.0, 0.2, 0.1, 1.0)
        for (iv0,iv1) in self.extrude_edges:
            glv(self.extrude_verts[iv0])
            glv(self.extrude_verts[iv1])
        bgl.glEnd()
        bgl.glDepthRange(0, 1)

        # draw new geometry: faces
        n_orig = len(self.outer_edges) * self.segments
        bgl.glBegin(bgl.GL_TRIANGLES)
        bgl.glColor4f(0.7, 0.7, 0.5, 0.8)
        for liv in self.extrude_faces:
            iv0 = liv[0]
            for iv1,iv2 in zip(liv[1:-1], liv[2:]):
                glv(self.extrude_verts[iv0])
                glv(self.extrude_verts[iv1])
                glv(self.extrude_verts[iv2])
        bgl.glColor4f(0.5, 0.6, 0.5, 0.8)
        for liv in self.extrude_sides:
            iv0 = liv[0]
            for iv1,iv2 in zip(liv[1:-1], liv[2:]):
                glv(self.extrude_verts[iv0])
                glv(self.extrude_verts[iv1])
                glv(self.extrude_verts[iv2])
        bgl.glEnd()

        bgl.glDisable(bgl.GL_BLEND)


