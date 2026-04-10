"""
Scan Surface Align
Author: Glazyrin Alexey Sergeevich
Studio: 3dpotok.ru
Telegram: @standalone2k
Website: https://3dpotok.ru
License: GPL-3.0-or-later
"""

bl_info = {
    "name": "Scan Surface Align",
    "author": "Glazyrin Alexey Sergeevich | 3dpotok.ru",
    "version": (1, 0, 3),
    "blender": (5, 1, 0),
    "location": "View3D > Sidebar > Scan Align",
    "description": (
        "RU: Выравнивание выделенных поверхностей скана перпендикулярно мировым осям "
        "с сохранением сторон, AUTO ALIGN и Quick Align. "
        "EN: Align selected scan surfaces perpendicular to world axes with stored sides, "
        "AUTO ALIGN, and Quick Align tools."
    ),
    "doc_url": "https://3dpotok.ru",
    "tracker_url": "https://t.me/standalone2k",
    "support": "COMMUNITY",
    "category": "Mesh",
}

import itertools
from math import inf

import bmesh
import bpy
from bpy.props import BoolProperty, EnumProperty, IntProperty, PointerProperty, StringProperty
from bpy.types import Operator, Panel, PropertyGroup
from mathutils import Matrix, Vector


AXIS_ITEMS = [
    ("X", "X", "Align perpendicular to the world X axis"),
    ("Y", "Y", "Align perpendicular to the world Y axis"),
    ("Z", "Z", "Align perpendicular to the world Z axis"),
]

AXIS_VECTORS = {
    "X": Vector((1.0, 0.0, 0.0)),
    "Y": Vector((0.0, 1.0, 0.0)),
    "Z": Vector((0.0, 0.0, 1.0)),
}

addon_keymaps = []


def serialize_faces(indices):
    return ",".join(str(index) for index in sorted(set(indices)))


def deserialize_faces(data):
    if not data:
        return []
    return [int(part) for part in data.split(",") if part.strip()]


def axis_name_for_vector(vector, excluded=None):
    excluded = set(excluded or [])
    best_axis = None
    best_score = -1.0
    for axis_name, axis_vector in AXIS_VECTORS.items():
        if axis_name in excluded:
            continue
        score = abs(vector.normalized().dot(axis_vector))
        if score > best_score:
            best_axis = axis_name
            best_score = score
    return best_axis or "Z"


def signed_axis_vector(axis_name, source_vector):
    axis_vector = AXIS_VECTORS[axis_name]
    return axis_vector if axis_vector.dot(source_vector) >= 0.0 else -axis_vector


def object_in_view_layer(view_layer, obj):
    return bool(obj and obj.name in view_layer.objects)


def ensure_mesh_object(context, use_target=False):
    settings = context.scene.scan_align_settings
    view_layer = context.view_layer

    if use_target and settings.target_object and settings.target_object.type == "MESH":
        if object_in_view_layer(view_layer, settings.target_object):
            return settings.target_object

    obj = context.object
    if obj and obj.type == "MESH" and object_in_view_layer(view_layer, obj):
        if use_target:
            settings.target_object = obj
        return obj
    return None


def get_selected_face_indices(obj):
    if not obj or obj.type != "MESH" or obj.mode != "EDIT":
        return []

    bm = bmesh.from_edit_mesh(obj.data)
    bm.faces.ensure_lookup_table()
    bm.faces.index_update()
    return [face.index for face in bm.faces if face.select]


def set_selected_face_indices(obj, indices):
    if not obj or obj.type != "MESH" or obj.mode != "EDIT":
        return False

    target_indices = set(indices)
    bm = bmesh.from_edit_mesh(obj.data)
    bm.faces.ensure_lookup_table()
    bm.faces.index_update()

    for face in bm.faces:
        face.select = face.index in target_indices

    bmesh.update_edit_mesh(obj.data, loop_triangles=False, destructive=False)
    return True


