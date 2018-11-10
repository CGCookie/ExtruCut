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

bl_info = {
    'name':         'ExtruCut',
    'description':  'Extrude+LoopCut',
    'author':       'Jon Denning',
    'version':      (0, 0, 1),
    'blender':      (2, 7, 9),
    'location':     'View 3D > Tool Shelf',
    #'warning':      '',
    #'wiki_url':     '',
    #'tracker_url':  '',
    'category':     '3D View',
}

from bpy.utils import register_class, unregister_class
from bpy.types import Panel

from .extrucut import VIEW3D_OT_extrucut


class VIEW3D_PT_tools_extrucut(Panel):
    ''' Creates a panel in the Tools panel '''
    bl_label       = 'ExtruCut'
    bl_category    = 'Tools'
    bl_space_type  = 'VIEW_3D'
    bl_region_type = 'TOOLS'
    bl_context     = 'mesh_edit'

    def draw(self, context):
        row = self.layout.row()
        row.operator('cgcookie.extrucut')


def register():
    register_class(VIEW3D_OT_extrucut)
    register_class(VIEW3D_PT_tools_extrucut)

def unregister():
    unregister_class(VIEW3D_PT_tools_extrucut)
    unregister_class(VIEW3D_OT_extrucut)
