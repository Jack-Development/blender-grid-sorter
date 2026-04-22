bl_info = {
    "name": "Smart Grid Sorter",
    "author": "Jack Shilton",
    "version": (1, 1, 0),
    "blender": (3, 0, 0),
    "location": "View3D > Sidebar > Grid Tools",
    "description": "Arranges selected objects into a clean, overlap-free grid layout",
    "category": "Object",
    "doc_url": "",
    "tracker_url": "",
}

import bpy
import mathutils
from bpy.props import IntProperty, FloatProperty, EnumProperty
from bpy.types import Operator, Panel, PropertyGroup


class GRIDSORTER_PG_settings(PropertyGroup):
    layout_mode: EnumProperty(
        name="Layout",
        description="Whether to use a fixed column count or a maximum row width",
        items=[
            ('COLUMNS', "Columns", "Pack objects into a fixed number of columns"),
            ('ROW_WIDTH', "Row Width", "Fit as many objects as possible into each row before wrapping"),
        ],
        default='COLUMNS',
    )
    columns: IntProperty(
        name="Columns",
        description="Number of columns in the grid layout",
        default=5,
        min=1,
        soft_max=20,
    )
    row_width: FloatProperty(
        name="Row Width",
        description="Maximum width of each row (in scene units) before wrapping to the next row",
        default=20.0,
        min=0.01,
        soft_max=200.0,
        unit='LENGTH',
    )
    margin: FloatProperty(
        name="Gap",
        description="Minimum gap between objects (in scene units)",
        default=1.0,
        min=0.0,
        soft_max=10.0,
        unit='LENGTH',
    )
    sort_mode: EnumProperty(
        name="Sort By",
        description="How to order objects before placing them in the grid",
        items=[
            ('NAME', "Name", "Sort alphabetically by object name"),
            ('SIZE_DESC', "Size (Large → Small)", "Sort by footprint area, largest first"),
            ('SIZE_ASC', "Size (Small → Large)", "Sort by footprint area, smallest first"),
        ],
        default='NAME',
    )


class OBJECT_OT_grid_sort(Operator):
    bl_idname = "object.grid_sort"
    bl_label = "Apply Grid Sort"
    bl_options = {'REGISTER', 'UNDO'}

    @staticmethod
    def _world_bounds(obj):
        mat = obj.matrix_world
        corners = [mat @ mathutils.Vector(c) for c in obj.bound_box]

        min_x = min(c.x for c in corners)
        max_x = max(c.x for c in corners)
        min_y = min(c.y for c in corners)
        max_y = max(c.y for c in corners)

        return min_x, max_x, min_y, max_y, max_x - min_x, max_y - min_y

    def _place_columns(self, objects, cols, margin):
        col_widths  = [0.0] * cols
        row_heights = []
        current_row_max = 0.0

        for idx, obj in enumerate(objects):
            *_, w, h = self._world_bounds(obj)
            col = idx % cols

            col_widths[col] = max(col_widths[col], w + margin)
            current_row_max = max(current_row_max, h + margin)

            if col == cols - 1 or idx == len(objects) - 1:
                row_heights.append(current_row_max)
                current_row_max = 0.0

        col_offsets = [sum(col_widths[:c]) for c in range(cols)]
        row_offsets = [sum(row_heights[:r]) for r in range(len(row_heights))]

        for idx, obj in enumerate(objects):
            col = idx % cols
            row = idx // cols

            min_x, _, _, max_y, *_ = self._world_bounds(obj)

            obj.location.x = col_offsets[col] + (obj.location.x - min_x)
            obj.location.y = -row_offsets[row] + (obj.location.y - max_y)

    def _place_row_width(self, objects, row_width, margin):
        rows = []
        current_row = []
        current_row_w = 0.0

        for obj in objects:
            *_, w, h = self._world_bounds(obj)
            obj_slot = w + margin

            if current_row and current_row_w + obj_slot > row_width:
                rows.append(current_row)
                current_row = []
                current_row_w = 0.0

            current_row.append(obj)
            current_row_w += obj_slot

        if current_row:
            rows.append(current_row)

        y_offset = 0.0
        for row_objs in rows:
            row_height = 0.0
            x_offset = 0.0

            for obj in row_objs:
                min_x, _, _, max_y, w, h = self._world_bounds(obj)

                obj.location.x = x_offset + (obj.location.x - min_x)
                obj.location.y = -y_offset + (obj.location.y - max_y)

                x_offset += w + margin
                row_height = max(row_height, h + margin)

            y_offset += row_height

    def execute(self, context):
        props  = context.scene.grid_sorter_props
        margin = props.margin

        selected = context.selected_objects
        if not selected:
            self.report({'WARNING'}, "No objects selected")
            return {'CANCELLED'}

        selection_set = set(selected)
        objects = [obj for obj in selected if obj.parent not in selection_set]

        if props.sort_mode == 'NAME':
            objects.sort(key=lambda o: o.name.lower())
        else:
            reverse = (props.sort_mode == 'SIZE_DESC')
            objects.sort(
                key=lambda o: o.dimensions.x * o.dimensions.y,
                reverse=reverse,
            )

        if props.layout_mode == 'COLUMNS':
            self._place_columns(objects, props.columns, margin)
        else:
            self._place_row_width(objects, props.row_width, margin)

        return {'FINISHED'}


class VIEW3D_PT_grid_sorter(Panel):
    bl_space_type  = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category    = 'Grid Tools'
    bl_label       = "Smart Grid Sorter"

    def draw(self, context):
        layout = self.layout
        props  = context.scene.grid_sorter_props

        layout.use_property_split = True
        layout.use_property_decorate = False

        col = layout.column(align=True)
        col.prop(props, "sort_mode")
        col.prop(props, "layout_mode")

        if props.layout_mode == 'COLUMNS':
            col.prop(props, "columns")
        else:
            col.prop(props, "row_width")

        col.prop(props, "margin")

        layout.separator()
        layout.operator("object.grid_sort", icon='GRID')


classes = (
    GRIDSORTER_PG_settings,
    OBJECT_OT_grid_sort,
    VIEW3D_PT_grid_sorter,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.grid_sorter_props = bpy.props.PointerProperty(
        type=GRIDSORTER_PG_settings
    )


def unregister():
    del bpy.types.Scene.grid_sorter_props
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()