def collect_face_stats(obj, indices):
    if not obj or obj.type != "MESH":
        raise ValueError("Active object must be a mesh.")

    normal_matrix = obj.matrix_world.to_3x3().inverted().transposed()
    total_area = 0.0
    normal_sum = Vector((0.0, 0.0, 0.0))
    center_sum = Vector((0.0, 0.0, 0.0))
    valid_count = 0

    if obj.mode == "EDIT":
        bm = bmesh.from_edit_mesh(obj.data)
        bm.faces.ensure_lookup_table()
        bm.faces.index_update()
        faces = bm.faces
        face_count = len(faces)
        for index in indices:
            if index < 0 or index >= face_count:
                continue
            face = faces[index]
            area = max(face.calc_area(), 1e-8)
            normal_world = (normal_matrix @ face.normal).normalized()
            center_world = obj.matrix_world @ face.calc_center_median()
            normal_sum += normal_world * area
            center_sum += center_world * area
            total_area += area
            valid_count += 1
    else:
        mesh = obj.data
        faces = mesh.polygons
        face_count = len(faces)
        for index in indices:
            if index < 0 or index >= face_count:
                continue
            face = faces[index]
            area = max(face.area, 1e-8)
            normal_world = (normal_matrix @ face.normal).normalized()
            center_world = obj.matrix_world @ face.center
            normal_sum += normal_world * area
            center_sum += center_world * area
            total_area += area
            valid_count += 1

    if valid_count == 0 or normal_sum.length < 1e-8:
        raise ValueError("Stored face set is empty or no longer valid.")

    return normal_sum.normalized(), center_sum / total_area, valid_count


def orthonormal_basis(primary, secondary):
    axis_a = primary.normalized()
    axis_b = secondary - axis_a * secondary.dot(axis_a)
    if axis_b.length < 1e-6:
        raise ValueError("Selected sides are too parallel for a two-side alignment.")
    axis_b.normalize()
    axis_c = axis_a.cross(axis_b)
    if axis_c.length < 1e-6:
        raise ValueError("Could not build a stable alignment basis from the selected sides.")
    axis_c.normalize()
    axis_b = axis_c.cross(axis_a).normalized()
    return Matrix((axis_a, axis_b, axis_c)).transposed()


def best_dual_axis_match(normal_a, normal_b):
    best_choice = None
    best_score = -inf
    for axis_a, axis_b in itertools.permutations(AXIS_VECTORS.keys(), 2):
        score = abs(normal_a.dot(AXIS_VECTORS[axis_a])) + abs(normal_b.dot(AXIS_VECTORS[axis_b]))
        if score > best_score:
            best_choice = (axis_a, axis_b)
            best_score = score
    return best_choice


def rotation_for_single_side(normal, axis_name, flip_if_aligned=False, tolerance=0.9999):
    target = signed_axis_vector(axis_name, normal)
    if flip_if_aligned and normal.normalized().dot(target) >= tolerance:
        target = -target
    return normal.rotation_difference(target).to_matrix()


def rotation_for_two_sides(normal_a, axis_a, normal_b, axis_b):
    if axis_a == axis_b:
        raise ValueError("Side 1 and Side 2 must target different axes.")

    source_basis = orthonormal_basis(normal_a, normal_b)
    best_rotation = None
    best_score = -inf

    for sign_a, sign_b in itertools.product((1.0, -1.0), repeat=2):
        target_a = AXIS_VECTORS[axis_a] * sign_a
        target_b = AXIS_VECTORS[axis_b] * sign_b
        target_basis = orthonormal_basis(target_a, target_b)
        rotation = target_basis @ source_basis.transposed()
        score = rotation[0][0] + rotation[1][1] + rotation[2][2]
        if score > best_score:
            best_rotation = rotation
            best_score = score

    if best_rotation is None:
        raise ValueError("Could not solve a valid alignment rotation.")

    return best_rotation


