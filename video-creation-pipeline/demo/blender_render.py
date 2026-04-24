"""Blender --background render script.

Invoked by pipeline.py as:

    blender --background --python blender_render.py -- \
        --config /path/to/config.json --out-dir /path/to/frames

Builds a minimal procedural scene (shape + material + camera + light +
rotation keyframes), renders frames with Eevee, writes PNG sequence.
"""

import argparse
import json
import math
import sys
from pathlib import Path

import bpy  # only available inside Blender

SHAPE_CTORS = {
    "cube": lambda: bpy.ops.mesh.primitive_cube_add(size=2),
    "sphere": lambda: bpy.ops.mesh.primitive_uv_sphere_add(radius=1.2),
    "cone": lambda: bpy.ops.mesh.primitive_cone_add(radius1=1.2, depth=2),
    "torus": lambda: bpy.ops.mesh.primitive_torus_add(major_radius=1.2, minor_radius=0.4),
}


def parse_args() -> argparse.Namespace:
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, required=True)
    return ap.parse_args(argv)


def reset_scene() -> None:
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)


def add_shape(shape: str, color_rgb: list[float]):
    SHAPE_CTORS[shape]()
    obj = bpy.context.active_object
    mat = bpy.data.materials.new(name="shape_material")
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (*color_rgb, 1.0)
    bsdf.inputs["Roughness"].default_value = 0.4
    obj.data.materials.append(mat)
    return obj


def add_camera_and_light() -> None:
    bpy.ops.object.camera_add(location=(5, -5, 3.5), rotation=(math.radians(65), 0, math.radians(45)))
    bpy.context.scene.camera = bpy.context.active_object
    bpy.ops.object.light_add(type="SUN", location=(4, -4, 6))
    bpy.context.active_object.data.energy = 3.0


def set_background(scene: bpy.types.Scene, rgb: list[float]) -> None:
    world = scene.world or bpy.data.worlds.new("World")
    scene.world = world
    world.use_nodes = True
    bg = world.node_tree.nodes["Background"]
    bg.inputs["Color"].default_value = (*rgb, 1.0)
    bg.inputs["Strength"].default_value = 1.2


def animate_rotation(obj, total_frames: int) -> None:
    obj.rotation_euler = (0, 0, 0)
    obj.keyframe_insert("rotation_euler", frame=1)
    obj.rotation_euler = (0, 0, math.radians(360))
    obj.keyframe_insert("rotation_euler", frame=total_frames)
    for fcurve in obj.animation_data.action.fcurves:
        for kp in fcurve.keyframe_points:
            kp.interpolation = "LINEAR"


def configure_render(scene: bpy.types.Scene, out_dir: Path, total_frames: int, fps: int) -> None:
    scene.render.engine = "BLENDER_EEVEE_NEXT" if "BLENDER_EEVEE_NEXT" in {e.identifier for e in bpy.types.RenderSettings.bl_rna.properties["engine"].enum_items} else "BLENDER_EEVEE"
    scene.render.resolution_x = 960
    scene.render.resolution_y = 540
    scene.render.fps = fps
    scene.render.image_settings.file_format = "PNG"
    scene.render.filepath = str(out_dir / "frame_")
    scene.frame_start = 1
    scene.frame_end = total_frames


def main() -> None:
    args = parse_args()
    config = json.loads(args.config.read_text())
    total_frames = max(1, int(config["duration_seconds"] * config["fps"]))

    reset_scene()
    obj = add_shape(config["shape"], config["color_rgb"])
    add_camera_and_light()
    set_background(bpy.context.scene, config["background_rgb"])
    animate_rotation(obj, total_frames)
    configure_render(bpy.context.scene, args.out_dir, total_frames, config["fps"])

    bpy.ops.render.render(animation=True)


if __name__ == "__main__":
    main()
