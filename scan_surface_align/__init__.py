"""
3DPotok Scan Surface Align
Author: Glazyrin Alexey Sergeevich
Studio: 3dpotok.ru
Telegram: @standalone2k
Website: https://3dpotok.ru
License: GPL-3.0-or-later
"""

bl_info = {
    "name": "3DPotok Scan Surface Align",
    "author": "Glazyrin Alexey Sergeevich | 3dpotok.ru",
    "version": (1, 0, 7),
    "blender": (5, 1, 0),
    "location": "View3D > Sidebar > 3DPotok",
    "description": (
        "RU: Выравнивание выделенных поверхностей скана перпендикулярно мировым осям "
        "с сохранением сторон, AUTO ALIGN, TO FLOOR и Quick Align. "
        "EN: Align selected scan surfaces perpendicular to world axes with stored sides, "
        "AUTO ALIGN, TO FLOOR, and Quick Align tools."
    ),
    "doc_url": "https://3dpotok.ru",
    "tracker_url": "https://t.me/standalone2k",
    "support": "COMMUNITY",
    "category": "Mesh",
}

import itertools
from math import atan2, cos, inf, radians

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

AXIS_ICONS = {
    "X": "AXIS_SIDE",
    "Y": "AXIS_FRONT",
    "Z": "AXIS_TOP",
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


def create_analysis_bmesh(obj):
    if obj.mode == "EDIT":
        bm = bmesh.from_edit_mesh(obj.data)
        owned = False
    else:
        bm = bmesh.new()
        bm.from_mesh(obj.data)
        owned = True

    bm.faces.ensure_lookup_table()
    bm.faces.index_update()
    bm.normal_update()
    return bm, owned


def object_world_diagonal(obj):
    world_corners = [obj.matrix_world @ Vector(corner) for corner in obj.bound_box]
    min_corner = Vector((
        min(corner.x for corner in world_corners),
        min(corner.y for corner in world_corners),
        min(corner.z for corner in world_corners),
    ))
    max_corner = Vector((
        max(corner.x for corner in world_corners),
        max(corner.y for corner in world_corners),
        max(corner.z for corner in world_corners),
    ))
    return max((max_corner - min_corner).length, 1e-4)


def object_world_bounds_center(obj):
    world_corners = [obj.matrix_world @ Vector(corner) for corner in obj.bound_box]
    center = Vector((0.0, 0.0, 0.0))
    for corner in world_corners:
        center += corner
    return center / max(len(world_corners), 1)


def object_lowest_world_z(obj):
    mesh = obj.data
    if obj.mode == "EDIT":
        bm = bmesh.from_edit_mesh(mesh)
        verts = bm.verts
        return min((obj.matrix_world @ vert.co).z for vert in verts)
    return min((obj.matrix_world @ vertex.co).z for vertex in mesh.vertices)


def object_world_vertex_positions(obj):
    if obj.mode == "EDIT":
        bm = bmesh.from_edit_mesh(obj.data)
        return [obj.matrix_world @ vert.co for vert in bm.verts]
    return [obj.matrix_world @ vertex.co for vertex in obj.data.vertices]


def selected_face_plane_z(obj):
    if obj.mode != "EDIT":
        raise ValueError("Selected polygon plane is available only in Edit Mode.")

    bm = bmesh.from_edit_mesh(obj.data)
    bm.faces.ensure_lookup_table()
    selected_faces = [face for face in bm.faces if face.select]

    if not selected_faces:
        raise ValueError("Select at least one polygon in Edit Mode for TO FLOOR.")

    total_area = 0.0
    z_sum = 0.0
    for face in selected_faces:
        area = max(face.calc_area(), 1e-8)
        center_world = obj.matrix_world @ face.calc_center_median()
        z_sum += center_world.z * area
        total_area += area

    return z_sum / max(total_area, 1e-8)


def selected_face_floor_target(obj, plane_center, plane_normal):
    normal = plane_normal.normalized()
    vertices_world = object_world_vertex_positions(obj)
    if not vertices_world:
        return Vector((0.0, 0.0, -1.0))

    positive_extent = 0.0
    negative_extent = 0.0
    for vertex_world in vertices_world:
        distance = (vertex_world - plane_center).dot(normal)
        positive_extent = max(positive_extent, distance)
        negative_extent = max(negative_extent, -distance)

    if positive_extent > negative_extent:
        return Vector((0.0, 0.0, 1.0))
    return Vector((0.0, 0.0, -1.0))


def translate_object_world_z(context, obj, delta_z):
    if abs(delta_z) < 1e-8:
        return

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

        # Apply the offset in world space so parenting and transformed matrices
        # do not invert the movement direction.
        obj.matrix_world = Matrix.Translation((0.0, 0.0, delta_z)) @ obj.matrix_world
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


def collect_flat_surface_candidates(obj, angle_limit_degrees=8.0, plane_tolerance_ratio=0.006):
    if not obj or obj.type != "MESH":
        raise ValueError("Active object must be a mesh.")

    bm, owned = create_analysis_bmesh(obj)
    normal_matrix = obj.matrix_world.to_3x3().inverted().transposed()
    cosine_limit = cos(radians(angle_limit_degrees))
    plane_tolerance = max(object_world_diagonal(obj) * plane_tolerance_ratio, 1e-5)
    total_area = sum(max(face.calc_area(), 1e-8) for face in bm.faces)
    visited = set()
    candidates = []

    try:
        for seed_face in sorted(bm.faces, key=lambda face: face.calc_area(), reverse=True):
            if seed_face.index in visited:
                continue

            seed_normal = (normal_matrix @ seed_face.normal).normalized()
            seed_center = obj.matrix_world @ seed_face.calc_center_median()
            stack = [seed_face]
            cluster_indices = []
            area_sum = 0.0
            normal_sum = Vector((0.0, 0.0, 0.0))
            center_sum = Vector((0.0, 0.0, 0.0))
            alignment_sum = 0.0

            while stack:
                face = stack.pop()
                if face.index in visited:
                    continue

                area = max(face.calc_area(), 1e-8)
                normal_world = (normal_matrix @ face.normal).normalized()
                center_world = obj.matrix_world @ face.calc_center_median()

                if normal_world.dot(seed_normal) < cosine_limit:
                    continue
                if abs((center_world - seed_center).dot(seed_normal)) > plane_tolerance:
                    continue

                visited.add(face.index)
                cluster_indices.append(face.index)
                area_sum += area
                normal_sum += normal_world * area
                center_sum += center_world * area
                alignment_sum += max(normal_world.dot(seed_normal), 0.0) * area

                for edge in face.edges:
                    for linked_face in edge.link_faces:
                        if linked_face.index not in visited:
                            stack.append(linked_face)

            if not cluster_indices or normal_sum.length < 1e-8:
                continue

            average_alignment = alignment_sum / max(area_sum, 1e-8)
            area_ratio = area_sum / max(total_area, 1e-8)
            flatness_score = area_sum * (average_alignment ** 2)

            candidates.append({
                "faces": cluster_indices,
                "area": area_sum,
                "area_ratio": area_ratio,
                "normal": normal_sum.normalized(),
                "center": center_sum / area_sum,
                "score": flatness_score,
            })
    finally:
        if owned:
            bm.free()

    if not candidates:
        raise ValueError("Could not detect a flat support surface on this mesh.")

    candidates.sort(key=lambda item: (item["score"], item["area"]), reverse=True)
    return candidates


def choose_print_alignment_candidates(obj):
    candidates = collect_flat_surface_candidates(obj)
    primary = candidates[0]
    secondary = None
    best_secondary_score = -inf

    for candidate in candidates[1:]:
        orthogonality = 1.0 - abs(primary["normal"].dot(candidate["normal"]))
        if orthogonality < 0.35:
            continue
        secondary_score = candidate["area"] * orthogonality
        if secondary_score > best_secondary_score:
            secondary = candidate
            best_secondary_score = secondary_score

    return primary, secondary


def rotation_for_print_alignment(primary_normal, secondary_normal=None):
    base_target = Vector((0.0, 0.0, -1.0))
    base_rotation = primary_normal.rotation_difference(base_target).to_matrix()
    secondary_axis = None

    if secondary_normal is None:
        return base_rotation, secondary_axis

    rotated_secondary = base_rotation @ secondary_normal
    projected = Vector((rotated_secondary.x, rotated_secondary.y, 0.0))
    if projected.length < 1e-6:
        return base_rotation, secondary_axis

    if abs(projected.x) >= abs(projected.y):
        target_angle = 0.0 if projected.x >= 0.0 else 3.141592653589793
        secondary_axis = "X"
    else:
        target_angle = 1.5707963267948966 if projected.y >= 0.0 else -1.5707963267948966
        secondary_axis = "Y"

    current_angle = atan2(projected.y, projected.x)
    z_rotation = Matrix.Rotation(target_angle - current_angle, 3, "Z")
    return z_rotation @ base_rotation, secondary_axis


def auto_align_for_print(context, obj, apply_mode="ROTATE", center_origin=True):
    primary, secondary = choose_print_alignment_candidates(obj)
    rotation, secondary_axis = rotation_for_print_alignment(
        primary["normal"],
        secondary["normal"] if secondary else None,
    )
    pivot = (primary["center"] + secondary["center"]) * 0.5 if secondary else primary["center"]
    apply_world_rotation(context, obj, rotation, pivot, apply_mode, center_origin)
    return primary, secondary, secondary_axis


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
    auto_flip_axis: EnumProperty(
        name="Auto Flip Axis",
        items=[
            ("X", "X", "Flip around world X"),
            ("Y", "Y", "Flip around world Y"),
        ],
        default="X",
    )


class SCANALIGN_OT_set_axis(Operator):
    bl_idname = "scan_align.set_axis"
    bl_label = "Set Axis"
    bl_description = "Set the target axis for the stored side"
    bl_options = {"REGISTER", "UNDO"}

    side: IntProperty(default=1, min=1, max=2)
    axis: EnumProperty(name="Axis", items=AXIS_ITEMS, default="Z")

    def execute(self, context):
        settings = context.scene.scan_align_settings
        setattr(settings, f"side{self.side}_axis", self.axis)
        self.report({"INFO"}, f"Side {self.side} target axis set to {self.axis}.")
        return {"FINISHED"}


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
    bl_description = "Align stored sides manually or auto-detect the best print support orientation"
    bl_options = {"REGISTER", "UNDO"}

    auto_axes: BoolProperty(default=False)

    def execute(self, context):
        settings = context.scene.scan_align_settings
        if self.auto_axes:
            obj = ensure_mesh_object(context, use_target=False) or ensure_mesh_object(context, use_target=True)
        else:
            obj = ensure_mesh_object(context, use_target=True)

        if not obj:
            self.report({"ERROR"}, "No active mesh object is available for alignment.")
            return {"CANCELLED"}

        try:
            if self.auto_axes:
                primary, secondary, secondary_axis = auto_align_for_print(
                    context=context,
                    obj=obj,
                    apply_mode=settings.apply_mode,
                    center_origin=settings.center_origin,
                )
                settings.target_object = obj
                settings.side1_faces = serialize_faces(primary["faces"])
                settings.side1_axis = "Z"
                settings.auto_flip_axis = secondary_axis or "X"
                if secondary:
                    settings.side2_faces = serialize_faces(secondary["faces"])
                    settings.side2_axis = secondary_axis or "Y"
                else:
                    settings.side2_faces = ""
            else:
                side1_faces = deserialize_faces(settings.side1_faces)
                side2_faces = deserialize_faces(settings.side2_faces)

                if not side1_faces:
                    self.report({"ERROR"}, "Store Side 1 faces first.")
                    return {"CANCELLED"}

                axis1 = settings.side1_axis
                axis2 = settings.side2_axis
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

        if self.auto_axes:
            if secondary:
                self.report({"INFO"}, f"Auto-aligned mesh for printing using the main flat side and secondary {secondary_axis} guide.")
            else:
                self.report({"INFO"}, "Auto-aligned mesh for printing using the main flat support side.")
        else:
            side2_faces = deserialize_faces(settings.side2_faces)
            if side2_faces:
                self.report({"INFO"}, f"Aligned Side 1 to {settings.side1_axis} and Side 2 to {settings.side2_axis}.")
            else:
                self.report({"INFO"}, f"Aligned Side 1 to {settings.side1_axis}.")
        return {"FINISHED"}


class SCANALIGN_OT_flip(Operator):
    bl_idname = "scan_align.flip"
    bl_label = "Flip"
    bl_description = "Flip the active mesh 180 degrees after AUTO ALIGN"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        obj = context.object
        return obj and obj.type == "MESH"

    def execute(self, context):
        settings = context.scene.scan_align_settings
        obj = ensure_mesh_object(context, use_target=False) or ensure_mesh_object(context, use_target=True)

        if not obj:
            self.report({"ERROR"}, "No active mesh object is available for flip.")
            return {"CANCELLED"}

        axis_name = settings.auto_flip_axis or "X"
        pivot = object_world_bounds_center(obj)
        rotation = Matrix.Rotation(radians(180.0), 3, axis_name)

        try:
            apply_world_rotation(
                context=context,
                obj=obj,
                rotation=rotation,
                pivot_world=pivot,
                apply_mode=settings.apply_mode,
                center_origin=settings.center_origin,
            )
        except ValueError as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}
        except RuntimeError as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}

        self.report({"INFO"}, f"Flipped mesh 180 degrees around {axis_name}.")
        return {"FINISHED"}