def apply_world_rotation(context, obj, rotation, pivot_world, apply_mode, center_origin):
    if obj.type != "MESH":
        raise ValueError("Target object must be a mesh.")

    view_layer = context.view_layer
    if not object_in_view_layer(view_layer, obj):
        raise ValueError("Target object is not in the active View Layer.")

    previous_active = view_layer.objects.active if object_in_view_layer(view_layer, view_layer.objects.active) else None
    previous_mode = obj.mode
    previous_selection = [item for item in context.selected_objects if object_in_view_layer(view_layer, item)]

    try:
        for item in previous_selection:
            item.select_set(False)
        obj.select_set(True)
        view_layer.objects.active = obj

        if obj.mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")

        transform = Matrix.Translation(pivot_world) @ rotation.to_4x4() @ Matrix.Translation(-pivot_world)
        obj.matrix_world = transform @ obj.matrix_world

        if apply_mode == "BAKE":
            bpy.ops.object.transform_apply(location=False, rotation=True, scale=False)

        if center_origin:
            bpy.ops.object.origin_set(type="ORIGIN_GEOMETRY", center="BOUNDS")
    finally:
        for item in context.selected_objects:
            item.select_set(False)
        for item in previous_selection:
            if item.name in bpy.data.objects:
                item.select_set(True)
        if previous_mode != "OBJECT" and obj.name in bpy.data.objects:
            view_layer.objects.active = obj
            bpy.ops.object.mode_set(mode=previous_mode)
        if previous_mode == "OBJECT":
            if previous_active and previous_active.name in bpy.data.objects:
                view_layer.objects.active = previous_active
            else:
                view_layer.objects.active = obj


def align_face_sets(
    context,
    obj,
    side1_faces,
    side1_axis,
    side2_faces=None,
    side2_axis="Y",
    apply_mode="ROTATE",
    center_origin=True,
    flip_if_aligned=False,
):
    normal_a, center_a, _ = collect_face_stats(obj, side1_faces)
    pivot = center_a

    if side2_faces:
        normal_b, center_b, _ = collect_face_stats(obj, side2_faces)
        rotation = rotation_for_two_sides(normal_a, side1_axis, normal_b, side2_axis)
        pivot = (center_a + center_b) * 0.5
    else:
        rotation = rotation_for_single_side(normal_a, side1_axis, flip_if_aligned=flip_if_aligned)

    apply_world_rotation(context, obj, rotation, pivot, apply_mode, center_origin)


class SCANALIGN_PG_settings(PropertyGroup):
    target_object: PointerProperty(
        name="Target Object",
        type=bpy.types.Object,
    )
    side1_faces: StringProperty(name="Side 1 Faces", default="")
    side2_faces: StringProperty(name="Side 2 Faces", default="")
    side1_axis: EnumProperty(name="Side 1 Axis", items=AXIS_ITEMS, default="Z")
    side2_axis: EnumProperty(name="Side 2 Axis", items=AXIS_ITEMS, default="Y")
    apply_mode: EnumProperty(
        name="Transform Mode",
        items=[
            ("ROTATE", "Rotate", "Rotate the object only"),
            ("BAKE", "Bake Rotation", "Apply rotation to the mesh and zero object rotation"),
        ],
        default="ROTATE",
    )
    center_origin: BoolProperty(
        name="Center Origin",
        description="Move the origin to the mesh bounds after alignment",
        default=True,
    )


class SCANALIGN_OT_store_side(Operator):
    bl_idname = "scan_align.store_side"
    bl_label = "Store Selected Faces"
    bl_description = "Store the currently selected faces as Side 1 or Side 2"
    bl_options = {"REGISTER", "UNDO"}

    side: IntProperty(default=1, min=1, max=2)

    @classmethod
    def poll(cls, context):
        obj = context.object
        return obj and obj.type == "MESH" and obj.mode == "EDIT"

    def execute(self, context):
        settings = context.scene.scan_align_settings
        obj = context.object
        selected_faces = get_selected_face_indices(obj)

        if not selected_faces:
            self.report({"ERROR"}, "Select at least one face in Edit Mode.")
            return {"CANCELLED"}

        if settings.target_object and settings.target_object != obj:
            self.report({"ERROR"}, "Stored sides already belong to another object. Clear them first.")
            return {"CANCELLED"}

        settings.target_object = obj
        setattr(settings, f"side{self.side}_faces", serialize_faces(selected_faces))

        try:
            normal, _, _ = collect_face_stats(obj, selected_faces)
            setattr(settings, f"side{self.side}_axis", axis_name_for_vector(normal))
        except ValueError:
            pass

        self.report({"INFO"}, f"Stored {len(selected_faces)} faces for Side {self.side}.")
        return {"FINISHED"}