class SCANALIGN_OT_to_floor(Operator):
    bl_idname = "scan_align.to_floor"
    bl_label = "To Floor"
    bl_description = "Move the mesh to Z=0 using the lowest point in Object Mode or lay the selected polygon plane onto the floor in Edit Mode"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        obj = context.object
        return obj and obj.type == "MESH" and obj.mode in {"OBJECT", "EDIT"}

    def execute(self, context):
        settings = context.scene.scan_align_settings
        obj = ensure_mesh_object(context, use_target=False) or ensure_mesh_object(context, use_target=True)

        if not obj:
            self.report({"ERROR"}, "No active mesh object is available for TO FLOOR.")
            return {"CANCELLED"}

        try:
            if obj.mode == "EDIT":
                selected_faces = get_selected_face_indices(obj)
                if not selected_faces:
                    raise ValueError("Select at least one polygon in Edit Mode for TO FLOOR.")

                plane_normal, plane_center, _ = collect_face_stats(obj, selected_faces)
                target_normal = selected_face_floor_target(obj, plane_center, plane_normal)
                rotation = plane_normal.rotation_difference(target_normal).to_matrix()

                apply_world_rotation(
                    context=context,
                    obj=obj,
                    rotation=rotation,
                    pivot_world=plane_center,
                    apply_mode=settings.apply_mode,
                    center_origin=settings.center_origin,
                )

                source_z = selected_face_plane_z(obj)
            else:
                source_z = object_lowest_world_z(obj)

            translate_object_world_z(context, obj, -source_z)

            # Verify against the actual resulting position and correct any mismatch.
            if obj.mode == "EDIT":
                correction_z = selected_face_plane_z(obj)
            else:
                correction_z = object_lowest_world_z(obj)

            if abs(correction_z) > 1e-5:
                translate_object_world_z(context, obj, -correction_z)
        except ValueError as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}
        except RuntimeError as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}

        if obj.mode == "EDIT":
            self.report({"INFO"}, "Moved the selected polygon plane to the floor.")
        else:
            self.report({"INFO"}, "Moved the mesh to the floor using the lowest vertex.")
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
    bl_label = "3DPotok Scan Surface Align"
    bl_idname = "SCANALIGN_PT_main_panel"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "3DPotok"

    def draw_axis_buttons(self, layout, settings, side):
        current_axis = getattr(settings, f"side{side}_axis")
        row = layout.row(align=True)
        for axis_name in ("X", "Y", "Z"):
            operator = row.operator(
                "scan_align.set_axis",
                text=axis_name,
                icon=AXIS_ICONS[axis_name],
                depress=(current_axis == axis_name),
            )
            operator.side = side
            operator.axis = axis_name

    def draw_side_box(self, layout, settings, side):
        faces_data = getattr(settings, f"side{side}_faces")
        face_count = len(deserialize_faces(faces_data))

        box = layout.box()
        box.label(text=f"Select Faces From Side {side}")
        box.label(text=f"Stored Faces: {face_count}")
        box.label(text=f"Make Side {side} Perpendicular To:")

        self.draw_axis_buttons(box, settings, side)

        row = box.row(align=True)
        store = row.operator("scan_align.store_side", text="Store Selected Faces", icon="IMPORT")
        store.side = side
        select = row.operator("scan_align.select_side", text="", icon="RESTRICT_SELECT_OFF")
        select.side = side
        clear = row.operator("scan_align.clear_side", text="", icon="TRASH")
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
        floor_row = transform_box.row(align=True)
        floor_row.scale_y = 1.05
        floor_row.operator("scan_align.to_floor", text="TO FLOOR", icon="IMPORT")
        floor_row.operator("scan_align.flip", text="FLIP", icon="FILE_REFRESH")
        transform_box.label(text=f"AUTO ALIGN analyzes the active mesh for print support")
        transform_box.label(text=f"FLIP uses {settings.auto_flip_axis} after AUTO ALIGN")
        transform_box.label(text="TO FLOOR: object lowest vertex / edit selected polygon plane")

        quick_box = layout.box()
        quick_box.label(text="Quick Align Current Selection")
        quick_row = quick_box.row(align=True)
        quick_row.operator("scan_align.quick_align_selection", text="Auto", icon="ORIENTATION_GLOBAL").axis = "AUTO"
        quick_row.operator("scan_align.quick_align_selection", text="X", icon=AXIS_ICONS["X"]).axis = "X"
        quick_row.operator("scan_align.quick_align_selection", text="Y", icon=AXIS_ICONS["Y"]).axis = "Y"
        quick_row.operator("scan_align.quick_align_selection", text="Z", icon=AXIS_ICONS["Z"]).axis = "Z"
        quick_box.label(text="Press X / Y / Z again to flip 180 degrees")

        help_box = layout.box()
        help_box.label(text="Hotkeys")
        help_box.label(text="Ctrl+Alt+1 / 2: Store Side 1 / Side 2")
        help_box.label(text="Ctrl+Alt+X / Y / Z: Quick Align Selection")
        help_box.label(text="Ctrl+Alt+A: ALIGN  |  Ctrl+Shift+Alt+A: AUTO ALIGN")


classes = (
    SCANALIGN_PG_settings,
    SCANALIGN_OT_set_axis,
    SCANALIGN_OT_store_side,
    SCANALIGN_OT_select_side,
    SCANALIGN_OT_clear_side,
    SCANALIGN_OT_auto_axes,
    SCANALIGN_OT_align,
    SCANALIGN_OT_flip,
    SCANALIGN_OT_to_floor,
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