class SCANALIGN_OT_select_side(Operator):
    bl_idname = "scan_align.select_side"
    bl_label = "Select Stored Faces"
    bl_description = "Restore selection from the stored face set"
    bl_options = {"REGISTER", "UNDO"}

    side: IntProperty(default=1, min=1, max=2)

    @classmethod
    def poll(cls, context):
        obj = context.object
        return obj and obj.type == "MESH" and obj.mode == "EDIT"

    def execute(self, context):
        settings = context.scene.scan_align_settings
        obj = context.object
        stored_object = settings.target_object

        if stored_object and stored_object != obj:
            self.report({"ERROR"}, "Switch to the stored target object to restore this selection.")
            return {"CANCELLED"}

        indices = deserialize_faces(getattr(settings, f"side{self.side}_faces"))
        if not indices:
            self.report({"ERROR"}, f"Side {self.side} has no stored faces.")
            return {"CANCELLED"}

        if not set_selected_face_indices(obj, indices):
            self.report({"ERROR"}, "Could not restore the stored face selection.")
            return {"CANCELLED"}

        self.report({"INFO"}, f"Selected stored faces for Side {self.side}.")
        return {"FINISHED"}


class SCANALIGN_OT_clear_side(Operator):
    bl_idname = "scan_align.clear_side"
    bl_label = "Clear Stored Faces"
    bl_description = "Remove the stored data for one side"
    bl_options = {"REGISTER", "UNDO"}

    side: IntProperty(default=1, min=1, max=2)

    def execute(self, context):
        settings = context.scene.scan_align_settings
        setattr(settings, f"side{self.side}_faces", "")

        if not settings.side1_faces and not settings.side2_faces:
            settings.target_object = None

        self.report({"INFO"}, f"Cleared Side {self.side}.")
        return {"FINISHED"}


class SCANALIGN_OT_auto_axes(Operator):
    bl_idname = "scan_align.auto_axes"
    bl_label = "Auto Axes"
    bl_description = "Pick the closest world axes for the stored sides"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        settings = context.scene.scan_align_settings
        obj = ensure_mesh_object(context, use_target=True)

        if not obj:
            self.report({"ERROR"}, "No target mesh object is stored yet.")
            return {"CANCELLED"}

        side1_faces = deserialize_faces(settings.side1_faces)
        side2_faces = deserialize_faces(settings.side2_faces)

        if not side1_faces:
            self.report({"ERROR"}, "Store Side 1 first.")
            return {"CANCELLED"}

        normal_a, _, _ = collect_face_stats(obj, side1_faces)

        if side2_faces:
            normal_b, _, _ = collect_face_stats(obj, side2_faces)
            axis_a, axis_b = best_dual_axis_match(normal_a, normal_b)
            settings.side1_axis = axis_a
            settings.side2_axis = axis_b
            self.report({"INFO"}, f"Auto-picked Side 1 -> {axis_a}, Side 2 -> {axis_b}.")
        else:
            settings.side1_axis = axis_name_for_vector(normal_a)
            self.report({"INFO"}, f"Auto-picked Side 1 -> {settings.side1_axis}.")

        return {"FINISHED"}


class SCANALIGN_OT_align(Operator):
    bl_idname = "scan_align.align"
    bl_label = "Align"
    bl_description = "Align the stored scan sides perpendicular to the selected axes"
    bl_options = {"REGISTER", "UNDO"}

    auto_axes: BoolProperty(default=False)

    def execute(self, context):
        settings = context.scene.scan_align_settings
        obj = ensure_mesh_object(context, use_target=True)

        if not obj:
            self.report({"ERROR"}, "No target mesh object is stored yet.")
            return {"CANCELLED"}

        side1_faces = deserialize_faces(settings.side1_faces)
        side2_faces = deserialize_faces(settings.side2_faces)

        if not side1_faces:
            self.report({"ERROR"}, "Store Side 1 faces first.")
            return {"CANCELLED"}

        axis1 = settings.side1_axis
        axis2 = settings.side2_axis

        try:
            normal_a, _, _ = collect_face_stats(obj, side1_faces)
            if self.auto_axes:
                if side2_faces:
                    normal_b, _, _ = collect_face_stats(obj, side2_faces)
                    axis1, axis2 = best_dual_axis_match(normal_a, normal_b)
                    settings.side1_axis = axis1
                    settings.side2_axis = axis2
                else:
                    axis1 = axis_name_for_vector(normal_a)
                    settings.side1_axis = axis1

            align_face_sets(
                context=context,
                obj=obj,
                side1_faces=side1_faces,
                side1_axis=axis1,
                side2_faces=side2_faces,
                side2_axis=axis2,
                apply_mode=settings.apply_mode,
                center_origin=settings.center_origin,
            )
        except ValueError as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}
        except RuntimeError as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}

        if side2_faces:
            self.report({"INFO"}, f"Aligned Side 1 to {axis1} and Side 2 to {axis2}.")
        else:
            self.report({"INFO"}, f"Aligned Side 1 to {axis1}.")
        return {"FINISHED"}


class SCANALIGN_OT_quick_align_selection(Operator):
    bl_idname = "scan_align.quick_align_selection"
    bl_label = "Quick Align Selection"
    bl_description = "Align the current face selection directly to a world axis"
    bl_options = {"REGISTER", "UNDO"}

    axis: EnumProperty(
        name="Axis",
        items=[
            ("AUTO", "Auto", "Use the closest world axis"),
            ("X", "X", "Align to world X"),
            ("Y", "Y", "Align to world Y"),
            ("Z", "Z", "Align to world Z"),
        ],
        default="AUTO",
    )

    @classmethod
    def poll(cls, context):
        obj = context.object
        return obj and obj.type == "MESH" and obj.mode == "EDIT"

    def execute(self, context):
        obj = context.object
        settings = context.scene.scan_align_settings
        selected_faces = get_selected_face_indices(obj)

        if not selected_faces:
            self.report({"ERROR"}, "Select faces in Edit Mode first.")
            return {"CANCELLED"}

        try:
            normal, _, _ = collect_face_stats(obj, selected_faces)
            axis = axis_name_for_vector(normal) if self.axis == "AUTO" else self.axis
            align_face_sets(
                context=context,
                obj=obj,
                side1_faces=selected_faces,
                side1_axis=axis,
                apply_mode=settings.apply_mode,
                center_origin=settings.center_origin,
                flip_if_aligned=self.axis != "AUTO",
            )
        except ValueError as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}
        except RuntimeError as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}

        self.report({"INFO"}, f"Aligned current selection to {axis}.")
        return {"FINISHED"}


class SCANALIGN_PT_main_panel(Panel):
    bl_label = "Scan Align"
    bl_idname = "SCANALIGN_PT_main_panel"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Scan Align"

    def draw_side_box(self, layout, settings, side):
        faces_data = getattr(settings, f"side{side}_faces")
        face_count = len(deserialize_faces(faces_data))

        box = layout.box()
        box.label(text=f"Select Faces From Side {side}")
        box.label(text=f"Stored Faces: {face_count}")
        box.label(text=f"Make Side {side} Perpendicular To:")

        axis_row = box.row(align=True)
        axis_row.prop(settings, f"side{side}_axis", expand=True)

        row = box.row(align=True)
        store = row.operator("scan_align.store_side", text="Store Selected Faces", icon="IMPORT")
        store.side = side
        select = row.operator("scan_align.select_side", text="", icon="RESTRICT_SELECT_OFF")
        select.side = side
        clear = row.operator("scan_align.clear_side", text="", icon="X")
        clear.side = side

    def draw(self, context):
        layout = self.layout
        settings = context.scene.scan_align_settings

        if settings.target_object:
            layout.label(text=f"Target: {settings.target_object.name}", icon="MESH_DATA")
        else:
            layout.label(text="Target: active mesh", icon="INFO")

        self.draw_side_box(layout, settings, 1)
        self.draw_side_box(layout, settings, 2)

        transform_box = layout.box()
        transform_box.label(text="Restore World Transforms")
        mode_row = transform_box.row(align=True)
        mode_row.prop(settings, "apply_mode", expand=True)
        transform_box.prop(settings, "center_origin")

        action_row = transform_box.row(align=True)
        action_row.scale_y = 1.25
        action_row.operator("scan_align.auto_axes", text="Auto Axes", icon="ORIENTATION_GLOBAL")
        align_manual = action_row.operator("scan_align.align", text="ALIGN", icon="CON_ROTLIKE")
        align_manual.auto_axes = False

        auto_row = transform_box.row(align=True)
        auto_row.scale_y = 1.15
        align_auto = auto_row.operator("scan_align.align", text="AUTO ALIGN", icon="DRIVER_ROTATIONAL_DIFFERENCE")
        align_auto.auto_axes = True

        quick_box = layout.box()
        quick_box.label(text="Quick Align Current Selection")
        quick_row = quick_box.row(align=True)
        quick_row.operator("scan_align.quick_align_selection", text="Auto").axis = "AUTO"
        quick_row.operator("scan_align.quick_align_selection", text="X").axis = "X"
        quick_row.operator("scan_align.quick_align_selection", text="Y").axis = "Y"
        quick_row.operator("scan_align.quick_align_selection", text="Z").axis = "Z"
        quick_box.label(text="Press X / Y / Z again to flip 180 degrees")

        help_box = layout.box()
        help_box.label(text="Hotkeys")
        help_box.label(text="Ctrl+Alt+1 / 2: Store Side 1 / Side 2")
        help_box.label(text="Ctrl+Alt+X / Y / Z: Quick Align Selection")
        help_box.label(text="Ctrl+Alt+A: ALIGN  |  Ctrl+Shift+Alt+A: AUTO ALIGN")


classes = (
    SCANALIGN_PG_settings,
    SCANALIGN_OT_store_side,
    SCANALIGN_OT_select_side,
    SCANALIGN_OT_clear_side,
    SCANALIGN_OT_auto_axes,
    SCANALIGN_OT_align,
    SCANALIGN_OT_quick_align_selection,
    SCANALIGN_PT_main_panel,
)


def register_keymaps():
    wm = bpy.context.window_manager
    kc = wm.keyconfigs.addon
    if not kc:
        return

    km = kc.keymaps.new(name="Mesh", space_type="EMPTY")

    kmi = km.keymap_items.new("scan_align.store_side", "ONE", "PRESS", ctrl=True, alt=True)
    kmi.properties.side = 1
    addon_keymaps.append((km, kmi))

    kmi = km.keymap_items.new("scan_align.store_side", "TWO", "PRESS", ctrl=True, alt=True)
    kmi.properties.side = 2
    addon_keymaps.append((km, kmi))

    kmi = km.keymap_items.new("scan_align.quick_align_selection", "X", "PRESS", ctrl=True, alt=True)
    kmi.properties.axis = "X"
    addon_keymaps.append((km, kmi))

    kmi = km.keymap_items.new("scan_align.quick_align_selection", "Y", "PRESS", ctrl=True, alt=True)
    kmi.properties.axis = "Y"
    addon_keymaps.append((km, kmi))

    kmi = km.keymap_items.new("scan_align.quick_align_selection", "Z", "PRESS", ctrl=True, alt=True)
    kmi.properties.axis = "Z"
    addon_keymaps.append((km, kmi))

    kmi = km.keymap_items.new("scan_align.align", "A", "PRESS", ctrl=True, alt=True)
    kmi.properties.auto_axes = False
    addon_keymaps.append((km, kmi))

    kmi = km.keymap_items.new("scan_align.align", "A", "PRESS", ctrl=True, alt=True, shift=True)
    kmi.properties.auto_axes = True
    addon_keymaps.append((km, kmi))


def unregister_keymaps():
    for km, kmi in addon_keymaps:
        km.keymap_items.remove(kmi)
    addon_keymaps.clear()


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.scan_align_settings = PointerProperty(type=SCANALIGN_PG_settings)
    register_keymaps()


def unregister():
    unregister_keymaps()
    del bpy.types.Scene.scan_align_settings
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()
