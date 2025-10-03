'''Copyright (C) 2025 Aperturia FX
Created by Arvo Andre Radik
This file is part of Aperturia FX
Aperturia FX is free software; you can redistribute it and/or
modify it under the terms of the GNU General Public License
as published by the Free Software Foundation; either version 3
of the License, or (at your option) any later version.


This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
GNU General Public License for more details.


You should have received a copy of the GNU General Public License
along with this program; if not, see https://www.gnu.org
/licenses.'''

bl_info = {
    "name": "Aperturia FX Pro",
    "author": "Radikal",
    "version": (1, 0, 2),
    "blender": (4, 5, 0),
    "location": "Node Editor > Add > Compositor > Aperturia FX Pro",
    "description": "Fast lens effect node for Compositor",
    "category": "Compositing"
}

import bpy
import nodeitems_utils
import os
import json
import mathutils
from nodeitems_utils import NodeCategory, NodeItem

addon_dir = os.path.dirname(__file__)
texture_dir = os.path.join(addon_dir, "textures")

fingerprint_textures = [
    "AperturiaFX_Fingerprints_Light.png",
    "AperturiaFX_Fingerprints_Heavy.png",
    "AperturiaFX_Smudges_Light.png",
    "AperturiaFX_Smudges_Heavy.png"
]

GROUP_NAME = "Aperturia FX Pro"

INPUT_INDEX_MAP = {
    "noise_toggle": 2,
    "noise_general": 3,
    "noise_shadow_amount": 4,
    "noise_advanced_toggle": 5,
    "noise_profile": 6,
    "noise_scale": 7,
    "noise_general_secondary": 8,
    "noise_blend": 9,
    "color_noise_intensity": 10,
    "color_noise_scale": 11,
    "color_noise_blend": 12,
    "shadow_mask_lift": 13,
    "shadow_mask_gamma": 14,
    "shadow_mask_gain": 15,
    "glare_toggle": 16,
    "glare_intensity": 17,
    "glare_bloom": 18,
    # 19 is image input and intentionally skipped
    "vignette_toggle": 20,
    "vignette_amount": 21,
    "vignette_intensity": 22,
    "vignette_softness": 23,
    "compression_toggle": 24,
    "compression_lens_distortion": 25,
    "compression_lens_dispersion": 26,
    "compression_pixelation_size": 27,
    "compression_intensity": 28,
    "compression_softness": 29,
    "compression_noise_scale": 30,
    "compression_noise_blend": 31,
    "smudge_toggle": 32,
    "smudge_seed": 33,
    "smudge_fingerprint_amount": 34,
    "smudge_fingerprint_intensity": 35,
    "smudge_amount": 36,
    "smudge_intensity": 37,
    "advanced_shadow_mask_optional_toggle": 38,
}

PRESET_KEYS = list(INPUT_INDEX_MAP.keys())

def on_file_load(scene):
    bulk_load_images()
    
    ensure_aperturia_textures()
    check_aperturia_integrity()

    group_missing = "Aperturia FX Pro" not in bpy.data.node_groups
    was_restored = check_aperturia_integrity()

    if group_missing and not was_restored:
        group, node_map = create_custom_node_group()
        
def get_presets_path():
    return os.path.join(os.path.dirname(__file__), "presets.json")

def load_presets():
    path = get_presets_path()
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            text = f.read().strip()
            if not text:
                return {}
            return json.loads(text)
    except (json.JSONDecodeError, ValueError):
        # Invalid JSON; fail safe
        return {}

def save_presets(presets: dict):
    path = get_presets_path()
    with open(path, "w", encoding="utf-8") as f:
        json.dump(presets, f, indent=4)
        
def capture_nodegroup_values():
    group_name = "Aperturia FX Pro"
    if group_name not in bpy.data.node_groups:
        return {}
    ng = bpy.data.node_groups[group_name]
    values = {}
    for key, socket_name in SOCKET_MAP.items():
        for sock in ng.inputs:
            if sock.name == socket_name:
                try:
                    values[key] = sock.default_value
                except Exception:
                    values[key] = None
    return values

def get_scene_compositor_tree():
    scene = bpy.context.scene
    if not scene:
        return None
    if not scene.use_nodes:
        scene.use_nodes = True
    return scene.node_tree

def find_group_node_in_scene():
    nt = get_scene_compositor_tree()
    if not nt:
        return None
    # Preferred: find a Group node referencing the specific node group
    for n in nt.nodes:
        if n.type == 'GROUP' and n.node_tree and n.node_tree.name == GROUP_NAME:
            return n
    # Fallback: find by node name (label) if user renamed the group reference
    node_by_name = nt.nodes.get(GROUP_NAME)
    if node_by_name and node_by_name.type == 'GROUP':
        return node_by_name
    return None

def capture_node_values_from_scene():
    node = find_group_node_in_scene()
    if not node:
        return {}
    values = {}
    for key, idx in INPUT_INDEX_MAP.items():
        try:
            values[key] = node.inputs[idx].default_value
        except Exception:
            values[key] = None
    return values

def apply_preset_to_scene_node(preset_name: str):
    presets = load_presets()
    if preset_name not in presets:
        return
    node = find_group_node_in_scene()
    if not node:
        return
    values = presets[preset_name]
    for key, idx in INPUT_INDEX_MAP.items():
        if key in values:
            try:
                node.inputs[idx].default_value = values[key]
            except Exception:
                # Ignore incompatible types (e.g., image inputs or mismatched types)
                pass

# === TEXTURE SETUP ===
#--COLOR NOISE
def reset_color_noise_texture():
    tex_name = "FX_AptColornoise"
    if tex_name in bpy.data.textures:
        try:
            bpy.data.textures[tex_name].type = 'CLOUDS'
            tex = bpy.data.textures[tex_name]
        except:
            bpy.data.textures.remove(bpy.data.textures[tex_name])
            tex = bpy.data.textures.new(tex_name, type='CLOUDS')
    else:
        tex = bpy.data.textures.new(tex_name, type='CLOUDS')

    tex.noise_basis = 'IMPROVED_PERLIN'
    tex.cloud_type = 'COLOR'
    tex.noise_depth = 24
    tex.use_color_ramp = True

    ramp = tex.color_ramp
    while len(ramp.elements) > 2:
        ramp.elements.remove(ramp.elements[-1])
    while len(ramp.elements) < 2:
        ramp.elements.new(0.5)

    ramp.elements[0].position = 0.0
    ramp.elements[0].color = (1, 0, 0, 1)
    ramp.elements[1].position = 1.0
    ramp.elements[1].color = (0, 1, 1, 1)
    
#--COMPRESSION NOISE 1.1
def reset_comp_tex_11_texture():
    tex_name = "FX_AptNoise1.1"
    if tex_name in bpy.data.textures:
        try:
            bpy.data.textures[tex_name].type = 'CLOUDS'
            tex = bpy.data.textures[tex_name]
        except:
            bpy.data.textures.remove(bpy.data.textures[tex_name])
            tex = bpy.data.textures.new(tex_name, type='CLOUDS')
    else:
        tex = bpy.data.textures.new(tex_name, type='CLOUDS')

    tex.noise_basis = 'BLENDER_ORIGINAL'
    tex.noise_type = 'SOFT_NOISE'
    tex.noise_scale = 0.15
    tex.noise_depth = 0
    tex.nabla = 0.1
    tex.use_color_ramp = True

    ramp = tex.color_ramp
    while len(ramp.elements) > 2:
        ramp.elements.remove(ramp.elements[-1])
    while len(ramp.elements) < 2:
        ramp.elements.new(0.5)

    ramp.elements[0].position = 0.0
    ramp.elements[0].color = (1, 1, 1, 1)
    ramp.elements[1].position = 1.0
    ramp.elements[1].color = (0, 0, 0, 0)

#--COMPRESSION NOISE 1.2
def reset_comp_tex_12_texture():
    tex_name = "FX_AptNoise1.2"
    if tex_name in bpy.data.textures:
        try:
            bpy.data.textures[tex_name].type = 'MUSGRAVE'
            tex = bpy.data.textures[tex_name]
        except:
            bpy.data.textures.remove(bpy.data.textures[tex_name])
            tex = bpy.data.textures.new(tex_name, type='MUSGRAVE')
    else:
        tex = bpy.data.textures.new(tex_name, type='MUSGRAVE')

    tex.noise_basis = 'VORONOI_F1'
    tex.noise_scale = 0.15
    tex.nabla = 0.1
    
def reset_comp_tex_21_texture():
    tex_name = "FX_AptNoise2.1"
    if tex_name in bpy.data.textures:
        try:
            bpy.data.textures[tex_name].type = 'MUSGRAVE'
            tex = bpy.data.textures[tex_name]
        except:
            bpy.data.textures.remove(bpy.data.textures[tex_name])
            tex = bpy.data.textures.new(tex_name, type='MUSGRAVE')
    else:
        tex = bpy.data.textures.new(tex_name, type='MUSGRAVE')
        
    tex.noise_basis = 'VORONOI_F1'
    tex.noise_scale = 1.0
    tex.nabla = 0.1
    
def reset_comp_tex_22_texture():
    tex_name = "FX_AptNoise2.2"
    if tex_name in bpy.data.textures:
        try:
            bpy.data.textures[tex_name].type = 'MUSGRAVE'
            tex = bpy.data.textures[tex_name]
        except:
            bpy.data.textures.remove(bpy.data.textures[tex_name])
            tex = bpy.data.textures.new(tex_name, type='MUSGRAVE')
    else:
        tex = bpy.data.textures.new(tex_name, type='MUSGRAVE')
        
    tex.noise_basis = 'VORONOI_F1'
    tex.musgrave_type = 'RIDGED_MULTIFRACTAL'
    tex.noise_scale = 1.0
    tex.nabla = 0.1
    tex.dimension_max = 2.0
    tex.lacunarity = 6.0
    tex.octaves = 8.0
    
def reset_comp_tex_31_texture():
    tex_name = "FX_AptNoise3.1"
    if tex_name in bpy.data.textures:
        try:
            bpy.data.textures[tex_name].type = 'VORONOI'
            tex = bpy.data.textures[tex_name]
        except:
            bpy.data.textures.remove(bpy.data.textures[tex_name])
            tex = bpy.data.textures.new(tex_name, type='VORONOI')
    else:
        tex = bpy.data.textures.new(tex_name, type='VORONOI')
        
    tex.distance_metric = 'CHEBYCHEV'
    tex.color_mode = 'POSITION_OUTLINE_INTENSITY'
    tex.intensity = 1.0
    tex.noise_scale = 0.1
    tex.nabla = 0.03
    tex.weight_1 = 2.0
    tex.weight_2 = 1.5
    tex.weight_3 = 1.0
    tex.weight_4 = 0.5
    
def reset_comp_tex_32_texture():
    tex_name = "FX_AptNoise3.2"
    if tex_name in bpy.data.textures:
        try:
            bpy.data.textures[tex_name].type = 'CLOUDS'
            tex = bpy.data.textures[tex_name]
        except:
            bpy.data.textures.remove(bpy.data.textures[tex_name])
            tex = bpy.data.textures.new(tex_name, type='CLOUDS')
    else:
        tex = bpy.data.textures.new(tex_name, type='CLOUDS')
    
    tex.cloud_type = 'COLOR'
    tex.noise_basis = 'VORONOI_F1'
    tex.noise_type = 'HARD_NOISE'
    tex.noise_scale = 1.0
    tex.noise_depth = 0
    tex.nabla = 0.1

def reset_comp_tex_41_texture():
    tex_name = "FX_AptNoise4.1"
    if tex_name in bpy.data.textures:
        try:
            bpy.data.textures[tex_name].type = 'WOOD'
            tex = bpy.data.textures[tex_name]
        except:
            bpy.data.textures.remove(bpy.data.textures[tex_name])
            tex = bpy.data.textures.new(tex_name, type='WOOD')
    else:
        tex = bpy.data.textures.new(tex_name, type='WOOD')

    tex.noise_scale = 0.1
    tex.use_color_ramp = True
    ramp = tex.color_ramp
    
    while len(ramp.elements) > 2:
        ramp.elements.remove(ramp.elements[-1])
    while len(ramp.elements) < 2:
        ramp.elements.new(0.5)

    ramp.elements[0].position = 0.0
    ramp.elements[0].color = (0, 0, 0, 0)

    ramp.elements[1].position = 0.195
    ramp.elements[1].color = (1, 1, 1, 1)
    
def reset_comp_tex_42_texture():
    tex_name = "FX_AptNoise4.2"
    if tex_name in bpy.data.textures:
        try:
            bpy.data.textures[tex_name].type = 'DISTORTED_NOISE'
            tex = bpy.data.textures[tex_name]
        except:
            bpy.data.textures.remove(bpy.data.textures[tex_name])
            tex = bpy.data.textures.new(tex_name, type='DISTORTED_NOISE')
    else:
        tex = bpy.data.textures.new(tex_name, type='DISTORTED_NOISE')

    tex.noise_basis = 'BLENDER_ORIGINAL'
    tex.noise_distortion = 'VORONOI_F1'
    tex.noise_scale = 1.0
    tex.nabla = 0.1
    
def reset_comp_tex_51_texture():
    tex_name = "FX_AptNoise5.1"
    if tex_name in bpy.data.textures:
        try:
            bpy.data.textures[tex_name].type = 'DISTORTED_NOISE'
            tex = bpy.data.textures[tex_name]
        except:
            bpy.data.textures.remove(bpy.data.textures[tex_name])
            tex = bpy.data.textures.new(tex_name, type='DISTORTED_NOISE')
    else:
        tex = bpy.data.textures.new(tex_name, type='DISTORTED_NOISE')

    tex.noise_basis = 'BLENDER_ORIGINAL'
    tex.noise_distortion = 'BLENDER_ORIGINAL'
    tex.noise_scale = 0.1
    tex.nabla = 0.03
    tex.use_color_ramp = True
    ramp = tex.color_ramp
    
    while len(ramp.elements) > 2:
        ramp.elements.remove(ramp.elements[-1])
    while len(ramp.elements) < 2:
        ramp.elements.new(0.5)

    ramp.elements[0].position = 0.0
    ramp.elements[0].color = (0, 0, 0, 0)

    ramp.elements[1].position = 0.195
    ramp.elements[1].color = (1, 1, 1, 1)


    
def reset_comp_tex_52_texture():
    tex_name = "FX_AptNoise5.2"
    if tex_name in bpy.data.textures:
        try:
            bpy.data.textures[tex_name].type = 'DISTORTED_NOISE'
            tex = bpy.data.textures[tex_name]
        except:
            bpy.data.textures.remove(bpy.data.textures[tex_name])
            tex = bpy.data.textures.new(tex_name, type='DISTORTED_NOISE')
    else:
        tex = bpy.data.textures.new(tex_name, type='DISTORTED_NOISE')

    tex.noise_basis = 'BLENDER_ORIGINAL'
    tex.noise_distortion = 'VORONOI_F1'
    tex.noise_scale = 1.0
    tex.nabla = 0.1
    
def reset_comp_tex_61_texture():
    tex_name = "FX_AptNoise6.1"
    if tex_name in bpy.data.textures:
        try:
            bpy.data.textures[tex_name].type = 'DISTORTED_NOISE'
            tex = bpy.data.textures[tex_name]
        except:
            bpy.data.textures.remove(bpy.data.textures[tex_name])
            tex = bpy.data.textures.new(tex_name, type='DISTORTED_NOISE')
    else:
        tex = bpy.data.textures.new(tex_name, type='DISTORTED_NOISE')

    tex.noise_basis = 'BLENDER_ORIGINAL'
    tex.noise_distortion = 'BLENDER_ORIGINAL'
    tex.noise_scale = 0.1
    tex.nabla = 0.03
    tex.use_color_ramp = True
    ramp = tex.color_ramp
    
    while len(ramp.elements) > 2:
        ramp.elements.remove(ramp.elements[-1])
    while len(ramp.elements) < 2:
        ramp.elements.new(0.5)

    ramp.elements[0].position = 0.0
    ramp.elements[0].color = (0, 0, 0, 0)

    ramp.elements[1].position = 0.195
    ramp.elements[1].color = (1, 1, 1, 1)
    
def reset_comp_tex_62_texture():
    tex_name = "FX_AptNoise6.2"
    if tex_name in bpy.data.textures:
        try:
            bpy.data.textures[tex_name].type = 'VORONOI'
            tex = bpy.data.textures[tex_name]
        except:
            bpy.data.textures.remove(bpy.data.textures[tex_name])
            tex = bpy.data.textures.new(tex_name, type='VORONOI')
    else:
        tex = bpy.data.textures.new(tex_name, type='VORONOI')
        
    tex.distance_metric = 'MINKOVSKY_HALF'
    tex.color_mode = 'INTENSITY'
    tex.noise_intensity = 1.0
    tex.noise_scale = 1.0
    tex.nabla = 0.1
    tex.weight_1 = 1.0
    tex.weight_2 = 0.0
    tex.weight_3 = 0.0
    tex.weight_4 = 0.0
    
def reset_comp_texture():
    tex_name = "FX_AptCompression"
    if tex_name in bpy.data.textures:
        try:
            bpy.data.textures[tex_name].type = 'DISTORTED_NOISE'
            tex = bpy.data.textures[tex_name]
        except:
            bpy.data.textures.remove(bpy.data.textures[tex_name])
            tex = bpy.data.textures.new(tex_name, type='DISTORTED_NOISE')
    else:
        tex = bpy.data.textures.new(tex_name, type='DISTORTED_NOISE')
        
    tex.use_color_ramp = True
    ramp = tex.color_ramp
    
    while len(ramp.elements) > 2:
        ramp.elements.remove(ramp.elements[-1])
    while len(ramp.elements) < 2:
        ramp.elements.new(0.5)

    ramp.elements[0].position = 0.0
    ramp.elements[0].color = (0, 0, 0, 0)

    ramp.elements[1].position = 1.0
    ramp.elements[1].color = (1, 1, 1, 1)


def load_image(filename):
    image_path = os.path.join(texture_dir, filename)

    for img in bpy.data.images:
        if bpy.path.abspath(img.filepath) == bpy.path.abspath(image_path):
            return img

    try:
        image = bpy.data.images.load(image_path)
        image.source = 'FILE'
        return image
    except Exception as e:
        print(f"Failed to load image: {filename}\n{e}")
        return None

def bulk_load_images():
    loaded = {}
    for filename in fingerprint_textures:
        image_path = os.path.join(texture_dir, filename)
        try:
            image = bpy.data.images.load(image_path, check_existing=True)
            image.source = 'FILE'
            loaded[filename] = image
            print(f"[Fingerprint] Loaded: {filename}")
        except Exception as e:
            print(f"[Fingerprint] Failed: {filename} — {e}")
    bpy.context.view_layer.update()  # Force refresh
    for img in loaded.values():
        if img.has_data:
            img.reload()  # Fully initialize
    return loaded

aperturia_textures = [
    ("FX_AptColornoise", reset_color_noise_texture),
    ("FX_AptNoise1.1", reset_comp_tex_11_texture),
    ("FX_AptNoise1.2", reset_comp_tex_12_texture),
    ("FX_AptNoise2.1", reset_comp_tex_21_texture),
    ("FX_AptNoise2.2", reset_comp_tex_22_texture),
    ("FX_AptNoise3.1", reset_comp_tex_31_texture),
    ("FX_AptNoise3.2", reset_comp_tex_32_texture),
    ("FX_AptNoise4.1", reset_comp_tex_41_texture),
    ("FX_AptNoise4.2", reset_comp_tex_42_texture),
    ("FX_AptNoise5.1", reset_comp_tex_51_texture),
    ("FX_AptNoise5.2", reset_comp_tex_52_texture),
    ("FX_AptNoise6.1", reset_comp_tex_61_texture),
    ("FX_AptNoise6.2", reset_comp_tex_62_texture),
    ("FX_AptCompression", reset_comp_texture)
]

def ensure_all_aperturia_textures():
    for tex_name, restore_func in aperturia_textures:
        tex = bpy.data.textures.get(tex_name)
        if not tex:
            print(f"[Restore] Creating missing texture: {tex_name}")
            restore_func()
        else:
            try:
                # Optional: verify type if needed, or refresh logic
                restore_func()
            except Exception as e:
                print(f"[Error] Failed restoring {tex_name}: {e}")

def ensure_aperturia_textures(force=False):
    if force or "FX_AptColornoise" not in bpy.data.textures:
        reset_color_noise_texture()
    if force or "FX_AptNoise1.1" not in bpy.data.textures:
        reset_comp_tex_11_texture()
    if force or "FX_AptNoise1.2" not in bpy.data.textures:
        reset_comp_tex_12_texture()
    if force or "FX_AptNoise2.1" not in bpy.data.textures:
        reset_comp_tex_21_texture()
    if force or "FX_AptNoise2.2" not in bpy.data.textures:
        reset_comp_tex_22_texture()
    if force or "FX_AptNoise3.1" not in bpy.data.textures:
        reset_comp_tex_31_texture()
    if force or "FX_AptNoise3.2" not in bpy.data.textures:
        reset_comp_tex_32_texture()    
    if force or "FX_AptNoise4.1" not in bpy.data.textures:
        reset_comp_tex_41_texture()
    if force or "FX_AptNoise4.2" not in bpy.data.textures:
        reset_comp_tex_42_texture()
    if force or "FX_AptNoise5.1" not in bpy.data.textures:
        reset_comp_tex_51_texture()
    if force or "FX_AptNoise5.2" not in bpy.data.textures:
        reset_comp_tex_52_texture()
    if force or "FX_AptNoise6.1" not in bpy.data.textures:
        reset_comp_tex_61_texture()
    if force or "FX_AptNoise6.2" not in bpy.data.textures:
        reset_comp_tex_62_texture()  
    if force or "FX_AptCompression" not in bpy.data.textures:
        reset_comp_texture()  
        
    bulk_load_images()

def check_aperturia_integrity():
    restored = False

    if "FX_AptColornoise" not in bpy.data.textures or bpy.data.textures["FX_AptColornoise"].type != 'CLOUDS':
        print("Restoring FX_AptColornoise...")
        reset_color_noise_texture()
        restored = True
        
    if "FX_AptNoise1.1" not in bpy.data.textures or bpy.data.textures["FX_AptNoise1.1"].type != 'CLOUDS':
        print("Restoring FX_AptNoise1.1...")
        reset_comp_tex_11_texture()
        restored = True
        
    if "FX_AptNoise1.2" not in bpy.data.textures or bpy.data.textures["FX_AptNoise1.2"].type != 'MUSGRAVE':
        print("Restoring FX_AptNoise1.2...")
        reset_comp_tex_12_texture()
        restored = True
        
    if "FX_AptNoise2.1" not in bpy.data.textures or bpy.data.textures["FX_AptNoise2.1"].type != 'MUSGRAVE':
        print("Restoring FX_AptNoise2.1...")
        reset_comp_tex_21_texture()
        restored = True
    
    if "FX_AptNoise2.2" not in bpy.data.textures or bpy.data.textures["FX_AptNoise2.2"].type != 'MUSGRAVE':
        print("Restoring FX_AptNoise2.2...")
        reset_comp_tex_22_texture()
        restored = True
        
    if "FX_AptNoise3.1" not in bpy.data.textures or bpy.data.textures["FX_AptNoise3.1"].type != 'VORONOI':
        print("Restoring FX_AptNoise3.1...")
        reset_comp_tex_31_texture()
        restored = True
        
    if "FX_AptNoise3.2" not in bpy.data.textures or bpy.data.textures["FX_AptNoise3.2"].type != 'CLOUDS':
        print("Restoring FX_AptNoise3.2...")
        reset_comp_tex_32_texture()
        restored = True
        
    if "FX_AptNoise4.1" not in bpy.data.textures or bpy.data.textures["FX_AptNoise4.1"].type != 'WOOD':
        print("Restoring FX_AptNoise4.1...")
        reset_comp_tex_41_texture()
        restored = True
        
    if "FX_AptNoise4.2" not in bpy.data.textures or bpy.data.textures["FX_AptNoise4.2"].type != 'DISTORTED_NOISE':
        print("Restoring FX_AptNoise4.2...")
        reset_comp_tex_42_texture()
        restored = True
        
    if "FX_AptNoise5.1" not in bpy.data.textures or bpy.data.textures["FX_AptNoise5.1"].type != 'DISTORTED_NOISE':
        print("Restoring FX_AptNoise5.1...")
        reset_comp_tex_51_texture()
        restored = True
        
    if "FX_AptNoise5.2" not in bpy.data.textures or bpy.data.textures["FX_AptNoise5.2"].type != 'DISTORTED_NOISE':
        print("Restoring FX_AptNoise5.2...")
        reset_comp_tex_52_texture()
        restored = True
        
    if "FX_AptNoise6.1" not in bpy.data.textures or bpy.data.textures["FX_AptNoise6.1"].type != 'DISTORTED_NOISE':
        print("Restoring FX_AptNoise6.1...")
        reset_comp_tex_61_texture()
        restored = True
        
    if "FX_AptNoise6.2" not in bpy.data.textures or bpy.data.textures["FX_AptNoise6.2"].type != 'VORONOI':
        print("Restoring FX_AptNoise6.2...")
        reset_comp_tex_62_texture()
        restored = True
        
    if "FX_AptCompression" not in bpy.data.textures or bpy.data.textures["FX_AptCompression"].type != 'DISTORTED_NOISE':
        print("Restoring FX_AptCompression...")
        reset_comp_texture()
        restored = True

    if "Aperturia FX Pro" not in bpy.data.node_groups:
        print("Rebuilding Aperturia FX Pro node group...")
        group, node_map = aperturia_fx_pro_node_group()
        restored = True
        
    if "AptPro VIGNETTE" not in bpy.data.node_groups:
        print("Rebuilding VIGNETTE node group...")
        group, node_map = aptpro_vignette_node_group()
        restored = True
        
    if "AptPro LENS FLARE" not in bpy.data.node_groups:
        print("Rebuilding LENS FLARE node group...")
        group, node_map = aptpro_lens_flare_node_group()
        restored = True
    
    if "AptPro SHADOW MASK" not in bpy.data.node_groups:
        print("Rebuilding SHADOW MASK node group...")
        group, node_map = aptpro_shadow_mask_node_group()
        restored = True
        
    if "AptPro NOISE PATTERNS" not in bpy.data.node_groups:
        print("Rebuilding NOISE PATTERNS node group...")
        group, node_map = aptpro_noise_patterns_node_group()
        restored = True
        
    if "AptPro COMPRESSION EFFECTS" not in bpy.data.node_groups:
        print("Rebuilding COMPRESSION EFFECTS node group...")
        group, node_map = aptpro_compression_effects_node_group()
        restored = True
        
    if "AptPro DIRT" not in bpy.data.node_groups:
        print("Rebuilding DIRT node group...")
        group, node_map = aptpro_dirt_node_group()
        restored = True
        
    if "AptPro ADVANCED NOISE" not in bpy.data.node_groups:
        print("Rebuilding ADVANCED NOISE node group...")
        group, node_map = aptpro_advanced_noise_node_group()
        restored = True
        
    if "Noiseprofile1" not in bpy.data.node_groups:
        print("Rebuilding Noiseprofile1 node group...")
        group, node_map = noiseprofile1_node_group()
        restored = True
        
    if "Noiseprofile2" not in bpy.data.node_groups:
        print("Rebuilding Noiseprofile2 node group...")
        group, node_map = noiseprofile2_node_group()
        restored = True
        
    if "Noiseprofile3" not in bpy.data.node_groups:
        print("Rebuilding Noiseprofile3 node group...")
        group, node_map = noiseprofile3_node_group()
        restored = True
        
    if "Noiseprofile4" not in bpy.data.node_groups:
        print("Rebuilding Noiseprofile4 node group...")
        group, node_map = noiseprofile4_node_group()
        restored = True
        
    if "Noiseprofile5" not in bpy.data.node_groups:
        print("Rebuilding Noiseprofile5 node group...")
        group, node_map = noiseprofile5_node_group()
        restored = True
        
    if "Noiseprofile6" not in bpy.data.node_groups:
        print("Rebuilding Noiseprofile6 node group...")
        group, node_map = noiseprofile6_node_group()
        restored = True
            
    bulk_load_images()
    restore_aperturia()

    return restored

def restore_aperturia():
    print("Restoring all Aperturia textures and node group...")
    ensure_aperturia_textures(force=True)
    group, node_map = create_custom_node_group()
    print("Restore completed.")

def create_custom_node_group():
    def aptpro_lens_flare_node_group():
        """Initialize AptPro LENS FLARE node group"""
        aptpro_lens_flare = bpy.data.node_groups.new(type = 'CompositorNodeTree', name = "AptPro LENS FLARE")

        aptpro_lens_flare.color_tag = 'NONE'
        aptpro_lens_flare.description = ""
        aptpro_lens_flare.default_group_node_width = 140
        aptpro_lens_flare.use_fake_user = True
        # aptpro_lens_flare interface

        # Socket Image
        image_socket = aptpro_lens_flare.interface.new_socket(name="Image", in_out='OUTPUT', socket_type='NodeSocketColor')
        image_socket.default_value = (0.800000011920929, 0.800000011920929, 0.800000011920929, 1.0)
        image_socket.attribute_domain = 'POINT'
        image_socket.default_input = 'VALUE'
        image_socket.structure_type = 'AUTO'

        # Socket Image
        image_socket_1 = aptpro_lens_flare.interface.new_socket(name="Image", in_out='INPUT', socket_type='NodeSocketColor')
        image_socket_1.default_value = (1.0, 1.0, 1.0, 1.0)
        image_socket_1.attribute_domain = 'POINT'
        image_socket_1.default_input = 'VALUE'
        image_socket_1.structure_type = 'AUTO'

        # Socket Emission pass
        emission_pass_socket = aptpro_lens_flare.interface.new_socket(name="Emission pass", in_out='INPUT', socket_type='NodeSocketFloat')
        emission_pass_socket.default_value = 5.0
        emission_pass_socket.min_value = 0.0
        emission_pass_socket.max_value = 1.0000000150474662e+30
        emission_pass_socket.subtype = 'NONE'
        emission_pass_socket.attribute_domain = 'POINT'
        emission_pass_socket.default_input = 'VALUE'
        emission_pass_socket.structure_type = 'AUTO'

        # Socket General Bloom
        general_bloom_socket = aptpro_lens_flare.interface.new_socket(name="General Bloom", in_out='INPUT', socket_type='NodeSocketFloat')
        general_bloom_socket.default_value = 0.5
        general_bloom_socket.min_value = 0.0
        general_bloom_socket.max_value = 1.0
        general_bloom_socket.subtype = 'NONE'
        general_bloom_socket.attribute_domain = 'POINT'
        general_bloom_socket.default_input = 'VALUE'
        general_bloom_socket.structure_type = 'AUTO'

        # Socket Lens Flare intensity
        lens_flare_intensity_socket = aptpro_lens_flare.interface.new_socket(name="Lens Flare intensity", in_out='INPUT', socket_type='NodeSocketFloat')
        lens_flare_intensity_socket.default_value = 0.0
        lens_flare_intensity_socket.min_value = 0.0
        lens_flare_intensity_socket.max_value = 1.0
        lens_flare_intensity_socket.subtype = 'NONE'
        lens_flare_intensity_socket.attribute_domain = 'POINT'
        lens_flare_intensity_socket.default_input = 'VALUE'
        lens_flare_intensity_socket.structure_type = 'AUTO'

        # Initialize aptpro_lens_flare nodes

        # Node GlareOut
        glareout = aptpro_lens_flare.nodes.new("NodeGroupOutput")
        glareout.label = "GlareOut"
        glareout.name = "GlareOut"
        glareout.is_active_output = True

        # Node GlareIn
        glarein = aptpro_lens_flare.nodes.new("NodeGroupInput")
        glarein.label = "GlareIn"
        glarein.name = "GlareIn"

        # Node GhostGlare
        ghostglare = aptpro_lens_flare.nodes.new("CompositorNodeGlare")
        ghostglare.label = "GhostGlare"
        ghostglare.name = "GhostGlare"
        ghostglare.glare_type = 'GHOSTS'
        ghostglare.quality = 'HIGH'
        # Highlights Threshold
        ghostglare.inputs[1].default_value = 5.0
        # Highlights Smoothness
        ghostglare.inputs[2].default_value = 1.0
        # Clamp Highlights
        ghostglare.inputs[3].default_value = True
        # Strength
        ghostglare.inputs[5].default_value = 1.0
        # Saturation
        ghostglare.inputs[6].default_value = 1.0
        # Tint
        ghostglare.inputs[7].default_value = (1.0, 1.0, 1.0, 1.0)
        # Iterations
        ghostglare.inputs[11].default_value = 5
        # Color Modulation
        ghostglare.inputs[13].default_value = 0.5

        # Node LDRad
        ldrad = aptpro_lens_flare.nodes.new("CompositorNodeLensdist")
        ldrad.label = "LDRad"
        ldrad.name = "LDRad"
        ldrad.distortion_type = 'RADIAL'
        # Distortion
        ldrad.inputs[1].default_value = 1.0
        # Dispersion
        ldrad.inputs[2].default_value = 1.0
        # Jitter
        ldrad.inputs[3].default_value = False
        # Fit
        ldrad.inputs[4].default_value = True

        # Node EmissionPassBlur
        emissionpassblur = aptpro_lens_flare.nodes.new("CompositorNodeBlur")
        emissionpassblur.label = "EmissionPassBlur"
        emissionpassblur.name = "EmissionPassBlur"
        emissionpassblur.filter_type = 'FAST_GAUSS'
        # Size
        emissionpassblur.inputs[1].default_value = (50.0, 50.0)
        # Extend Bounds
        emissionpassblur.inputs[2].default_value = False
        # Separable
        emissionpassblur.inputs[3].default_value = True

        # Node GlareEffect
        glareeffect = aptpro_lens_flare.nodes.new("CompositorNodeGlare")
        glareeffect.label = "GlareEffect"
        glareeffect.name = "GlareEffect"
        glareeffect.glare_type = 'BLOOM'
        glareeffect.quality = 'HIGH'
        # Highlights Threshold
        glareeffect.inputs[1].default_value = 25.0
        # Highlights Smoothness
        glareeffect.inputs[2].default_value = 1.0
        # Clamp Highlights
        glareeffect.inputs[3].default_value = True
        # Maximum Highlights
        glareeffect.inputs[4].default_value = 5.0
        # Strength
        glareeffect.inputs[5].default_value = 1.0
        # Saturation
        glareeffect.inputs[6].default_value = 1.0
        # Tint
        glareeffect.inputs[7].default_value = (1.0, 1.0, 1.0, 1.0)
        # Size
        glareeffect.inputs[8].default_value = 1.0

        # Node LDHor
        ldhor = aptpro_lens_flare.nodes.new("CompositorNodeLensdist")
        ldhor.label = "LDHor"
        ldhor.name = "LDHor"
        ldhor.distortion_type = 'HORIZONTAL'
        # Dispersion
        ldhor.inputs[2].default_value = 0.30000001192092896

        # Node LDmerge
        ldmerge = aptpro_lens_flare.nodes.new("ShaderNodeMix")
        ldmerge.label = "LDmerge"
        ldmerge.name = "LDmerge"
        ldmerge.blend_type = 'LIGHTEN'
        ldmerge.clamp_factor = False
        ldmerge.clamp_result = True
        ldmerge.data_type = 'RGBA'
        ldmerge.factor_mode = 'UNIFORM'

        # Node HeavyGlare
        heavyglare = aptpro_lens_flare.nodes.new("CompositorNodeGlare")
        heavyglare.label = "HeavyGlare"
        heavyglare.name = "HeavyGlare"
        heavyglare.glare_type = 'BLOOM'
        heavyglare.quality = 'HIGH'
        # Highlights Threshold
        heavyglare.inputs[1].default_value = 0.5
        # Highlights Smoothness
        heavyglare.inputs[2].default_value = 1.0
        # Clamp Highlights
        heavyglare.inputs[3].default_value = True
        # Maximum Highlights
        heavyglare.inputs[4].default_value = 5.0
        # Strength
        heavyglare.inputs[5].default_value = 1.0
        # Saturation
        heavyglare.inputs[6].default_value = 1.0
        # Tint
        heavyglare.inputs[7].default_value = (1.0, 1.0, 1.0, 1.0)
        # Size
        heavyglare.inputs[8].default_value = 1.0

        # Node LDscreen
        ldscreen = aptpro_lens_flare.nodes.new("ShaderNodeMix")
        ldscreen.label = "LDscreen"
        ldscreen.name = "LDscreen"
        ldscreen.blend_type = 'SCREEN'
        ldscreen.clamp_factor = False
        ldscreen.clamp_result = True
        ldscreen.data_type = 'RGBA'
        ldscreen.factor_mode = 'UNIFORM'

        # Set locations
        glareout.location = (1262.625244140625, 119.78299713134766)
        glarein.location = (-814.3770141601562, -34.27398681640625)
        ghostglare.location = (85.81334686279297, -187.0814971923828)
        ldrad.location = (314.9693603515625, -16.030517578125)
        emissionpassblur.location = (-153.20443725585938, 51.68720245361328)
        glareeffect.location = (82.52542877197266, 222.9254150390625)
        ldhor.location = (307.8520812988281, 218.88320922851562)
        ldmerge.location = (538.654052734375, 131.53196716308594)
        heavyglare.location = (83.25872802734375, 664.5924072265625)
        ldscreen.location = (874.5314331054688, 226.48110961914062)

        # Set dimensions
        glareout.width, glareout.height = 140.0, 100.0
        glarein.width, glarein.height = 140.0, 100.0
        ghostglare.width, ghostglare.height = 186.9810791015625, 100.0
        ldrad.width, ldrad.height = 140.0, 100.0
        emissionpassblur.width, emissionpassblur.height = 140.0, 100.0
        glareeffect.width, glareeffect.height = 140.0, 100.0
        ldhor.width, ldhor.height = 174.1680908203125, 100.0
        ldmerge.width, ldmerge.height = 140.0, 100.0
        heavyglare.width, heavyglare.height = 140.0, 100.0
        ldscreen.width, ldscreen.height = 140.0, 100.0

        # Initialize aptpro_lens_flare links

        # ldrad.Image -> ldmerge.A
        aptpro_lens_flare.links.new(ldrad.outputs[0], ldmerge.inputs[6])
        # glareeffect.Glare -> ldhor.Image
        aptpro_lens_flare.links.new(glareeffect.outputs[1], ldhor.inputs[0])
        # emissionpassblur.Image -> glareeffect.Image
        aptpro_lens_flare.links.new(emissionpassblur.outputs[0], glareeffect.inputs[0])
        # ldhor.Image -> ldmerge.B
        aptpro_lens_flare.links.new(ldhor.outputs[0], ldmerge.inputs[7])
        # ghostglare.Glare -> ldrad.Image
        aptpro_lens_flare.links.new(ghostglare.outputs[1], ldrad.inputs[0])
        # emissionpassblur.Image -> ghostglare.Image
        aptpro_lens_flare.links.new(emissionpassblur.outputs[0], ghostglare.inputs[0])
        # glarein.Emission pass -> ghostglare.Maximum
        aptpro_lens_flare.links.new(glarein.outputs[1], ghostglare.inputs[4])
        # glarein.Emission pass -> emissionpassblur.Image
        aptpro_lens_flare.links.new(glarein.outputs[1], emissionpassblur.inputs[0])
        # glarein.Lens Flare intensity -> ldmerge.Factor
        aptpro_lens_flare.links.new(glarein.outputs[3], ldmerge.inputs[0])
        # glarein.Image -> heavyglare.Image
        aptpro_lens_flare.links.new(glarein.outputs[0], heavyglare.inputs[0])
        # ldmerge.Result -> ldscreen.A
        aptpro_lens_flare.links.new(ldmerge.outputs[2], ldscreen.inputs[6])
        # glarein.General Bloom -> ldscreen.Factor
        aptpro_lens_flare.links.new(glarein.outputs[2], ldscreen.inputs[0])
        # heavyglare.Glare -> ldscreen.B
        aptpro_lens_flare.links.new(heavyglare.outputs[1], ldscreen.inputs[7])
        # ldscreen.Result -> glareout.Image
        aptpro_lens_flare.links.new(ldscreen.outputs[2], glareout.inputs[0])

        return aptpro_lens_flare

    aptpro_lens_flare = aptpro_lens_flare_node_group()

    def aptpro_shadow_mask_node_group():
        """Initialize AptPro SHADOW MASK node group"""
        aptpro_shadow_mask = bpy.data.node_groups.new(type = 'CompositorNodeTree', name = "AptPro SHADOW MASK")

        aptpro_shadow_mask.color_tag = 'NONE'
        aptpro_shadow_mask.description = ""
        aptpro_shadow_mask.default_group_node_width = 140
        aptpro_shadow_mask.use_fake_user = True
        # aptpro_shadow_mask interface

        # Socket Shadow Mask
        shadow_mask_socket = aptpro_shadow_mask.interface.new_socket(name="Shadow Mask", in_out='OUTPUT', socket_type='NodeSocketColor')
        shadow_mask_socket.default_value = (0.0, 0.0, 0.0, 1.0)
        shadow_mask_socket.attribute_domain = 'POINT'
        shadow_mask_socket.default_input = 'VALUE'
        shadow_mask_socket.structure_type = 'AUTO'

        # Socket Diffuse Direct
        diffuse_direct_socket = aptpro_shadow_mask.interface.new_socket(name="Diffuse Direct", in_out='INPUT', socket_type='NodeSocketColor')
        diffuse_direct_socket.default_value = (1.0, 1.0, 1.0, 1.0)
        diffuse_direct_socket.attribute_domain = 'POINT'
        diffuse_direct_socket.default_input = 'VALUE'
        diffuse_direct_socket.structure_type = 'AUTO'

        # Socket Glossy Direct
        glossy_direct_socket = aptpro_shadow_mask.interface.new_socket(name="Glossy Direct", in_out='INPUT', socket_type='NodeSocketColor')
        glossy_direct_socket.default_value = (1.0, 1.0, 1.0, 1.0)
        glossy_direct_socket.attribute_domain = 'POINT'
        glossy_direct_socket.default_input = 'VALUE'
        glossy_direct_socket.structure_type = 'AUTO'

        # Socket Transmission Indirect
        transmission_indirect_socket = aptpro_shadow_mask.interface.new_socket(name="Transmission Indirect", in_out='INPUT', socket_type='NodeSocketColor')
        transmission_indirect_socket.default_value = (1.0, 1.0, 1.0, 1.0)
        transmission_indirect_socket.attribute_domain = 'POINT'
        transmission_indirect_socket.default_input = 'VALUE'
        transmission_indirect_socket.structure_type = 'AUTO'

        # Socket Volume Direct
        volume_direct_socket = aptpro_shadow_mask.interface.new_socket(name="Volume Direct", in_out='INPUT', socket_type='NodeSocketColor')
        volume_direct_socket.default_value = (1.0, 1.0, 1.0, 1.0)
        volume_direct_socket.attribute_domain = 'POINT'
        volume_direct_socket.default_input = 'VALUE'
        volume_direct_socket.structure_type = 'AUTO'

        # Socket Emission
        emission_socket = aptpro_shadow_mask.interface.new_socket(name="Emission", in_out='INPUT', socket_type='NodeSocketColor')
        emission_socket.default_value = (1.0, 1.0, 1.0, 1.0)
        emission_socket.attribute_domain = 'POINT'
        emission_socket.default_input = 'VALUE'
        emission_socket.structure_type = 'AUTO'

        # Socket Environment
        environment_socket = aptpro_shadow_mask.interface.new_socket(name="Environment", in_out='INPUT', socket_type='NodeSocketColor')
        environment_socket.default_value = (1.0, 1.0, 1.0, 1.0)
        environment_socket.attribute_domain = 'POINT'
        environment_socket.default_input = 'VALUE'
        environment_socket.structure_type = 'AUTO'

        # Socket Ambient Occlusion
        ambient_occlusion_socket = aptpro_shadow_mask.interface.new_socket(name="Ambient Occlusion", in_out='INPUT', socket_type='NodeSocketColor')
        ambient_occlusion_socket.default_value = (1.0, 1.0, 1.0, 1.0)
        ambient_occlusion_socket.attribute_domain = 'POINT'
        ambient_occlusion_socket.default_input = 'VALUE'
        ambient_occlusion_socket.structure_type = 'AUTO'

        # Initialize aptpro_shadow_mask nodes

        # Node SMout
        smout = aptpro_shadow_mask.nodes.new("NodeGroupOutput")
        smout.label = "SMout"
        smout.name = "SMout"
        smout.is_active_output = True

        # Node SMin
        smin = aptpro_shadow_mask.nodes.new("NodeGroupInput")
        smin.label = "SMin"
        smin.name = "SMin"

        # Node SMden4
        smden4 = aptpro_shadow_mask.nodes.new("CompositorNodeDenoise")
        smden4.label = "SMden4"
        smden4.name = "SMden4"
        smden4.prefilter = 'ACCURATE'
        smden4.quality = 'FOLLOW_SCENE'
        # Normal
        smden4.inputs[1].default_value = (0.0, 0.0, 0.0)
        # Albedo
        smden4.inputs[2].default_value = (1.0, 1.0, 1.0, 1.0)
        # HDR
        smden4.inputs[3].default_value = False

        # Node SMden6
        smden6 = aptpro_shadow_mask.nodes.new("CompositorNodeDenoise")
        smden6.label = "SMden6"
        smden6.name = "SMden6"
        smden6.prefilter = 'ACCURATE'
        smden6.quality = 'FOLLOW_SCENE'
        # Normal
        smden6.inputs[1].default_value = (0.0, 0.0, 0.0)
        # Albedo
        smden6.inputs[2].default_value = (1.0, 1.0, 1.0, 1.0)
        # HDR
        smden6.inputs[3].default_value = False

        # Node SMden5
        smden5 = aptpro_shadow_mask.nodes.new("CompositorNodeDenoise")
        smden5.label = "SMden5"
        smden5.name = "SMden5"
        smden5.prefilter = 'ACCURATE'
        smden5.quality = 'FOLLOW_SCENE'
        # Normal
        smden5.inputs[1].default_value = (0.0, 0.0, 0.0)
        # Albedo
        smden5.inputs[2].default_value = (1.0, 1.0, 1.0, 1.0)
        # HDR
        smden5.inputs[3].default_value = False

        # Node SMden7
        smden7 = aptpro_shadow_mask.nodes.new("CompositorNodeDenoise")
        smden7.label = "SMden7"
        smden7.name = "SMden7"
        smden7.prefilter = 'ACCURATE'
        smden7.quality = 'FOLLOW_SCENE'
        # Normal
        smden7.inputs[1].default_value = (0.0, 0.0, 0.0)
        # Albedo
        smden7.inputs[2].default_value = (1.0, 1.0, 1.0, 1.0)
        # HDR
        smden7.inputs[3].default_value = False

        # Node SMden1
        smden1 = aptpro_shadow_mask.nodes.new("CompositorNodeDenoise")
        smden1.label = "SMden1"
        smden1.name = "SMden1"
        smden1.prefilter = 'ACCURATE'
        smden1.quality = 'FOLLOW_SCENE'
        # Normal
        smden1.inputs[1].default_value = (0.0, 0.0, 0.0)
        # Albedo
        smden1.inputs[2].default_value = (1.0, 1.0, 1.0, 1.0)
        # HDR
        smden1.inputs[3].default_value = False

        # Node SMden2
        smden2 = aptpro_shadow_mask.nodes.new("CompositorNodeDenoise")
        smden2.label = "SMden2"
        smden2.name = "SMden2"
        smden2.prefilter = 'ACCURATE'
        smden2.quality = 'FOLLOW_SCENE'
        # Normal
        smden2.inputs[1].default_value = (0.0, 0.0, 0.0)
        # Albedo
        smden2.inputs[2].default_value = (1.0, 1.0, 1.0, 1.0)
        # HDR
        smden2.inputs[3].default_value = False

        # Node SMden3
        smden3 = aptpro_shadow_mask.nodes.new("CompositorNodeDenoise")
        smden3.label = "SMden3"
        smden3.name = "SMden3"
        smden3.prefilter = 'ACCURATE'
        smden3.quality = 'FOLLOW_SCENE'
        # Normal
        smden3.inputs[1].default_value = (0.0, 0.0, 0.0)
        # Albedo
        smden3.inputs[2].default_value = (1.0, 1.0, 1.0, 1.0)
        # HDR
        smden3.inputs[3].default_value = False

        # Node Den1Alpha
        den1alpha = aptpro_shadow_mask.nodes.new("CompositorNodeSetAlpha")
        den1alpha.label = "Den1Alpha"
        den1alpha.name = "Den1Alpha"
        den1alpha.mode = 'APPLY'
        # Alpha
        den1alpha.inputs[1].default_value = 1.0

        # Node Den2Alpha
        den2alpha = aptpro_shadow_mask.nodes.new("CompositorNodeSetAlpha")
        den2alpha.label = "Den2Alpha"
        den2alpha.name = "Den2Alpha"
        den2alpha.mode = 'APPLY'
        # Alpha
        den2alpha.inputs[1].default_value = 1.0

        # Node Den12Lighten
        den12lighten = aptpro_shadow_mask.nodes.new("ShaderNodeMix")
        den12lighten.label = "Den12Lighten"
        den12lighten.name = "Den12Lighten"
        den12lighten.blend_type = 'LIGHTEN'
        den12lighten.clamp_factor = False
        den12lighten.clamp_result = True
        den12lighten.data_type = 'RGBA'
        den12lighten.factor_mode = 'UNIFORM'

        # Node Den3Alpha
        den3alpha = aptpro_shadow_mask.nodes.new("CompositorNodeSetAlpha")
        den3alpha.label = "Den3Alpha"
        den3alpha.name = "Den3Alpha"
        den3alpha.mode = 'APPLY'
        # Alpha
        den3alpha.inputs[1].default_value = 1.0

        # Node Den4Alpha
        den4alpha = aptpro_shadow_mask.nodes.new("CompositorNodeSetAlpha")
        den4alpha.label = "Den4Alpha"
        den4alpha.name = "Den4Alpha"
        den4alpha.mode = 'APPLY'
        # Alpha
        den4alpha.inputs[1].default_value = 1.0

        # Node Den34Lighten
        den34lighten = aptpro_shadow_mask.nodes.new("ShaderNodeMix")
        den34lighten.label = "Den34Lighten"
        den34lighten.name = "Den34Lighten"
        den34lighten.blend_type = 'LIGHTEN'
        den34lighten.clamp_factor = False
        den34lighten.clamp_result = True
        den34lighten.data_type = 'RGBA'
        den34lighten.factor_mode = 'UNIFORM'

        # Node Den5Alpha
        den5alpha = aptpro_shadow_mask.nodes.new("CompositorNodeSetAlpha")
        den5alpha.label = "Den5Alpha"
        den5alpha.name = "Den5Alpha"
        den5alpha.mode = 'APPLY'
        # Alpha
        den5alpha.inputs[1].default_value = 1.0

        # Node Den6Alpha
        den6alpha = aptpro_shadow_mask.nodes.new("CompositorNodeSetAlpha")
        den6alpha.label = "Den6Alpha"
        den6alpha.name = "Den6Alpha"
        den6alpha.mode = 'APPLY'
        # Alpha
        den6alpha.inputs[1].default_value = 1.0

        # Node Den56Lighten
        den56lighten = aptpro_shadow_mask.nodes.new("ShaderNodeMix")
        den56lighten.label = "Den56Lighten"
        den56lighten.name = "Den56Lighten"
        den56lighten.blend_type = 'LIGHTEN'
        den56lighten.clamp_factor = False
        den56lighten.clamp_result = True
        den56lighten.data_type = 'RGBA'
        den56lighten.factor_mode = 'UNIFORM'

        # Node Den1234Lighten
        den1234lighten = aptpro_shadow_mask.nodes.new("ShaderNodeMix")
        den1234lighten.label = "Den1234Lighten"
        den1234lighten.name = "Den1234Lighten"
        den1234lighten.blend_type = 'LIGHTEN'
        den1234lighten.clamp_factor = False
        den1234lighten.clamp_result = True
        den1234lighten.data_type = 'RGBA'
        den1234lighten.factor_mode = 'UNIFORM'

        # Node Den1-6Excl
        den1_6excl = aptpro_shadow_mask.nodes.new("ShaderNodeMix")
        den1_6excl.label = "Den1-6Excl"
        den1_6excl.name = "Den1-6Excl"
        den1_6excl.blend_type = 'EXCLUSION'
        den1_6excl.clamp_factor = False
        den1_6excl.clamp_result = True
        den1_6excl.data_type = 'RGBA'
        den1_6excl.factor_mode = 'UNIFORM'

        # Node DenCombineAdd
        dencombineadd = aptpro_shadow_mask.nodes.new("ShaderNodeMix")
        dencombineadd.label = "DenCombineAdd"
        dencombineadd.name = "DenCombineAdd"
        dencombineadd.blend_type = 'ADD'
        dencombineadd.clamp_factor = False
        dencombineadd.clamp_result = True
        dencombineadd.data_type = 'RGBA'
        dencombineadd.factor_mode = 'UNIFORM'

        # Node SM_BW
        sm_bw = aptpro_shadow_mask.nodes.new("CompositorNodeRGBToBW")
        sm_bw.label = "SM_BW"
        sm_bw.name = "SM_BW"

        # Node Den2Mult
        den2mult = aptpro_shadow_mask.nodes.new("ShaderNodeMath")
        den2mult.label = "Den2Mult"
        den2mult.name = "Den2Mult"
        den2mult.operation = 'MULTIPLY'
        den2mult.use_clamp = False

        # Node Den2SeparateAlpha
        den2separatealpha = aptpro_shadow_mask.nodes.new("CompositorNodeSeparateColor")
        den2separatealpha.label = "Den2SeparateAlpha"
        den2separatealpha.name = "Den2SeparateAlpha"
        den2separatealpha.mode = 'RGB'
        den2separatealpha.ycc_mode = 'ITUBT709'

        # Node Den4Mult
        den4mult = aptpro_shadow_mask.nodes.new("ShaderNodeMath")
        den4mult.label = "Den4Mult"
        den4mult.name = "Den4Mult"
        den4mult.operation = 'MULTIPLY'
        den4mult.use_clamp = False

        # Node Den4SeparateAlpha
        den4separatealpha = aptpro_shadow_mask.nodes.new("CompositorNodeSeparateColor")
        den4separatealpha.label = "Den4SeparateAlpha"
        den4separatealpha.name = "Den4SeparateAlpha"
        den4separatealpha.mode = 'RGB'
        den4separatealpha.ycc_mode = 'ITUBT709'

        # Node Den6Mult
        den6mult = aptpro_shadow_mask.nodes.new("ShaderNodeMath")
        den6mult.label = "Den6Mult"
        den6mult.name = "Den6Mult"
        den6mult.operation = 'MULTIPLY'
        den6mult.use_clamp = False

        # Node Den6SeparateAlpha
        den6separatealpha = aptpro_shadow_mask.nodes.new("CompositorNodeSeparateColor")
        den6separatealpha.label = "Den6SeparateAlpha"
        den6separatealpha.name = "Den6SeparateAlpha"
        den6separatealpha.mode = 'RGB'
        den6separatealpha.ycc_mode = 'ITUBT709'

        # Node Den34Mult
        den34mult = aptpro_shadow_mask.nodes.new("ShaderNodeMath")
        den34mult.label = "Den34Mult"
        den34mult.name = "Den34Mult"
        den34mult.operation = 'MULTIPLY'
        den34mult.use_clamp = False
        # Value
        den34mult.inputs[0].default_value = 1.0

        # Node Den34SeparateAlpha
        den34separatealpha = aptpro_shadow_mask.nodes.new("CompositorNodeSeparateColor")
        den34separatealpha.label = "Den34SeparateAlpha"
        den34separatealpha.name = "Den34SeparateAlpha"
        den34separatealpha.mode = 'RGB'
        den34separatealpha.ycc_mode = 'ITUBT709'

        # Node Den56Mult
        den56mult = aptpro_shadow_mask.nodes.new("ShaderNodeMath")
        den56mult.label = "Den56Mult"
        den56mult.name = "Den56Mult"
        den56mult.operation = 'MULTIPLY'
        den56mult.use_clamp = False
        # Value
        den56mult.inputs[0].default_value = 1.0

        # Node Den56SeparateAlpha
        den56separatealpha = aptpro_shadow_mask.nodes.new("CompositorNodeSeparateColor")
        den56separatealpha.label = "Den56SeparateAlpha"
        den56separatealpha.name = "Den56SeparateAlpha"
        den56separatealpha.mode = 'RGB'
        den56separatealpha.ycc_mode = 'ITUBT709'

        # Node Den7Mult
        den7mult = aptpro_shadow_mask.nodes.new("ShaderNodeMath")
        den7mult.label = "Den7Mult"
        den7mult.name = "Den7Mult"
        den7mult.operation = 'MULTIPLY'
        den7mult.use_clamp = False
        # Value
        den7mult.inputs[0].default_value = 1.0

        # Node Den7SeparateAlpha
        den7separatealpha = aptpro_shadow_mask.nodes.new("CompositorNodeSeparateColor")
        den7separatealpha.label = "Den7SeparateAlpha"
        den7separatealpha.name = "Den7SeparateAlpha"
        den7separatealpha.mode = 'RGB'
        den7separatealpha.ycc_mode = 'ITUBT709'

        # Set locations
        smout.location = (1841.005126953125, 52.80200958251953)
        smin.location = (-1738.6099853515625, 56.568092346191406)
        smden4.location = (-1261.639892578125, -99.52218627929688)
        smden6.location = (-1113.666748046875, -574.6509399414062)
        smden5.location = (-1113.5084228515625, -326.06866455078125)
        smden7.location = (-1106.4927978515625, -844.4006958007812)
        smden1.location = (-1471.410400390625, 370.5016784667969)
        smden2.location = (-1324.5941162109375, 271.6446838378906)
        smden3.location = (-1171.8424072265625, 150.74868774414062)
        den1alpha.location = (-936.681884765625, 439.7300720214844)
        den2alpha.location = (-944.2076416015625, 278.21502685546875)
        den12lighten.location = (195.83856201171875, 434.18719482421875)
        den3alpha.location = (-963.0430297851562, 129.947998046875)
        den4alpha.location = (-1037.904541015625, -152.7812042236328)
        den34lighten.location = (-349.37738037109375, 117.35810852050781)
        den5alpha.location = (-796.710205078125, -429.7969665527344)
        den6alpha.location = (-923.0370483398438, -575.3062744140625)
        den56lighten.location = (512.5911254882812, 173.80380249023438)
        den1234lighten.location = (559.1408081054688, 465.2008972167969)
        den1_6excl.location = (1240.095703125, 345.56170654296875)
        dencombineadd.location = (1436.6650390625, 63.87954330444336)
        sm_bw.location = (1647.7913818359375, 55.400264739990234)
        den2mult.location = (-31.789419174194336, 513.8639526367188)
        den2separatealpha.location = (-283.4629211425781, 583.0174560546875)
        den4mult.location = (-577.3262939453125, -188.5846710205078)
        den4separatealpha.location = (-826.763671875, -253.19915771484375)
        den6mult.location = (-213.7292022705078, -391.10760498046875)
        den6separatealpha.location = (-668.8292236328125, -616.0426635742188)
        den34mult.location = (285.9173583984375, 166.9801025390625)
        den34separatealpha.location = (-82.97200012207031, 76.86937713623047)
        den56mult.location = (987.8128662109375, 126.64530181884766)
        den56separatealpha.location = (750.453125, 109.76637268066406)
        den7mult.location = (1181.818359375, -14.482528686523438)
        den7separatealpha.location = (983.7311401367188, -29.362361907958984)

        # Set dimensions
        smout.width, smout.height = 140.0, 100.0
        smin.width, smin.height = 140.0, 100.0
        smden4.width, smden4.height = 140.0, 100.0
        smden6.width, smden6.height = 140.0, 100.0
        smden5.width, smden5.height = 140.0, 100.0
        smden7.width, smden7.height = 140.0, 100.0
        smden1.width, smden1.height = 140.0, 100.0
        smden2.width, smden2.height = 140.0, 100.0
        smden3.width, smden3.height = 140.0, 100.0
        den1alpha.width, den1alpha.height = 140.0, 100.0
        den2alpha.width, den2alpha.height = 140.0, 100.0
        den12lighten.width, den12lighten.height = 140.0, 100.0
        den3alpha.width, den3alpha.height = 138.23532104492188, 100.0
        den4alpha.width, den4alpha.height = 140.0, 100.0
        den34lighten.width, den34lighten.height = 140.0, 100.0
        den5alpha.width, den5alpha.height = 138.23532104492188, 100.0
        den6alpha.width, den6alpha.height = 140.0, 100.0
        den56lighten.width, den56lighten.height = 140.0, 100.0
        den1234lighten.width, den1234lighten.height = 140.0, 100.0
        den1_6excl.width, den1_6excl.height = 140.0, 100.0
        dencombineadd.width, dencombineadd.height = 140.0, 100.0
        sm_bw.width, sm_bw.height = 140.0, 100.0
        den2mult.width, den2mult.height = 140.0, 100.0
        den2separatealpha.width, den2separatealpha.height = 140.0, 100.0
        den4mult.width, den4mult.height = 140.0, 100.0
        den4separatealpha.width, den4separatealpha.height = 140.0, 100.0
        den6mult.width, den6mult.height = 140.0, 100.0
        den6separatealpha.width, den6separatealpha.height = 140.0, 100.0
        den34mult.width, den34mult.height = 140.0, 100.0
        den34separatealpha.width, den34separatealpha.height = 140.0, 100.0
        den56mult.width, den56mult.height = 140.0, 100.0
        den56separatealpha.width, den56separatealpha.height = 140.0, 100.0
        den7mult.width, den7mult.height = 140.0, 100.0
        den7separatealpha.width, den7separatealpha.height = 140.0, 100.0

        # Initialize aptpro_shadow_mask links

        # smden5.Image -> den5alpha.Image
        aptpro_shadow_mask.links.new(smden5.outputs[0], den5alpha.inputs[0])
        # den34lighten.Result -> den1234lighten.B
        aptpro_shadow_mask.links.new(den34lighten.outputs[2], den1234lighten.inputs[7])
        # den3alpha.Image -> den34lighten.A
        aptpro_shadow_mask.links.new(den3alpha.outputs[0], den34lighten.inputs[6])
        # den12lighten.Result -> den1234lighten.A
        aptpro_shadow_mask.links.new(den12lighten.outputs[2], den1234lighten.inputs[6])
        # smden4.Image -> den4alpha.Image
        aptpro_shadow_mask.links.new(smden4.outputs[0], den4alpha.inputs[0])
        # den1234lighten.Result -> den1_6excl.A
        aptpro_shadow_mask.links.new(den1234lighten.outputs[2], den1_6excl.inputs[6])
        # den6alpha.Image -> den56lighten.B
        aptpro_shadow_mask.links.new(den6alpha.outputs[0], den56lighten.inputs[7])
        # smden3.Image -> den3alpha.Image
        aptpro_shadow_mask.links.new(smden3.outputs[0], den3alpha.inputs[0])
        # den56lighten.Result -> den1_6excl.B
        aptpro_shadow_mask.links.new(den56lighten.outputs[2], den1_6excl.inputs[7])
        # den2alpha.Image -> den12lighten.B
        aptpro_shadow_mask.links.new(den2alpha.outputs[0], den12lighten.inputs[7])
        # smden2.Image -> den2alpha.Image
        aptpro_shadow_mask.links.new(smden2.outputs[0], den2alpha.inputs[0])
        # den1_6excl.Result -> dencombineadd.A
        aptpro_shadow_mask.links.new(den1_6excl.outputs[2], dencombineadd.inputs[6])
        # smden1.Image -> den1alpha.Image
        aptpro_shadow_mask.links.new(smden1.outputs[0], den1alpha.inputs[0])
        # smden7.Image -> dencombineadd.B
        aptpro_shadow_mask.links.new(smden7.outputs[0], dencombineadd.inputs[7])
        # den5alpha.Image -> den56lighten.A
        aptpro_shadow_mask.links.new(den5alpha.outputs[0], den56lighten.inputs[6])
        # dencombineadd.Result -> sm_bw.Image
        aptpro_shadow_mask.links.new(dencombineadd.outputs[2], sm_bw.inputs[0])
        # den1alpha.Image -> den12lighten.A
        aptpro_shadow_mask.links.new(den1alpha.outputs[0], den12lighten.inputs[6])
        # smden6.Image -> den6alpha.Image
        aptpro_shadow_mask.links.new(smden6.outputs[0], den6alpha.inputs[0])
        # den4alpha.Image -> den34lighten.B
        aptpro_shadow_mask.links.new(den4alpha.outputs[0], den34lighten.inputs[7])
        # smin.Transmission Indirect -> smden5.Image
        aptpro_shadow_mask.links.new(smin.outputs[2], smden5.inputs[0])
        # smin.Environment -> smden2.Image
        aptpro_shadow_mask.links.new(smin.outputs[5], smden2.inputs[0])
        # smin.Volume Direct -> smden7.Image
        aptpro_shadow_mask.links.new(smin.outputs[3], smden7.inputs[0])
        # smin.Diffuse Direct -> smden4.Image
        aptpro_shadow_mask.links.new(smin.outputs[0], smden4.inputs[0])
        # smin.Ambient Occlusion -> smden3.Image
        aptpro_shadow_mask.links.new(smin.outputs[6], smden3.inputs[0])
        # smin.Emission -> smden1.Image
        aptpro_shadow_mask.links.new(smin.outputs[4], smden1.inputs[0])
        # smin.Glossy Direct -> smden6.Image
        aptpro_shadow_mask.links.new(smin.outputs[1], smden6.inputs[0])
        # den2mult.Value -> den12lighten.Factor
        aptpro_shadow_mask.links.new(den2mult.outputs[0], den12lighten.inputs[0])
        # den2alpha.Image -> den2mult.Value
        aptpro_shadow_mask.links.new(den2alpha.outputs[0], den2mult.inputs[0])
        # den2alpha.Image -> den2separatealpha.Image
        aptpro_shadow_mask.links.new(den2alpha.outputs[0], den2separatealpha.inputs[0])
        # den2separatealpha.Alpha -> den2mult.Value
        aptpro_shadow_mask.links.new(den2separatealpha.outputs[3], den2mult.inputs[1])
        # den4mult.Value -> den34lighten.Factor
        aptpro_shadow_mask.links.new(den4mult.outputs[0], den34lighten.inputs[0])
        # den4alpha.Image -> den4mult.Value
        aptpro_shadow_mask.links.new(den4alpha.outputs[0], den4mult.inputs[0])
        # den4alpha.Image -> den4separatealpha.Image
        aptpro_shadow_mask.links.new(den4alpha.outputs[0], den4separatealpha.inputs[0])
        # den4separatealpha.Alpha -> den4mult.Value
        aptpro_shadow_mask.links.new(den4separatealpha.outputs[3], den4mult.inputs[1])
        # den6mult.Value -> den56lighten.Factor
        aptpro_shadow_mask.links.new(den6mult.outputs[0], den56lighten.inputs[0])
        # den6alpha.Image -> den6mult.Value
        aptpro_shadow_mask.links.new(den6alpha.outputs[0], den6mult.inputs[0])
        # den6alpha.Image -> den6separatealpha.Image
        aptpro_shadow_mask.links.new(den6alpha.outputs[0], den6separatealpha.inputs[0])
        # den6separatealpha.Alpha -> den6mult.Value
        aptpro_shadow_mask.links.new(den6separatealpha.outputs[3], den6mult.inputs[1])
        # den34mult.Value -> den1234lighten.Factor
        aptpro_shadow_mask.links.new(den34mult.outputs[0], den1234lighten.inputs[0])
        # den34lighten.Result -> den34separatealpha.Image
        aptpro_shadow_mask.links.new(den34lighten.outputs[2], den34separatealpha.inputs[0])
        # den34separatealpha.Alpha -> den34mult.Value
        aptpro_shadow_mask.links.new(den34separatealpha.outputs[3], den34mult.inputs[1])
        # den56mult.Value -> den1_6excl.Factor
        aptpro_shadow_mask.links.new(den56mult.outputs[0], den1_6excl.inputs[0])
        # den56lighten.Result -> den56separatealpha.Image
        aptpro_shadow_mask.links.new(den56lighten.outputs[2], den56separatealpha.inputs[0])
        # den56separatealpha.Alpha -> den56mult.Value
        aptpro_shadow_mask.links.new(den56separatealpha.outputs[3], den56mult.inputs[1])
        # den7mult.Value -> dencombineadd.Factor
        aptpro_shadow_mask.links.new(den7mult.outputs[0], dencombineadd.inputs[0])
        # smden7.Image -> den7separatealpha.Image
        aptpro_shadow_mask.links.new(smden7.outputs[0], den7separatealpha.inputs[0])
        # den7separatealpha.Alpha -> den7mult.Value
        aptpro_shadow_mask.links.new(den7separatealpha.outputs[3], den7mult.inputs[1])
        # sm_bw.Val -> smout.Shadow Mask
        aptpro_shadow_mask.links.new(sm_bw.outputs[0], smout.inputs[0])

        return aptpro_shadow_mask

    aptpro_shadow_mask = aptpro_shadow_mask_node_group()

    def aptpro_vignette_node_group():
        """Initialize AptPro VIGNETTE node group"""
        aptpro_vignette = bpy.data.node_groups.new(type = 'CompositorNodeTree', name = "AptPro VIGNETTE")

        aptpro_vignette.color_tag = 'NONE'
        aptpro_vignette.description = ""
        aptpro_vignette.default_group_node_width = 140
        aptpro_vignette.use_fake_user = True
        # aptpro_vignette interface

        # Socket Image
        image_socket_2 = aptpro_vignette.interface.new_socket(name="Image", in_out='OUTPUT', socket_type='NodeSocketColor')
        image_socket_2.default_value = (0.800000011920929, 0.800000011920929, 0.800000011920929, 1.0)
        image_socket_2.attribute_domain = 'POINT'
        image_socket_2.default_input = 'VALUE'
        image_socket_2.structure_type = 'AUTO'

        # Socket VIGNETTE AMOUNT
        vignette_amount_socket = aptpro_vignette.interface.new_socket(name="VIGNETTE AMOUNT", in_out='OUTPUT', socket_type='NodeSocketFloat')
        vignette_amount_socket.default_value = 1.0
        vignette_amount_socket.min_value = -3.4028234663852886e+38
        vignette_amount_socket.max_value = 3.4028234663852886e+38
        vignette_amount_socket.subtype = 'NONE'
        vignette_amount_socket.attribute_domain = 'POINT'
        vignette_amount_socket.default_input = 'VALUE'
        vignette_amount_socket.structure_type = 'AUTO'

        # Socket VIGNETTE INTENSITY
        vignette_intensity_socket = aptpro_vignette.interface.new_socket(name="VIGNETTE INTENSITY", in_out='INPUT', socket_type='NodeSocketFloat')
        vignette_intensity_socket.default_value = 0.5
        vignette_intensity_socket.min_value = 0.0
        vignette_intensity_socket.max_value = 1.0
        vignette_intensity_socket.subtype = 'NONE'
        vignette_intensity_socket.attribute_domain = 'POINT'
        vignette_intensity_socket.default_input = 'VALUE'
        vignette_intensity_socket.structure_type = 'AUTO'

        # Socket VIGNETTE SHARPNESS
        vignette_sharpness_socket = aptpro_vignette.interface.new_socket(name="VIGNETTE SHARPNESS", in_out='INPUT', socket_type='NodeSocketFloat')
        vignette_sharpness_socket.default_value = 1.0
        vignette_sharpness_socket.min_value = 0.0
        vignette_sharpness_socket.max_value = 1.0
        vignette_sharpness_socket.subtype = 'NONE'
        vignette_sharpness_socket.attribute_domain = 'POINT'
        vignette_sharpness_socket.default_input = 'VALUE'
        vignette_sharpness_socket.structure_type = 'AUTO'

        # Socket VIGNETTE AMOUNT
        vignette_amount_socket_1 = aptpro_vignette.interface.new_socket(name="VIGNETTE AMOUNT", in_out='INPUT', socket_type='NodeSocketFloat')
        vignette_amount_socket_1.default_value = 1.0
        vignette_amount_socket_1.min_value = 0.0
        vignette_amount_socket_1.max_value = 1.0
        vignette_amount_socket_1.subtype = 'NONE'
        vignette_amount_socket_1.attribute_domain = 'POINT'
        vignette_amount_socket_1.default_input = 'VALUE'
        vignette_amount_socket_1.structure_type = 'AUTO'

        # Initialize aptpro_vignette nodes

        # Node VignetteOut
        vignetteout = aptpro_vignette.nodes.new("NodeGroupOutput")
        vignetteout.label = "VignetteOut"
        vignetteout.name = "VignetteOut"
        vignetteout.is_active_output = True

        # Node VignetteIn
        vignettein = aptpro_vignette.nodes.new("NodeGroupInput")
        vignettein.label = "VignetteIn"
        vignettein.name = "VignetteIn"

        # Node VignetteMask
        vignettemask = aptpro_vignette.nodes.new("CompositorNodeEllipseMask")
        vignettemask.label = "VignetteMask"
        vignettemask.name = "VignetteMask"
        vignettemask.mask_type = 'ADD'
        # Value
        vignettemask.inputs[1].default_value = 1.0
        # Position
        vignettemask.inputs[2].default_value = (0.5, 0.5)
        # Size
        vignettemask.inputs[3].default_value = (1.0, 0.75)
        # Rotation
        vignettemask.inputs[4].default_value = 0.0

        # Node VignetteBlur
        vignetteblur = aptpro_vignette.nodes.new("CompositorNodeBlur")
        vignetteblur.label = "VignetteBlur"
        vignetteblur.name = "VignetteBlur"
        vignetteblur.filter_type = 'GAUSS'
        # Extend Bounds
        vignetteblur.inputs[2].default_value = False
        # Separable
        vignetteblur.inputs[3].default_value = True

        # Node VignetteIntensityMath
        vignetteintensitymath = aptpro_vignette.nodes.new("ShaderNodeMath")
        vignetteintensitymath.label = "VignetteIntensityMath"
        vignetteintensitymath.name = "VignetteIntensityMath"
        vignetteintensitymath.operation = 'MULTIPLY_ADD'
        vignetteintensitymath.use_clamp = True
        # Value_001
        vignetteintensitymath.inputs[1].default_value = -1.0
        # Value_002
        vignetteintensitymath.inputs[2].default_value = 1.0

        # Node VignetteGamma
        vignettegamma = aptpro_vignette.nodes.new("CompositorNodeGamma")
        vignettegamma.label = "VignetteGamma"
        vignettegamma.name = "VignetteGamma"
        # Gamma
        vignettegamma.inputs[1].default_value = 2.0

        # Node VigBlurGamma
        vigblurgamma = aptpro_vignette.nodes.new("CompositorNodeGamma")
        vigblurgamma.label = "VigBlurGamma"
        vigblurgamma.name = "VigBlurGamma"
        # Gamma
        vigblurgamma.inputs[1].default_value = 0.5

        # Node VignetteSharpnessVector
        vignettesharpnessvector = aptpro_vignette.nodes.new("ShaderNodeVectorMath")
        vignettesharpnessvector.label = "VignetteSharpnessVector"
        vignettesharpnessvector.name = "VignetteSharpnessVector"
        vignettesharpnessvector.operation = 'SCALE'
        # Vector
        vignettesharpnessvector.inputs[0].default_value = (300.0, 300.0, 300.0)

        # Set locations
        vignetteout.location = (1188.94775390625, 27.70817756652832)
        vignettein.location = (-561.3836059570312, 0.0)
        vignettemask.location = (24.23175048828125, 138.0729522705078)
        vignetteblur.location = (745.866455078125, 140.21971130371094)
        vignetteintensitymath.location = (-182.26707458496094, 139.30821228027344)
        vignettegamma.location = (419.08740234375, 118.57060241699219)
        vigblurgamma.location = (969.5224609375, 108.38270568847656)
        vignettesharpnessvector.location = (414.3648986816406, -128.48526000976562)

        # Set dimensions
        vignetteout.width, vignetteout.height = 140.0, 100.0
        vignettein.width, vignettein.height = 140.0, 100.0
        vignettemask.width, vignettemask.height = 260.0, 100.0
        vignetteblur.width, vignetteblur.height = 140.0, 100.0
        vignetteintensitymath.width, vignetteintensitymath.height = 140.0, 100.0
        vignettegamma.width, vignettegamma.height = 140.0, 100.0
        vigblurgamma.width, vigblurgamma.height = 140.0, 100.0
        vignettesharpnessvector.width, vignettesharpnessvector.height = 140.0, 100.0

        # Initialize aptpro_vignette links

        # vignetteintensitymath.Value -> vignettemask.Mask
        aptpro_vignette.links.new(vignetteintensitymath.outputs[0], vignettemask.inputs[0])
        # vignettein.VIGNETTE INTENSITY -> vignetteintensitymath.Value
        aptpro_vignette.links.new(vignettein.outputs[0], vignetteintensitymath.inputs[0])
        # vignettein.VIGNETTE AMOUNT -> vignetteout.VIGNETTE AMOUNT
        aptpro_vignette.links.new(vignettein.outputs[2], vignetteout.inputs[1])
        # vignettemask.Mask -> vignettegamma.Image
        aptpro_vignette.links.new(vignettemask.outputs[0], vignettegamma.inputs[0])
        # vignettegamma.Image -> vignetteblur.Image
        aptpro_vignette.links.new(vignettegamma.outputs[0], vignetteblur.inputs[0])
        # vignetteblur.Image -> vigblurgamma.Image
        aptpro_vignette.links.new(vignetteblur.outputs[0], vigblurgamma.inputs[0])
        # vigblurgamma.Image -> vignetteout.Image
        aptpro_vignette.links.new(vigblurgamma.outputs[0], vignetteout.inputs[0])
        # vignettein.VIGNETTE SHARPNESS -> vignettesharpnessvector.Scale
        aptpro_vignette.links.new(vignettein.outputs[1], vignettesharpnessvector.inputs[3])
        # vignettesharpnessvector.Vector -> vignetteblur.Size
        aptpro_vignette.links.new(vignettesharpnessvector.outputs[0], vignetteblur.inputs[1])

        return aptpro_vignette

    aptpro_vignette = aptpro_vignette_node_group()

    def aptpro_compression_effects_node_group():
        """Initialize AptPro COMPRESSION EFFECTS node group"""
        aptpro_compression_effects = bpy.data.node_groups.new(type = 'CompositorNodeTree', name = "AptPro COMPRESSION EFFECTS")

        aptpro_compression_effects.color_tag = 'NONE'
        aptpro_compression_effects.description = ""
        aptpro_compression_effects.default_group_node_width = 140
        aptpro_compression_effects.use_fake_user = True
        # aptpro_compression_effects interface

        # Socket Image
        image_socket_3 = aptpro_compression_effects.interface.new_socket(name="Image", in_out='OUTPUT', socket_type='NodeSocketColor')
        image_socket_3.default_value = (0.800000011920929, 0.800000011920929, 0.800000011920929, 1.0)
        image_socket_3.attribute_domain = 'POINT'
        image_socket_3.default_input = 'VALUE'
        image_socket_3.structure_type = 'AUTO'

        # Socket Image
        image_socket_4 = aptpro_compression_effects.interface.new_socket(name="Image", in_out='INPUT', socket_type='NodeSocketColor')
        image_socket_4.default_value = (1.0, 1.0, 1.0, 1.0)
        image_socket_4.attribute_domain = 'POINT'
        image_socket_4.default_input = 'VALUE'
        image_socket_4.structure_type = 'AUTO'

        # Socket COMPRESSION INTENSITY
        compression_intensity_socket = aptpro_compression_effects.interface.new_socket(name="COMPRESSION INTENSITY", in_out='INPUT', socket_type='NodeSocketFloat')
        compression_intensity_socket.default_value = 0.02500000037252903
        compression_intensity_socket.min_value = 0.0
        compression_intensity_socket.max_value = 0.05000000074505806
        compression_intensity_socket.subtype = 'FACTOR'
        compression_intensity_socket.attribute_domain = 'POINT'
        compression_intensity_socket.default_input = 'VALUE'
        compression_intensity_socket.structure_type = 'AUTO'

        # Socket COMPRESSION NOISE SCALE
        compression_noise_scale_socket = aptpro_compression_effects.interface.new_socket(name="COMPRESSION NOISE SCALE", in_out='INPUT', socket_type='NodeSocketFloat')
        compression_noise_scale_socket.default_value = 0.0
        compression_noise_scale_socket.min_value = 0.0
        compression_noise_scale_socket.max_value = 100.0
        compression_noise_scale_socket.subtype = 'FACTOR'
        compression_noise_scale_socket.attribute_domain = 'POINT'
        compression_noise_scale_socket.default_input = 'VALUE'
        compression_noise_scale_socket.structure_type = 'AUTO'

        # Socket COMPRESSION NOISE BLEND
        compression_noise_blend_socket = aptpro_compression_effects.interface.new_socket(name="COMPRESSION NOISE BLEND", in_out='INPUT', socket_type='NodeSocketFloat')
        compression_noise_blend_socket.default_value = 1.0
        compression_noise_blend_socket.min_value = 0.0
        compression_noise_blend_socket.max_value = 1.0
        compression_noise_blend_socket.subtype = 'NONE'
        compression_noise_blend_socket.attribute_domain = 'POINT'
        compression_noise_blend_socket.default_input = 'VALUE'
        compression_noise_blend_socket.structure_type = 'AUTO'

        # Socket Pixelation Size
        pixelation_size_socket = aptpro_compression_effects.interface.new_socket(name="Pixelation Size", in_out='INPUT', socket_type='NodeSocketInt')
        pixelation_size_socket.default_value = 5
        pixelation_size_socket.min_value = 1
        pixelation_size_socket.max_value = 2147483647
        pixelation_size_socket.subtype = 'NONE'
        pixelation_size_socket.attribute_domain = 'POINT'
        pixelation_size_socket.description = "The number of pixels that correspond to the same output pixel"
        pixelation_size_socket.default_input = 'VALUE'
        pixelation_size_socket.structure_type = 'AUTO'

        # Socket Compression softness
        compression_softness_socket = aptpro_compression_effects.interface.new_socket(name="Compression softness", in_out='INPUT', socket_type='NodeSocketFloat')
        compression_softness_socket.default_value = 0.0
        compression_softness_socket.min_value = 0.0
        compression_softness_socket.max_value = 100.0
        compression_softness_socket.subtype = 'NONE'
        compression_softness_socket.attribute_domain = 'POINT'
        compression_softness_socket.default_input = 'VALUE'
        compression_softness_socket.structure_type = 'AUTO'

        # Initialize aptpro_compression_effects nodes

        # Node Cout
        cout = aptpro_compression_effects.nodes.new("NodeGroupOutput")
        cout.label = "Cout"
        cout.name = "Cout"
        cout.is_active_output = True

        # Node Cin
        cin = aptpro_compression_effects.nodes.new("NodeGroupInput")
        cin.label = "Cin"
        cin.name = "Cin"

        # Node CompIntensityLighten
        compintensitylighten = aptpro_compression_effects.nodes.new("ShaderNodeMix")
        compintensitylighten.label = "CompIntensityLighten"
        compintensitylighten.name = "CompIntensityLighten"
        compintensitylighten.blend_type = 'LIGHTEN'
        compintensitylighten.clamp_factor = False
        compintensitylighten.clamp_result = False
        compintensitylighten.data_type = 'RGBA'
        compintensitylighten.factor_mode = 'UNIFORM'

        # Node CompressionNode
        compressionnode = aptpro_compression_effects.nodes.new("CompositorNodeTexture")
        compressionnode.label = "CompressionNode"
        compressionnode.name = "CompressionNode"
        compressionnode.node_output = 0
        # Offset
        compressionnode.texture = bpy.data.textures.get("FX_AptCompression")            
        fcurvex = compressionnode.inputs["Offset"].driver_add('default_value', 0)
        fcurvex.driver.type = 'SCRIPTED'
        fcurvex.driver.expression = "frame"
        
        fcurvey = compressionnode.inputs["Offset"].driver_add('default_value', 1)
        fcurvey.driver.type = 'SCRIPTED'
        fcurvey.driver.expression = "frame"
        
        fcurvez = compressionnode.inputs["Offset"].driver_add('default_value', 2)
        fcurvez.driver.type = 'SCRIPTED'
        fcurvez.driver.expression = "frame"

        # Node CompPixelate
        comppixelate = aptpro_compression_effects.nodes.new("CompositorNodePixelate")
        comppixelate.label = "CompPixelate"
        comppixelate.name = "CompPixelate"

        # Node CompBlur
        compblur = aptpro_compression_effects.nodes.new("CompositorNodeBlur")
        compblur.label = "CompBlur"
        compblur.name = "CompBlur"
        compblur.filter_type = 'GAUSS'
        # Extend Bounds
        compblur.inputs[2].default_value = False
        # Separable
        compblur.inputs[3].default_value = True

        # Node CompPixelateGamma
        comppixelategamma = aptpro_compression_effects.nodes.new("CompositorNodeGamma")
        comppixelategamma.label = "CompPixelateGamma"
        comppixelategamma.name = "CompPixelateGamma"
        # Gamma
        comppixelategamma.inputs[1].default_value = 2.0

        # Node CompBlurGamma
        compblurgamma = aptpro_compression_effects.nodes.new("CompositorNodeGamma")
        compblurgamma.label = "CompBlurGamma"
        compblurgamma.name = "CompBlurGamma"
        # Gamma
        compblurgamma.inputs[1].default_value = 0.5

        # Node CompBlurScale
        compblurscale = aptpro_compression_effects.nodes.new("ShaderNodeVectorMath")
        compblurscale.label = "CompBlurScale"
        compblurscale.name = "CompBlurScale"
        compblurscale.operation = 'SCALE'

        # Set locations
        cout.location = (594.4918212890625, 83.64755249023438)
        cin.location = (-1402.1431884765625, -19.23568344116211)
        compintensitylighten.location = (400.58856201171875, 134.58631896972656)
        compressionnode.location = (-963.373046875, -464.2499694824219)
        comppixelate.location = (-589.7176513671875, -363.9341735839844)
        compblur.location = (-225.56434631347656, -154.664306640625)
        comppixelategamma.location = (-429.63031005859375, -355.76934814453125)
        compblurgamma.location = (4.228263854980469, -147.1590576171875)
        compblurscale.location = (-428.4796447753906, -199.59588623046875)

        # Set dimensions
        cout.width, cout.height = 140.0, 100.0
        cin.width, cin.height = 246.2760009765625, 100.0
        compintensitylighten.width, compintensitylighten.height = 140.0, 100.0
        compressionnode.width, compressionnode.height = 278.7259521484375, 100.0
        comppixelate.width, comppixelate.height = 140.0, 100.0
        compblur.width, compblur.height = 140.0, 100.0
        comppixelategamma.width, comppixelategamma.height = 140.0, 100.0
        compblurgamma.width, compblurgamma.height = 140.0, 100.0
        compblurscale.width, compblurscale.height = 140.0, 100.0

        # Initialize aptpro_compression_effects links

        # cin.Image -> compintensitylighten.A
        aptpro_compression_effects.links.new(cin.outputs[0], compintensitylighten.inputs[6])
        # cin.COMPRESSION INTENSITY -> compintensitylighten.Factor
        aptpro_compression_effects.links.new(cin.outputs[1], compintensitylighten.inputs[0])
        # compressionnode.Color -> comppixelate.Color
        aptpro_compression_effects.links.new(compressionnode.outputs[1], comppixelate.inputs[0])
        # compintensitylighten.Result -> cout.Image
        aptpro_compression_effects.links.new(compintensitylighten.outputs[2], cout.inputs[0])
        # cin.COMPRESSION NOISE SCALE -> compressionnode.Scale
        aptpro_compression_effects.links.new(cin.outputs[2], compressionnode.inputs[1])
        # comppixelate.Color -> comppixelategamma.Image
        aptpro_compression_effects.links.new(comppixelate.outputs[0], comppixelategamma.inputs[0])
        # comppixelategamma.Image -> compblur.Image
        aptpro_compression_effects.links.new(comppixelategamma.outputs[0], compblur.inputs[0])
        # compblur.Image -> compblurgamma.Image
        aptpro_compression_effects.links.new(compblur.outputs[0], compblurgamma.inputs[0])
        # compblurscale.Vector -> compblur.Size
        aptpro_compression_effects.links.new(compblurscale.outputs[0], compblur.inputs[1])
        # cin.Pixelation Size -> comppixelate.Size
        aptpro_compression_effects.links.new(cin.outputs[4], comppixelate.inputs[1])
        # cin.Compression softness -> compblurscale.Vector
        aptpro_compression_effects.links.new(cin.outputs[5], compblurscale.inputs[0])
        # cin.COMPRESSION NOISE BLEND -> compblurscale.Scale
        aptpro_compression_effects.links.new(cin.outputs[3], compblurscale.inputs[3])
        # compblurgamma.Image -> compintensitylighten.B
        aptpro_compression_effects.links.new(compblurgamma.outputs[0], compintensitylighten.inputs[7])

        return aptpro_compression_effects

    aptpro_compression_effects = aptpro_compression_effects_node_group()

    def noiseprofile1_node_group():
        """Initialize Noiseprofile1 node group"""
        noiseprofile1 = bpy.data.node_groups.new(type = 'CompositorNodeTree', name = "Noiseprofile1")

        noiseprofile1.color_tag = 'NONE'
        noiseprofile1.description = ""
        noiseprofile1.default_group_node_width = 140
        noiseprofile1.use_fake_user = True
        # noiseprofile1 interface

        # Socket Image
        image_socket_5 = noiseprofile1.interface.new_socket(name="Image", in_out='OUTPUT', socket_type='NodeSocketColor')
        image_socket_5.default_value = (0.800000011920929, 0.800000011920929, 0.800000011920929, 1.0)
        image_socket_5.attribute_domain = 'POINT'
        image_socket_5.default_input = 'VALUE'
        image_socket_5.structure_type = 'AUTO'

        # Socket Offset
        offset_socket = noiseprofile1.interface.new_socket(name="Offset", in_out='INPUT', socket_type='NodeSocketVector')
        offset_socket.default_value = (1.0, 1.0, 1.0)
        offset_socket.min_value = -2.0
        offset_socket.max_value = 2.0
        offset_socket.subtype = 'TRANSLATION'
        offset_socket.attribute_domain = 'POINT'
        offset_socket.default_input = 'VALUE'
        offset_socket.structure_type = 'AUTO'

        # Socket Scale
        scale_socket = noiseprofile1.interface.new_socket(name="Scale", in_out='INPUT', socket_type='NodeSocketVector')
        scale_socket.default_value = (50.0, 50.0, 50.0)
        scale_socket.min_value = -10.0
        scale_socket.max_value = 10.0
        scale_socket.subtype = 'XYZ'
        scale_socket.attribute_domain = 'POINT'
        scale_socket.default_input = 'VALUE'
        scale_socket.structure_type = 'AUTO'

        # Initialize noiseprofile1 nodes

        # Node Group Output
        group_output = noiseprofile1.nodes.new("NodeGroupOutput")
        group_output.name = "Group Output"
        group_output.is_active_output = True

        # Node Group Input
        group_input = noiseprofile1.nodes.new("NodeGroupInput")
        group_input.name = "Group Input"

        # Node Noise11
        noise11 = noiseprofile1.nodes.new("CompositorNodeTexture")
        noise11.label = "Noise11"
        noise11.name = "Noise11"
        noise11.node_output = 0
        noise11.texture = bpy.data.textures.get("FX_AptNoise1.1")

        # Node Noise12
        noise12 = noiseprofile1.nodes.new("CompositorNodeTexture")
        noise12.label = "Noise12"
        noise12.name = "Noise12"
        noise12.node_output = 0
        noise12.texture = bpy.data.textures.get("FX_AptNoise1.2")

        # Node Noise1Div
        noise1div = noiseprofile1.nodes.new("ShaderNodeMix")
        noise1div.label = "Noise1Div"
        noise1div.name = "Noise1Div"
        noise1div.blend_type = 'DIVIDE'
        noise1div.clamp_factor = False
        noise1div.clamp_result = True
        noise1div.data_type = 'RGBA'
        noise1div.factor_mode = 'UNIFORM'
        # Factor_Float
        noise1div.inputs[0].default_value = 1.0

        # Node Noise1Mult
        noise1mult = noiseprofile1.nodes.new("ShaderNodeVectorMath")
        noise1mult.label = "Noise1Mult"
        noise1mult.name = "Noise1Mult"
        noise1mult.operation = 'MULTIPLY'
        # Vector_001
        noise1mult.inputs[1].default_value = (50.0, 50.0, 50.0)

        # Set locations
        group_output.location = (449.4483642578125, 0.0)
        group_input.location = (-731.782470703125, -1.3780033588409424)
        noise11.location = (-255.81903076171875, 196.86419677734375)
        noise12.location = (-250.40345764160156, -196.8641357421875)
        noise1div.location = (259.4483642578125, -33.19232177734375)
        noise1mult.location = (-435.33770751953125, 2.084564208984375)

        # Set dimensions
        group_output.width, group_output.height = 140.0, 100.0
        group_input.width, group_input.height = 140.0, 100.0
        noise11.width, noise11.height = 285.9837951660156, 100.0
        noise12.width, noise12.height = 284.69342041015625, 100.0
        noise1div.width, noise1div.height = 140.0, 100.0
        noise1mult.width, noise1mult.height = 140.0, 100.0

        # Initialize noiseprofile1 links

        # noise12.Color -> noise1div.B
        noiseprofile1.links.new(noise12.outputs[1], noise1div.inputs[7])
        # noise11.Color -> noise1div.A
        noiseprofile1.links.new(noise11.outputs[1], noise1div.inputs[6])
        # noise1div.Result -> group_output.Image
        noiseprofile1.links.new(noise1div.outputs[2], group_output.inputs[0])
        # group_input.Offset -> noise12.Offset
        noiseprofile1.links.new(group_input.outputs[0], noise12.inputs[0])
        # group_input.Offset -> noise11.Offset
        noiseprofile1.links.new(group_input.outputs[0], noise11.inputs[0])
        # group_input.Scale -> noise1mult.Vector
        noiseprofile1.links.new(group_input.outputs[1], noise1mult.inputs[0])
        # noise1mult.Vector -> noise11.Scale
        noiseprofile1.links.new(noise1mult.outputs[0], noise11.inputs[1])
        # noise1mult.Vector -> noise12.Scale
        noiseprofile1.links.new(noise1mult.outputs[0], noise12.inputs[1])

        return noiseprofile1

    noiseprofile1 = noiseprofile1_node_group()

    def noiseprofile2_node_group():
        """Initialize Noiseprofile2 node group"""
        noiseprofile2 = bpy.data.node_groups.new(type = 'CompositorNodeTree', name = "Noiseprofile2")

        noiseprofile2.color_tag = 'NONE'
        noiseprofile2.description = ""
        noiseprofile2.default_group_node_width = 140
        noiseprofile2.use_fake_user = True
        # noiseprofile2 interface

        # Socket Image
        image_socket_6 = noiseprofile2.interface.new_socket(name="Image", in_out='OUTPUT', socket_type='NodeSocketColor')
        image_socket_6.default_value = (0.800000011920929, 0.800000011920929, 0.800000011920929, 1.0)
        image_socket_6.attribute_domain = 'POINT'
        image_socket_6.default_input = 'VALUE'
        image_socket_6.structure_type = 'AUTO'

        # Socket Offset
        offset_socket_1 = noiseprofile2.interface.new_socket(name="Offset", in_out='INPUT', socket_type='NodeSocketVector')
        offset_socket_1.default_value = (1.0, 1.0, 1.0)
        offset_socket_1.min_value = -2.0
        offset_socket_1.max_value = 2.0
        offset_socket_1.subtype = 'TRANSLATION'
        offset_socket_1.attribute_domain = 'POINT'
        offset_socket_1.default_input = 'VALUE'
        offset_socket_1.structure_type = 'AUTO'

        # Socket Scale
        scale_socket_1 = noiseprofile2.interface.new_socket(name="Scale", in_out='INPUT', socket_type='NodeSocketVector')
        scale_socket_1.default_value = (0.0, 0.0, 0.0)
        scale_socket_1.min_value = -10000.0
        scale_socket_1.max_value = 10000.0
        scale_socket_1.subtype = 'NONE'
        scale_socket_1.attribute_domain = 'POINT'
        scale_socket_1.default_input = 'VALUE'
        scale_socket_1.structure_type = 'AUTO'

        # Initialize noiseprofile2 nodes

        # Node Group Output
        group_output_1 = noiseprofile2.nodes.new("NodeGroupOutput")
        group_output_1.name = "Group Output"
        group_output_1.is_active_output = True

        # Node Group Input
        group_input_1 = noiseprofile2.nodes.new("NodeGroupInput")
        group_input_1.name = "Group Input"

        # Node Noise21
        noise21 = noiseprofile2.nodes.new("CompositorNodeTexture")
        noise21.label = "Noise21"
        noise21.name = "Noise21"
        noise21.node_output = 0
        noise21.texture = bpy.data.textures.get("FX_AptNoise2.1")

        # Node Noise22
        noise22 = noiseprofile2.nodes.new("CompositorNodeTexture")
        noise22.label = "Noise22"
        noise22.name = "Noise22"
        noise22.node_output = 0
        noise22.texture = bpy.data.textures.get("FX_AptNoise2.2")

        # Node Noise2Mix
        noise2mix = noiseprofile2.nodes.new("ShaderNodeMix")
        noise2mix.label = "Noise2Mix"
        noise2mix.name = "Noise2Mix"
        noise2mix.blend_type = 'MIX'
        noise2mix.clamp_factor = False
        noise2mix.clamp_result = True
        noise2mix.data_type = 'RGBA'
        noise2mix.factor_mode = 'UNIFORM'
        # Factor_Float
        noise2mix.inputs[0].default_value = 0.5

        # Node Noise21Mult
        noise21mult = noiseprofile2.nodes.new("ShaderNodeVectorMath")
        noise21mult.label = "Noise21Mult"
        noise21mult.name = "Noise21Mult"
        noise21mult.operation = 'MULTIPLY'
        # Vector_001
        noise21mult.inputs[1].default_value = (100.0, 100.0, 100.0)

        # Node Noise22Mult
        noise22mult = noiseprofile2.nodes.new("ShaderNodeVectorMath")
        noise22mult.label = "Noise22Mult"
        noise22mult.name = "Noise22Mult"
        noise22mult.operation = 'MULTIPLY'
        # Vector_001
        noise22mult.inputs[1].default_value = (200.0, 200.0, 200.0)

        # Set locations
        group_output_1.location = (632.9320068359375, -7.752344131469727)
        group_input_1.location = (-926.2235717773438, -20.67005157470703)
        noise21.location = (-255.81903076171875, 196.86419677734375)
        noise22.location = (-256.0352478027344, -222.13479614257812)
        noise2mix.location = (274.9539489746094, -15.103309631347656)
        noise21mult.location = (-448.677734375, 354.0921630859375)
        noise22mult.location = (-447.30010986328125, -8.322662353515625)

        # Set dimensions
        group_output_1.width, group_output_1.height = 140.0, 100.0
        group_input_1.width, group_input_1.height = 140.0, 100.0
        noise21.width, noise21.height = 256.2325744628906, 100.0
        noise22.width, noise22.height = 260.62762451171875, 100.0
        noise2mix.width, noise2mix.height = 140.0, 100.0
        noise21mult.width, noise21mult.height = 140.0, 100.0
        noise22mult.width, noise22mult.height = 140.0, 100.0

        # Initialize noiseprofile2 links

        # noise21.Color -> noise2mix.A
        noiseprofile2.links.new(noise21.outputs[1], noise2mix.inputs[6])
        # noise22.Color -> noise2mix.B
        noiseprofile2.links.new(noise22.outputs[1], noise2mix.inputs[7])
        # noise2mix.Result -> group_output_1.Image
        noiseprofile2.links.new(noise2mix.outputs[2], group_output_1.inputs[0])
        # group_input_1.Offset -> noise21.Offset
        noiseprofile2.links.new(group_input_1.outputs[0], noise21.inputs[0])
        # group_input_1.Offset -> noise22.Offset
        noiseprofile2.links.new(group_input_1.outputs[0], noise22.inputs[0])
        # group_input_1.Scale -> noise22mult.Vector
        noiseprofile2.links.new(group_input_1.outputs[1], noise22mult.inputs[0])
        # group_input_1.Scale -> noise21mult.Vector
        noiseprofile2.links.new(group_input_1.outputs[1], noise21mult.inputs[0])
        # noise21mult.Vector -> noise21.Scale
        noiseprofile2.links.new(noise21mult.outputs[0], noise21.inputs[1])
        # noise22mult.Vector -> noise22.Scale
        noiseprofile2.links.new(noise22mult.outputs[0], noise22.inputs[1])

        return noiseprofile2

    noiseprofile2 = noiseprofile2_node_group()

    def noiseprofile3_node_group():
        """Initialize Noiseprofile3 node group"""
        noiseprofile3 = bpy.data.node_groups.new(type = 'CompositorNodeTree', name = "Noiseprofile3")

        noiseprofile3.color_tag = 'NONE'
        noiseprofile3.description = ""
        noiseprofile3.default_group_node_width = 140
        noiseprofile3.use_fake_user = True
        # noiseprofile3 interface

        # Socket Image
        image_socket_7 = noiseprofile3.interface.new_socket(name="Image", in_out='OUTPUT', socket_type='NodeSocketColor')
        image_socket_7.default_value = (0.800000011920929, 0.800000011920929, 0.800000011920929, 1.0)
        image_socket_7.attribute_domain = 'POINT'
        image_socket_7.default_input = 'VALUE'
        image_socket_7.structure_type = 'AUTO'

        # Socket Offset
        offset_socket_2 = noiseprofile3.interface.new_socket(name="Offset", in_out='INPUT', socket_type='NodeSocketVector')
        offset_socket_2.default_value = (1.0, 1.0, 1.0)
        offset_socket_2.min_value = -2.0
        offset_socket_2.max_value = 2.0
        offset_socket_2.subtype = 'TRANSLATION'
        offset_socket_2.attribute_domain = 'POINT'
        offset_socket_2.default_input = 'VALUE'
        offset_socket_2.structure_type = 'AUTO'

        # Socket Scale
        scale_socket_2 = noiseprofile3.interface.new_socket(name="Scale", in_out='INPUT', socket_type='NodeSocketVector')
        scale_socket_2.default_value = (25.0, 25.0, 25.0)
        scale_socket_2.min_value = -10.0
        scale_socket_2.max_value = 10.0
        scale_socket_2.subtype = 'XYZ'
        scale_socket_2.attribute_domain = 'POINT'
        scale_socket_2.default_input = 'VALUE'
        scale_socket_2.structure_type = 'AUTO'

        # Initialize noiseprofile3 nodes

        # Node Group Output
        group_output_2 = noiseprofile3.nodes.new("NodeGroupOutput")
        group_output_2.name = "Group Output"
        group_output_2.is_active_output = True

        # Node Group Input
        group_input_2 = noiseprofile3.nodes.new("NodeGroupInput")
        group_input_2.name = "Group Input"

        # Node Noise31
        noise31 = noiseprofile3.nodes.new("CompositorNodeTexture")
        noise31.label = "Noise31"
        noise31.name = "Noise31"
        noise31.node_output = 0
        noise31.texture = bpy.data.textures.get("FX_AptNoise3.1")

        # Node Noise32
        noise32 = noiseprofile3.nodes.new("CompositorNodeTexture")
        noise32.label = "Noise32"
        noise32.name = "Noise32"
        noise32.node_output = 0
        noise32.texture = bpy.data.textures.get("FX_AptNoise3.2")

        # Node Noise3Mix
        noise3mix = noiseprofile3.nodes.new("ShaderNodeMix")
        noise3mix.label = "Noise3Mix"
        noise3mix.name = "Noise3Mix"
        noise3mix.blend_type = 'MIX'
        noise3mix.clamp_factor = False
        noise3mix.clamp_result = True
        noise3mix.data_type = 'RGBA'
        noise3mix.factor_mode = 'UNIFORM'
        # Factor_Float
        noise3mix.inputs[0].default_value = 0.5

        # Node Noise31Mult
        noise31mult = noiseprofile3.nodes.new("ShaderNodeVectorMath")
        noise31mult.label = "Noise31Mult"
        noise31mult.name = "Noise31Mult"
        noise31mult.operation = 'MULTIPLY'
        # Vector_001
        noise31mult.inputs[1].default_value = (25.0, 25.0, 25.0)

        # Node Noise32Mult
        noise32mult = noiseprofile3.nodes.new("ShaderNodeVectorMath")
        noise32mult.label = "Noise32Mult"
        noise32mult.name = "Noise32Mult"
        noise32mult.operation = 'MULTIPLY'
        # Vector_001
        noise32mult.inputs[1].default_value = (100.0, 100.0, 100.0)

        # Set locations
        group_output_2.location = (632.9320068359375, -7.752344131469727)
        group_input_2.location = (-711.1463623046875, -8.938406944274902)
        noise31.location = (-255.81903076171875, 196.86419677734375)
        noise32.location = (-256.0352478027344, -222.13479614257812)
        noise3mix.location = (274.9539489746094, -15.103309631347656)
        noise31mult.location = (-479.9874572753906, 202.74517822265625)
        noise32mult.location = (-481.4768371582031, -309.72344970703125)

        # Set dimensions
        group_output_2.width, group_output_2.height = 140.0, 100.0
        group_input_2.width, group_input_2.height = 140.0, 100.0
        noise31.width, noise31.height = 256.2325744628906, 100.0
        noise32.width, noise32.height = 260.62762451171875, 100.0
        noise3mix.width, noise3mix.height = 140.0, 100.0
        noise31mult.width, noise31mult.height = 140.0, 100.0
        noise32mult.width, noise32mult.height = 140.0, 100.0

        # Initialize noiseprofile3 links

        # noise3mix.Result -> group_output_2.Image
        noiseprofile3.links.new(noise3mix.outputs[2], group_output_2.inputs[0])
        # noise31.Color -> noise3mix.A
        noiseprofile3.links.new(noise31.outputs[1], noise3mix.inputs[6])
        # noise32.Color -> noise3mix.B
        noiseprofile3.links.new(noise32.outputs[1], noise3mix.inputs[7])
        # group_input_2.Offset -> noise31.Offset
        noiseprofile3.links.new(group_input_2.outputs[0], noise31.inputs[0])
        # group_input_2.Offset -> noise32.Offset
        noiseprofile3.links.new(group_input_2.outputs[0], noise32.inputs[0])
        # group_input_2.Scale -> noise31mult.Vector
        noiseprofile3.links.new(group_input_2.outputs[1], noise31mult.inputs[0])
        # noise31mult.Vector -> noise31.Scale
        noiseprofile3.links.new(noise31mult.outputs[0], noise31.inputs[1])
        # group_input_2.Scale -> noise32mult.Vector
        noiseprofile3.links.new(group_input_2.outputs[1], noise32mult.inputs[0])
        # noise32mult.Vector -> noise32.Scale
        noiseprofile3.links.new(noise32mult.outputs[0], noise32.inputs[1])

        return noiseprofile3

    noiseprofile3 = noiseprofile3_node_group()

    def noiseprofile4_node_group():
        """Initialize Noiseprofile4 node group"""
        noiseprofile4 = bpy.data.node_groups.new(type = 'CompositorNodeTree', name = "Noiseprofile4")

        noiseprofile4.color_tag = 'NONE'
        noiseprofile4.description = ""
        noiseprofile4.default_group_node_width = 140
        noiseprofile4.use_fake_user = True
        # noiseprofile4 interface

        # Socket Image
        image_socket_8 = noiseprofile4.interface.new_socket(name="Image", in_out='OUTPUT', socket_type='NodeSocketColor')
        image_socket_8.default_value = (0.800000011920929, 0.800000011920929, 0.800000011920929, 1.0)
        image_socket_8.attribute_domain = 'POINT'
        image_socket_8.default_input = 'VALUE'
        image_socket_8.structure_type = 'AUTO'

        # Socket Offset
        offset_socket_3 = noiseprofile4.interface.new_socket(name="Offset", in_out='INPUT', socket_type='NodeSocketVector')
        offset_socket_3.default_value = (1.0, 1.0, 1.0)
        offset_socket_3.min_value = -2.0
        offset_socket_3.max_value = 2.0
        offset_socket_3.subtype = 'TRANSLATION'
        offset_socket_3.attribute_domain = 'POINT'
        offset_socket_3.default_input = 'VALUE'
        offset_socket_3.structure_type = 'AUTO'

        # Socket Scale
        scale_socket_3 = noiseprofile4.interface.new_socket(name="Scale", in_out='INPUT', socket_type='NodeSocketVector')
        scale_socket_3.default_value = (0.0, 250.0, 250.0)
        scale_socket_3.min_value = -10.0
        scale_socket_3.max_value = 10.0
        scale_socket_3.subtype = 'XYZ'
        scale_socket_3.attribute_domain = 'POINT'
        scale_socket_3.default_input = 'VALUE'
        scale_socket_3.structure_type = 'AUTO'

        # Initialize noiseprofile4 nodes

        # Node Group Output
        group_output_3 = noiseprofile4.nodes.new("NodeGroupOutput")
        group_output_3.name = "Group Output"
        group_output_3.is_active_output = True

        # Node Group Input
        group_input_3 = noiseprofile4.nodes.new("NodeGroupInput")
        group_input_3.name = "Group Input"

        # Node Noise41
        noise41 = noiseprofile4.nodes.new("CompositorNodeTexture")
        noise41.label = "Noise41"
        noise41.name = "Noise41"
        noise41.node_output = 0
        noise41.texture = bpy.data.textures.get("FX_AptNoise4.1")

        # Node Noise42
        noise42 = noiseprofile4.nodes.new("CompositorNodeTexture")
        noise42.label = "Noise42"
        noise42.name = "Noise42"
        noise42.node_output = 0
        noise42.texture = bpy.data.textures.get("FX_AptNoise4.2")

        # Node Noise4Add
        noise4add = noiseprofile4.nodes.new("ShaderNodeMix")
        noise4add.label = "Noise4Add"
        noise4add.name = "Noise4Add"
        noise4add.blend_type = 'ADD'
        noise4add.clamp_factor = False
        noise4add.clamp_result = True
        noise4add.data_type = 'RGBA'
        noise4add.factor_mode = 'UNIFORM'
        # Factor_Float
        noise4add.inputs[0].default_value = 1.0

        # Node Noise42Mult
        noise42mult = noiseprofile4.nodes.new("ShaderNodeVectorMath")
        noise42mult.label = "Noise42Mult"
        noise42mult.name = "Noise42Mult"
        noise42mult.operation = 'MULTIPLY'
        # Vector_001
        noise42mult.inputs[1].default_value = (250.0, 250.0, 250.0)

        # Node Noise41Mult
        noise41mult = noiseprofile4.nodes.new("ShaderNodeVectorMath")
        noise41mult.label = "Noise41Mult"
        noise41mult.name = "Noise41Mult"
        noise41mult.operation = 'MULTIPLY'
        # Vector_001
        noise41mult.inputs[1].default_value = (0.0, 250.0, 250.0)

        # Set locations
        group_output_3.location = (632.9320068359375, -7.752344131469727)
        group_input_3.location = (-679.8707275390625, -16.387113571166992)
        noise41.location = (-255.81903076171875, 196.86419677734375)
        noise42.location = (-256.0352478027344, -222.13479614257812)
        noise4add.location = (274.9539489746094, -15.103309631347656)
        noise42mult.location = (-470.639892578125, -333.176513671875)
        noise41mult.location = (-465.47406005859375, 283.31378173828125)

        # Set dimensions
        group_output_3.width, group_output_3.height = 140.0, 100.0
        group_input_3.width, group_input_3.height = 140.0, 100.0
        noise41.width, noise41.height = 256.2325744628906, 100.0
        noise42.width, noise42.height = 260.62762451171875, 100.0
        noise4add.width, noise4add.height = 140.0, 100.0
        noise42mult.width, noise42mult.height = 140.0, 100.0
        noise41mult.width, noise41mult.height = 140.0, 100.0

        # Initialize noiseprofile4 links

        # noise4add.Result -> group_output_3.Image
        noiseprofile4.links.new(noise4add.outputs[2], group_output_3.inputs[0])
        # noise41.Color -> noise4add.A
        noiseprofile4.links.new(noise41.outputs[1], noise4add.inputs[6])
        # noise42.Color -> noise4add.B
        noiseprofile4.links.new(noise42.outputs[1], noise4add.inputs[7])
        # group_input_3.Offset -> noise42.Offset
        noiseprofile4.links.new(group_input_3.outputs[0], noise42.inputs[0])
        # group_input_3.Offset -> noise41.Offset
        noiseprofile4.links.new(group_input_3.outputs[0], noise41.inputs[0])
        # group_input_3.Scale -> noise42mult.Vector
        noiseprofile4.links.new(group_input_3.outputs[1], noise42mult.inputs[0])
        # noise42mult.Vector -> noise42.Scale
        noiseprofile4.links.new(noise42mult.outputs[0], noise42.inputs[1])
        # group_input_3.Scale -> noise41mult.Vector
        noiseprofile4.links.new(group_input_3.outputs[1], noise41mult.inputs[0])
        # noise41mult.Vector -> noise41.Scale
        noiseprofile4.links.new(noise41mult.outputs[0], noise41.inputs[1])

        return noiseprofile4

    noiseprofile4 = noiseprofile4_node_group()

    def noiseprofile5_node_group():
        """Initialize Noiseprofile5 node group"""
        noiseprofile5 = bpy.data.node_groups.new(type = 'CompositorNodeTree', name = "Noiseprofile5")

        noiseprofile5.color_tag = 'NONE'
        noiseprofile5.description = ""
        noiseprofile5.default_group_node_width = 140
        noiseprofile5.use_fake_user = True
        # noiseprofile5 interface

        # Socket Image
        image_socket_9 = noiseprofile5.interface.new_socket(name="Image", in_out='OUTPUT', socket_type='NodeSocketColor')
        image_socket_9.default_value = (0.800000011920929, 0.800000011920929, 0.800000011920929, 1.0)
        image_socket_9.attribute_domain = 'POINT'
        image_socket_9.default_input = 'VALUE'
        image_socket_9.structure_type = 'AUTO'

        # Socket Offset
        offset_socket_4 = noiseprofile5.interface.new_socket(name="Offset", in_out='INPUT', socket_type='NodeSocketVector')
        offset_socket_4.default_value = (1.0, 1.0, 1.0)
        offset_socket_4.min_value = -2.0
        offset_socket_4.max_value = 2.0
        offset_socket_4.subtype = 'TRANSLATION'
        offset_socket_4.attribute_domain = 'POINT'
        offset_socket_4.default_input = 'VALUE'
        offset_socket_4.structure_type = 'AUTO'

        # Socket Scale
        scale_socket_4 = noiseprofile5.interface.new_socket(name="Scale", in_out='INPUT', socket_type='NodeSocketVector')
        scale_socket_4.default_value = (25.0, 25.0, 25.0)
        scale_socket_4.min_value = -10.0
        scale_socket_4.max_value = 10.0
        scale_socket_4.subtype = 'XYZ'
        scale_socket_4.attribute_domain = 'POINT'
        scale_socket_4.default_input = 'VALUE'
        scale_socket_4.structure_type = 'AUTO'

        # Initialize noiseprofile5 nodes

        # Node Group Output
        group_output_4 = noiseprofile5.nodes.new("NodeGroupOutput")
        group_output_4.name = "Group Output"
        group_output_4.is_active_output = True

        # Node Group Input
        group_input_4 = noiseprofile5.nodes.new("NodeGroupInput")
        group_input_4.name = "Group Input"

        # Node Noise51
        noise51 = noiseprofile5.nodes.new("CompositorNodeTexture")
        noise51.label = "Noise51"
        noise51.name = "Noise51"
        noise51.node_output = 0
        noise51.texture = bpy.data.textures.get("FX_AptNoise5.1")

        # Node Noise52
        noise52 = noiseprofile5.nodes.new("CompositorNodeTexture")
        noise52.label = "Noise52"
        noise52.name = "Noise52"
        noise52.node_output = 0
        noise52.texture = bpy.data.textures.get("FX_AptNoise5.2")

        # Node Noise5Add
        noise5add = noiseprofile5.nodes.new("ShaderNodeMix")
        noise5add.label = "Noise5Add"
        noise5add.name = "Noise5Add"
        noise5add.hide = True
        noise5add.blend_type = 'ADD'
        noise5add.clamp_factor = False
        noise5add.clamp_result = True
        noise5add.data_type = 'RGBA'
        noise5add.factor_mode = 'UNIFORM'
        # Factor_Float
        noise5add.inputs[0].default_value = 1.0

        # Node Noise52Mult
        noise52mult = noiseprofile5.nodes.new("ShaderNodeVectorMath")
        noise52mult.label = "Noise52Mult"
        noise52mult.name = "Noise52Mult"
        noise52mult.operation = 'MULTIPLY'
        # Vector_001
        noise52mult.inputs[1].default_value = (100.0, 100.0, 100.0)

        # Node Noise51Mult
        noise51mult = noiseprofile5.nodes.new("ShaderNodeVectorMath")
        noise51mult.label = "Noise51Mult"
        noise51mult.name = "Noise51Mult"
        noise51mult.operation = 'MULTIPLY'
        # Vector_001
        noise51mult.inputs[1].default_value = (25.0, 25.0, 25.0)

        # Set locations
        group_output_4.location = (632.9320068359375, -7.752344131469727)
        group_input_4.location = (-750.4776000976562, -37.24351119995117)
        noise51.location = (-255.81903076171875, 196.86419677734375)
        noise52.location = (-256.0352478027344, -222.13479614257812)
        noise5add.location = (274.9539489746094, -15.103309631347656)
        noise52mult.location = (-479.2388610839844, -328.9078369140625)
        noise51mult.location = (-467.3240966796875, 289.33447265625)

        # Set dimensions
        group_output_4.width, group_output_4.height = 140.0, 100.0
        group_input_4.width, group_input_4.height = 140.0, 100.0
        noise51.width, noise51.height = 256.2325744628906, 100.0
        noise52.width, noise52.height = 260.62762451171875, 100.0
        noise5add.width, noise5add.height = 140.0, 100.0
        noise52mult.width, noise52mult.height = 140.0, 100.0
        noise51mult.width, noise51mult.height = 140.0, 100.0

        # Initialize noiseprofile5 links

        # noise5add.Result -> group_output_4.Image
        noiseprofile5.links.new(noise5add.outputs[2], group_output_4.inputs[0])
        # group_input_4.Offset -> noise51.Offset
        noiseprofile5.links.new(group_input_4.outputs[0], noise51.inputs[0])
        # group_input_4.Offset -> noise52.Offset
        noiseprofile5.links.new(group_input_4.outputs[0], noise52.inputs[0])
        # noise52.Color -> noise5add.B
        noiseprofile5.links.new(noise52.outputs[1], noise5add.inputs[7])
        # noise51.Color -> noise5add.A
        noiseprofile5.links.new(noise51.outputs[1], noise5add.inputs[6])
        # group_input_4.Scale -> noise52mult.Vector
        noiseprofile5.links.new(group_input_4.outputs[1], noise52mult.inputs[0])
        # noise52mult.Vector -> noise52.Scale
        noiseprofile5.links.new(noise52mult.outputs[0], noise52.inputs[1])
        # group_input_4.Scale -> noise51mult.Vector
        noiseprofile5.links.new(group_input_4.outputs[1], noise51mult.inputs[0])
        # noise51mult.Vector -> noise51.Scale
        noiseprofile5.links.new(noise51mult.outputs[0], noise51.inputs[1])

        return noiseprofile5

    noiseprofile5 = noiseprofile5_node_group()

    def noiseprofile6_node_group():
        """Initialize Noiseprofile6 node group"""
        noiseprofile6 = bpy.data.node_groups.new(type = 'CompositorNodeTree', name = "Noiseprofile6")

        noiseprofile6.color_tag = 'NONE'
        noiseprofile6.description = ""
        noiseprofile6.default_group_node_width = 140
        noiseprofile6.use_fake_user = True
        # noiseprofile6 interface

        # Socket Image
        image_socket_10 = noiseprofile6.interface.new_socket(name="Image", in_out='OUTPUT', socket_type='NodeSocketColor')
        image_socket_10.default_value = (0.800000011920929, 0.800000011920929, 0.800000011920929, 1.0)
        image_socket_10.attribute_domain = 'POINT'
        image_socket_10.default_input = 'VALUE'
        image_socket_10.structure_type = 'AUTO'

        # Socket Offset
        offset_socket_5 = noiseprofile6.interface.new_socket(name="Offset", in_out='INPUT', socket_type='NodeSocketVector')
        offset_socket_5.default_value = (1.0, 1.0, 1.0)
        offset_socket_5.min_value = -2.0
        offset_socket_5.max_value = 2.0
        offset_socket_5.subtype = 'TRANSLATION'
        offset_socket_5.attribute_domain = 'POINT'
        offset_socket_5.default_input = 'VALUE'
        offset_socket_5.structure_type = 'AUTO'

        # Socket Scale
        scale_socket_5 = noiseprofile6.interface.new_socket(name="Scale", in_out='INPUT', socket_type='NodeSocketVector')
        scale_socket_5.default_value = (25.0, 25.0, 25.0)
        scale_socket_5.min_value = -10.0
        scale_socket_5.max_value = 10.0
        scale_socket_5.subtype = 'XYZ'
        scale_socket_5.attribute_domain = 'POINT'
        scale_socket_5.default_input = 'VALUE'
        scale_socket_5.structure_type = 'AUTO'

        # Initialize noiseprofile6 nodes

        # Node Group Output
        group_output_5 = noiseprofile6.nodes.new("NodeGroupOutput")
        group_output_5.name = "Group Output"
        group_output_5.is_active_output = True

        # Node Group Input
        group_input_5 = noiseprofile6.nodes.new("NodeGroupInput")
        group_input_5.name = "Group Input"

        # Node Noise61
        noise61 = noiseprofile6.nodes.new("CompositorNodeTexture")
        noise61.label = "Noise61"
        noise61.name = "Noise61"
        noise61.node_output = 0
        noise61.texture = bpy.data.textures.get("FX_AptNoise6.1")

        # Node Noise62
        noise62 = noiseprofile6.nodes.new("CompositorNodeTexture")
        noise62.label = "Noise62"
        noise62.name = "Noise62"
        noise62.node_output = 0
        noise62.texture = bpy.data.textures.get("FX_AptNoise6.2")

        # Node Noise6Add
        noise6add = noiseprofile6.nodes.new("ShaderNodeMix")
        noise6add.label = "Noise6Add"
        noise6add.name = "Noise6Add"
        noise6add.blend_type = 'ADD'
        noise6add.clamp_factor = False
        noise6add.clamp_result = True
        noise6add.data_type = 'RGBA'
        noise6add.factor_mode = 'UNIFORM'
        # B_Color
        noise6add.inputs[7].default_value = (0.10000000149011612, 0.10000000149011612, 0.10000000149011612, 1.0)

        # Node Noise61Pixelate
        noise61pixelate = noiseprofile6.nodes.new("CompositorNodePixelate")
        noise61pixelate.label = "Noise61Pixalate"
        noise61pixelate.name = "Noise61Pixelate"
        # Size
        noise61pixelate.inputs[1].default_value = 10

        # Node Noise61Mult
        noise61mult = noiseprofile6.nodes.new("ShaderNodeVectorMath")
        noise61mult.label = "Noise61Mult"
        noise61mult.name = "Noise61Mult"
        noise61mult.operation = 'MULTIPLY'
        # Vector_001
        noise61mult.inputs[1].default_value = (25.0, 25.0, 25.0)

        # Node Noise62Mult
        noise62mult = noiseprofile6.nodes.new("ShaderNodeVectorMath")
        noise62mult.label = "Noise62Mult"
        noise62mult.name = "Noise62Mult"
        noise62mult.operation = 'MULTIPLY'
        # Vector_001
        noise62mult.inputs[1].default_value = (3.0, 3.0, 3.0)

        # Set locations
        group_output_5.location = (632.9320068359375, -7.752344131469727)
        group_input_5.location = (-809.3189697265625, -15.670026779174805)
        noise61.location = (-255.81903076171875, 196.86419677734375)
        noise62.location = (-256.0352478027344, -222.13479614257812)
        noise6add.location = (367.7209167480469, -10.727783203125)
        noise61pixelate.location = (95.0, 66.19591522216797)
        noise61mult.location = (-473.43438720703125, 311.4093322753906)
        noise62mult.location = (-466.4718017578125, -313.650634765625)

        # Set dimensions
        group_output_5.width, group_output_5.height = 140.0, 100.0
        group_input_5.width, group_input_5.height = 140.0, 100.0
        noise61.width, noise61.height = 256.2325744628906, 100.0
        noise62.width, noise62.height = 260.62762451171875, 100.0
        noise6add.width, noise6add.height = 140.0, 100.0
        noise61pixelate.width, noise61pixelate.height = 140.0, 100.0
        noise61mult.width, noise61mult.height = 140.0, 100.0
        noise62mult.width, noise62mult.height = 140.0, 100.0

        # Initialize noiseprofile6 links

        # noise6add.Result -> group_output_5.Image
        noiseprofile6.links.new(noise6add.outputs[2], group_output_5.inputs[0])
        # group_input_5.Offset -> noise61.Offset
        noiseprofile6.links.new(group_input_5.outputs[0], noise61.inputs[0])
        # group_input_5.Offset -> noise62.Offset
        noiseprofile6.links.new(group_input_5.outputs[0], noise62.inputs[0])
        # noise61pixelate.Color -> noise6add.A
        noiseprofile6.links.new(noise61pixelate.outputs[0], noise6add.inputs[6])
        # noise61.Color -> noise61pixelate.Color
        noiseprofile6.links.new(noise61.outputs[1], noise61pixelate.inputs[0])
        # noise62.Color -> noise6add.Factor
        noiseprofile6.links.new(noise62.outputs[1], noise6add.inputs[0])
        # group_input_5.Scale -> noise61mult.Vector
        noiseprofile6.links.new(group_input_5.outputs[1], noise61mult.inputs[0])
        # noise61mult.Vector -> noise61.Scale
        noiseprofile6.links.new(noise61mult.outputs[0], noise61.inputs[1])
        # group_input_5.Scale -> noise62mult.Vector
        noiseprofile6.links.new(group_input_5.outputs[1], noise62mult.inputs[0])
        # noise62mult.Vector -> noise62.Scale
        noiseprofile6.links.new(noise62mult.outputs[0], noise62.inputs[1])

        return noiseprofile6

    noiseprofile6 = noiseprofile6_node_group()

    def aptpro_advanced_noise_node_group():
        """Initialize AptPro ADVANCED NOISE node group"""
        aptpro_advanced_noise = bpy.data.node_groups.new(type = 'CompositorNodeTree', name = "AptPro ADVANCED NOISE")

        aptpro_advanced_noise.color_tag = 'NONE'
        aptpro_advanced_noise.description = ""
        aptpro_advanced_noise.default_group_node_width = 140
        aptpro_advanced_noise.use_fake_user = True
        # aptpro_advanced_noise interface

        # Socket Result
        result_socket = aptpro_advanced_noise.interface.new_socket(name="Result", in_out='OUTPUT', socket_type='NodeSocketColor')
        result_socket.default_value = (0.800000011920929, 0.800000011920929, 0.800000011920929, 1.0)
        result_socket.attribute_domain = 'POINT'
        result_socket.default_input = 'VALUE'
        result_socket.structure_type = 'AUTO'

        # Socket Image
        image_socket_11 = aptpro_advanced_noise.interface.new_socket(name="Image", in_out='INPUT', socket_type='NodeSocketColor')
        image_socket_11.default_value = (1.0, 1.0, 1.0, 1.0)
        image_socket_11.attribute_domain = 'POINT'
        image_socket_11.default_input = 'VALUE'
        image_socket_11.structure_type = 'AUTO'

        # Socket General Noise
        general_noise_socket = aptpro_advanced_noise.interface.new_socket(name="General Noise", in_out='INPUT', socket_type='NodeSocketFloat')
        general_noise_socket.default_value = 1.0
        general_noise_socket.min_value = 0.0
        general_noise_socket.max_value = 1.0
        general_noise_socket.subtype = 'FACTOR'
        general_noise_socket.attribute_domain = 'POINT'
        general_noise_socket.description = "Amount of mixing between the A and B inputs"
        general_noise_socket.default_input = 'VALUE'
        general_noise_socket.structure_type = 'AUTO'

        # Socket Factor
        factor_socket = aptpro_advanced_noise.interface.new_socket(name="Factor", in_out='INPUT', socket_type='NodeSocketFloat')
        factor_socket.default_value = 1.0
        factor_socket.min_value = 0.0
        factor_socket.max_value = 1.0
        factor_socket.subtype = 'FACTOR'
        factor_socket.attribute_domain = 'POINT'
        factor_socket.description = "Amount of mixing between the A and B inputs"
        factor_socket.default_input = 'VALUE'
        factor_socket.structure_type = 'AUTO'

        # Socket Color Noise scale
        color_noise_scale_socket = aptpro_advanced_noise.interface.new_socket(name="Color Noise scale", in_out='INPUT', socket_type='NodeSocketVector')
        color_noise_scale_socket.default_value = (100.0, 100.0, 100.0)
        color_noise_scale_socket.min_value = -10.0
        color_noise_scale_socket.max_value = 10.0
        color_noise_scale_socket.subtype = 'XYZ'
        color_noise_scale_socket.attribute_domain = 'POINT'
        color_noise_scale_socket.default_input = 'VALUE'
        color_noise_scale_socket.structure_type = 'AUTO'

        # Socket Scale
        scale_socket_6 = aptpro_advanced_noise.interface.new_socket(name="Scale", in_out='INPUT', socket_type='NodeSocketFloat')
        scale_socket_6.default_value = 1.0
        scale_socket_6.min_value = -10000.0
        scale_socket_6.max_value = 10000.0
        scale_socket_6.subtype = 'NONE'
        scale_socket_6.attribute_domain = 'POINT'
        scale_socket_6.default_input = 'VALUE'
        scale_socket_6.structure_type = 'AUTO'

        # Socket Scale
        scale_socket_7 = aptpro_advanced_noise.interface.new_socket(name="Scale", in_out='INPUT', socket_type='NodeSocketFloat')
        scale_socket_7.default_value = 1.0
        scale_socket_7.min_value = -10000.0
        scale_socket_7.max_value = 10000.0
        scale_socket_7.subtype = 'NONE'
        scale_socket_7.attribute_domain = 'POINT'
        scale_socket_7.default_input = 'VALUE'
        scale_socket_7.structure_type = 'AUTO'

        # Socket Noise Profile
        noise_profile_socket = aptpro_advanced_noise.interface.new_socket(name="Noise Profile", in_out='INPUT', socket_type='NodeSocketInt')
        noise_profile_socket.default_value = 1
        noise_profile_socket.min_value = 1
        noise_profile_socket.max_value = 6
        noise_profile_socket.subtype = 'NONE'
        noise_profile_socket.attribute_domain = 'POINT'
        noise_profile_socket.default_input = 'VALUE'
        noise_profile_socket.structure_type = 'AUTO'

        # Socket Shadow Mask
        shadow_mask_socket_1 = aptpro_advanced_noise.interface.new_socket(name="Shadow Mask", in_out='INPUT', socket_type='NodeSocketColor')
        shadow_mask_socket_1.default_value = (0.0, 0.0, 0.0, 1.0)
        shadow_mask_socket_1.attribute_domain = 'POINT'
        shadow_mask_socket_1.default_input = 'VALUE'
        shadow_mask_socket_1.structure_type = 'AUTO'

        # Socket Noise scale
        noise_scale_socket = aptpro_advanced_noise.interface.new_socket(name="Noise scale", in_out='INPUT', socket_type='NodeSocketFloat')
        noise_scale_socket.default_value = 1.0
        noise_scale_socket.min_value = 0.0
        noise_scale_socket.max_value = 1.0
        noise_scale_socket.subtype = 'NONE'
        noise_scale_socket.attribute_domain = 'POINT'
        noise_scale_socket.default_input = 'VALUE'
        noise_scale_socket.structure_type = 'AUTO'

        # Initialize aptpro_advanced_noise nodes

        # Node AdvNoiseOut
        advnoiseout = aptpro_advanced_noise.nodes.new("NodeGroupOutput")
        advnoiseout.label = "AdvNoiseOut"
        advnoiseout.name = "AdvNoiseOut"
        advnoiseout.is_active_output = True

        # Node AdvNoiseIn
        advnoisein = aptpro_advanced_noise.nodes.new("NodeGroupInput")
        advnoisein.label = "AdvNoiseIn"
        advnoisein.name = "AdvNoiseIn"

        # Node NPDen
        npden = aptpro_advanced_noise.nodes.new("CompositorNodeDenoise")
        npden.label = "NPDen"
        npden.name = "NPDen"
        npden.prefilter = 'ACCURATE'
        npden.quality = 'FOLLOW_SCENE'
        # Normal
        npden.inputs[1].default_value = (0.0, 0.0, 0.0)
        # Albedo
        npden.inputs[2].default_value = (1.0, 1.0, 1.0, 1.0)
        # HDR
        npden.inputs[3].default_value = True

        # Node NOISEPROFILE 1
        noiseprofile_1 = aptpro_advanced_noise.nodes.new("CompositorNodeGroup")
        noiseprofile_1.label = "NOISEPROFILE 1"
        noiseprofile_1.name = "NOISEPROFILE 1"
        noiseprofile_1.node_tree = noiseprofile1

        # Node NOISEPROFILE 2
        noiseprofile_2 = aptpro_advanced_noise.nodes.new("CompositorNodeGroup")
        noiseprofile_2.label = "NOISEPROFILE 2"
        noiseprofile_2.name = "NOISEPROFILE 2"
        noiseprofile_2.node_tree = noiseprofile2

        # Node NPBlur
        npblur = aptpro_advanced_noise.nodes.new("CompositorNodeBlur")
        npblur.label = "NPBlur"
        npblur.name = "NPBlur"
        npblur.filter_type = 'GAUSS'
        # Extend Bounds
        npblur.inputs[2].default_value = False
        # Separable
        npblur.inputs[3].default_value = True

        # Node NOISEPROFILE 3
        noiseprofile_3 = aptpro_advanced_noise.nodes.new("CompositorNodeGroup")
        noiseprofile_3.label = "NOISEPROFILE 3"
        noiseprofile_3.name = "NOISEPROFILE 3"
        noiseprofile_3.node_tree = noiseprofile3

        # Node NOISEPROFILE 4
        noiseprofile_4 = aptpro_advanced_noise.nodes.new("CompositorNodeGroup")
        noiseprofile_4.label = "NOISEPROFILE 4"
        noiseprofile_4.name = "NOISEPROFILE 4"
        noiseprofile_4.node_tree = noiseprofile4

        # Node NPGammaMult
        npgammamult = aptpro_advanced_noise.nodes.new("ShaderNodeMix")
        npgammamult.label = "NPGammaMult"
        npgammamult.name = "NPGammaMult"
        npgammamult.blend_type = 'MULTIPLY'
        npgammamult.clamp_factor = True
        npgammamult.clamp_result = True
        npgammamult.data_type = 'RGBA'
        npgammamult.factor_mode = 'UNIFORM'

        # Node NOISEPROFILE 5
        noiseprofile_5 = aptpro_advanced_noise.nodes.new("CompositorNodeGroup")
        noiseprofile_5.label = "NOISEPROFILE 5"
        noiseprofile_5.name = "NOISEPROFILE 5"
        noiseprofile_5.node_tree = noiseprofile5

        # Node NOISEPROFILE 6
        noiseprofile_6 = aptpro_advanced_noise.nodes.new("CompositorNodeGroup")
        noiseprofile_6.label = "NOISEPROFILE 6"
        noiseprofile_6.name = "NOISEPROFILE 6"
        noiseprofile_6.node_tree = noiseprofile6

        # Node #frame
        _frame = aptpro_advanced_noise.nodes.new("ShaderNodeValue")
        _frame.label = "#frame"
        _frame.name = "#frame"
        
        fcurve = _frame.outputs[0].driver_add("default_value")
        fcurve.driver.type = 'SCRIPTED'  # Use scripted expression
        fcurve.driver.expression = "frame"  # Outputs current frame number
        fcurve.driver.use_self = False  # Not needed for simple frame expression
        
        # Node SMNPSoftlight
        smnpsoftlight = aptpro_advanced_noise.nodes.new("ShaderNodeMix")
        smnpsoftlight.label = "SMNPSoftlight"
        smnpsoftlight.name = "SMNPSoftlight"
        smnpsoftlight.blend_type = 'SOFT_LIGHT'
        smnpsoftlight.clamp_factor = False
        smnpsoftlight.clamp_result = True
        smnpsoftlight.data_type = 'RGBA'
        smnpsoftlight.factor_mode = 'UNIFORM'

        # Node ColornoiseNode
        colornoisenode = aptpro_advanced_noise.nodes.new("CompositorNodeTexture")
        colornoisenode.label = "ColornoiseNode"
        colornoisenode.name = "ColornoiseNode"
        colornoisenode.node_output = 0
        # Offset
        colornoisenode.texture = bpy.data.textures.get("FX_AptColornoise")            
        fcurvecnx = colornoisenode.inputs["Offset"].driver_add('default_value', 0)
        fcurvecnx.driver.type = 'SCRIPTED'
        fcurvecnx.driver.expression = "frame"
        
        fcurvecny = colornoisenode.inputs["Offset"].driver_add('default_value', 1)
        fcurvecny.driver.type = 'SCRIPTED'
        fcurvecny.driver.expression = "frame"
        
        fcurvecnz = colornoisenode.inputs["Offset"].driver_add('default_value', 2)
        fcurvecnz.driver.type = 'SCRIPTED'
        fcurvecnz.driver.expression = "frame"

        # Node CNBlur
        cnblur = aptpro_advanced_noise.nodes.new("CompositorNodeBlur")
        cnblur.label = "CNBlur"
        cnblur.name = "CNBlur"
        cnblur.filter_type = 'GAUSS'
        # Extend Bounds
        cnblur.inputs[2].default_value = False
        # Separable
        cnblur.inputs[3].default_value = True

        # Node NoiseProfileGammaSet
        noiseprofilegammaset = aptpro_advanced_noise.nodes.new("CompositorNodeGamma")
        noiseprofilegammaset.label = "NoiseProfileGammaSet"
        noiseprofilegammaset.name = "NoiseProfileGammaSet"
        # Gamma
        noiseprofilegammaset.inputs[1].default_value = 0.5

        # Node CNBlurGama
        cnblurgama = aptpro_advanced_noise.nodes.new("CompositorNodeGamma")
        cnblurgama.label = "CNBlurGamma"
        cnblurgama.name = "CNBlurGama"
        # Gamma
        cnblurgama.inputs[1].default_value = 0.5

        # Node NPGamma
        npgamma = aptpro_advanced_noise.nodes.new("CompositorNodeGamma")
        npgamma.label = "NPGamma"
        npgamma.name = "NPGamma"
        # Gamma
        npgamma.inputs[1].default_value = 0.5

        # Node NPBlurScale
        npblurscale = aptpro_advanced_noise.nodes.new("ShaderNodeVectorMath")
        npblurscale.label = "NPBlurScale"
        npblurscale.name = "NPBlurScale"
        npblurscale.operation = 'SCALE'
        # Vector
        npblurscale.inputs[0].default_value = (5.0, 5.0, 0.0)

        # Node CNBlurScale
        cnblurscale = aptpro_advanced_noise.nodes.new("ShaderNodeVectorMath")
        cnblurscale.label = "CNBlurScale"
        cnblurscale.name = "CNBlurScale"
        cnblurscale.operation = 'SCALE'
        # Vector
        cnblurscale.inputs[0].default_value = (25.0, 25.0, 0.0)

        # Node ProfileMix1
        profilemix1 = aptpro_advanced_noise.nodes.new("ShaderNodeMix")
        profilemix1.label = "ProfileMix1"
        profilemix1.name = "ProfileMix1"
        profilemix1.blend_type = 'MIX'
        profilemix1.clamp_factor = True
        profilemix1.clamp_result = False
        profilemix1.data_type = 'RGBA'
        profilemix1.factor_mode = 'UNIFORM'

        # Node ProfileMix2
        profilemix2 = aptpro_advanced_noise.nodes.new("ShaderNodeMix")
        profilemix2.label = "ProfileMix2"
        profilemix2.name = "ProfileMix2"
        profilemix2.blend_type = 'MIX'
        profilemix2.clamp_factor = True
        profilemix2.clamp_result = False
        profilemix2.data_type = 'RGBA'
        profilemix2.factor_mode = 'UNIFORM'

        # Node ProfileMix3
        profilemix3 = aptpro_advanced_noise.nodes.new("ShaderNodeMix")
        profilemix3.label = "ProfileMix3"
        profilemix3.name = "ProfileMix3"
        profilemix3.blend_type = 'MIX'
        profilemix3.clamp_factor = True
        profilemix3.clamp_result = False
        profilemix3.data_type = 'RGBA'
        profilemix3.factor_mode = 'UNIFORM'

        # Node ProfileMix4
        profilemix4 = aptpro_advanced_noise.nodes.new("ShaderNodeMix")
        profilemix4.label = "ProfileMix4"
        profilemix4.name = "ProfileMix4"
        profilemix4.blend_type = 'MIX'
        profilemix4.clamp_factor = True
        profilemix4.clamp_result = False
        profilemix4.data_type = 'RGBA'
        profilemix4.factor_mode = 'UNIFORM'

        # Node ProfileMix5
        profilemix5 = aptpro_advanced_noise.nodes.new("ShaderNodeMix")
        profilemix5.label = "ProfileMix5"
        profilemix5.name = "ProfileMix5"
        profilemix5.blend_type = 'MIX'
        profilemix5.clamp_factor = True
        profilemix5.clamp_result = False
        profilemix5.data_type = 'RGBA'
        profilemix5.factor_mode = 'UNIFORM'

        # Node ProfileSub1
        profilesub1 = aptpro_advanced_noise.nodes.new("ShaderNodeMath")
        profilesub1.label = "ProfileSub1"
        profilesub1.name = "ProfileSub1"
        profilesub1.hide = True
        profilesub1.operation = 'SUBTRACT'
        profilesub1.use_clamp = False
        # Value_001
        profilesub1.inputs[1].default_value = 1.0

        # Node ProfileSub2
        profilesub2 = aptpro_advanced_noise.nodes.new("ShaderNodeMath")
        profilesub2.label = "ProfileSub2"
        profilesub2.name = "ProfileSub2"
        profilesub2.hide = True
        profilesub2.operation = 'SUBTRACT'
        profilesub2.use_clamp = False
        # Value_001
        profilesub2.inputs[1].default_value = 2.0

        # Node ProfileSub3
        profilesub3 = aptpro_advanced_noise.nodes.new("ShaderNodeMath")
        profilesub3.label = "ProfileSub3"
        profilesub3.name = "ProfileSub3"
        profilesub3.hide = True
        profilesub3.operation = 'SUBTRACT'
        profilesub3.use_clamp = False
        # Value_001
        profilesub3.inputs[1].default_value = 3.0

        # Node ProfileSub4
        profilesub4 = aptpro_advanced_noise.nodes.new("ShaderNodeMath")
        profilesub4.label = "ProfileSub4"
        profilesub4.name = "ProfileSub4"
        profilesub4.hide = True
        profilesub4.operation = 'SUBTRACT'
        profilesub4.use_clamp = False
        # Value_001
        profilesub4.inputs[1].default_value = 4.0

        # Node ProfileSub5
        profilesub5 = aptpro_advanced_noise.nodes.new("ShaderNodeMath")
        profilesub5.label = "ProfileSub5"
        profilesub5.name = "ProfileSub5"
        profilesub5.hide = True
        profilesub5.operation = 'SUBTRACT'
        profilesub5.use_clamp = False
        # Value_001
        profilesub5.inputs[1].default_value = 5.0

        # Node SMMix
        smmix = aptpro_advanced_noise.nodes.new("ShaderNodeMix")
        smmix.label = "SMMix"
        smmix.name = "SMMix"
        smmix.blend_type = 'MIX'
        smmix.clamp_factor = True
        smmix.clamp_result = False
        smmix.data_type = 'RGBA'
        smmix.factor_mode = 'UNIFORM'

        # Node Reroute
        reroute = aptpro_advanced_noise.nodes.new("NodeReroute")
        reroute.name = "Reroute"
        reroute.socket_idname = "NodeSocketColor"
        # Node NPGeneralMix
        npgeneralmix = aptpro_advanced_noise.nodes.new("ShaderNodeMix")
        npgeneralmix.label = "NPGeneralMix"
        npgeneralmix.name = "NPGeneralMix"
        npgeneralmix.blend_type = 'MIX'
        npgeneralmix.clamp_factor = True
        npgeneralmix.clamp_result = False
        npgeneralmix.data_type = 'RGBA'
        npgeneralmix.factor_mode = 'UNIFORM'

        # Set locations
        advnoiseout.location = (1905.7274169921875, 19.116300582885742)
        advnoisein.location = (-1769.7867431640625, -363.957763671875)
        npden.location = (445.306640625, -525.8928833007812)
        noiseprofile_1.location = (-1059.549072265625, 681.79541015625)
        noiseprofile_2.location = (-1061.5108642578125, 559.555908203125)
        npblur.location = (325.7559814453125, -191.30270385742188)
        noiseprofile_3.location = (-1061.68115234375, 436.9693603515625)
        noiseprofile_4.location = (-1063.170166015625, 313.9339599609375)
        npgammamult.location = (747.88037109375, -381.08294677734375)
        noiseprofile_5.location = (-1065.6824951171875, 192.16989135742188)
        noiseprofile_6.location = (-1065.204345703125, 69.95596313476562)
        _frame.location = (-1531.3232421875, 190.55963134765625)
        smnpsoftlight.location = (1352.3597412109375, -219.72445678710938)
        colornoisenode.location = (271.5169677734375, 156.86520385742188)
        cnblur.location = (899.869873046875, 26.122177124023438)
        noiseprofilegammaset.location = (146.35472106933594, -129.52455139160156)
        cnblurgama.location = (1066.23095703125, -40.52686309814453)
        npgamma.location = (485.7560119628906, -270.94317626953125)
        npblurscale.location = (144.89328002929688, -261.01043701171875)
        cnblurscale.location = (680.859130859375, -126.416259765625)
        profilemix1.location = (-700.060302734375, 579.736083984375)
        profilemix2.location = (-533.0256958007812, 495.5168151855469)
        profilemix3.location = (-364.37353515625, 428.2113342285156)
        profilemix4.location = (-203.28099060058594, 341.9945373535156)
        profilemix5.location = (-22.89983367919922, 182.67904663085938)
        profilesub1.location = (-1069.8125, -57.04913330078125)
        profilesub2.location = (-1071.301025390625, -95.76397705078125)
        profilesub3.location = (-1069.812744140625, -135.9678192138672)
        profilesub4.location = (-1069.8125, -176.17169189453125)
        profilesub5.location = (-1071.30126953125, -220.84266662597656)
        smmix.location = (1068.05126953125, -458.9000244140625)
        reroute.location = (440.9735107421875, -994.6163330078125)
        npgeneralmix.location = (1562.7867431640625, -1.2565689086914062)

        # Set dimensions
        advnoiseout.width, advnoiseout.height = 140.0, 100.0
        advnoisein.width, advnoisein.height = 140.0, 100.0
        npden.width, npden.height = 140.0, 100.0
        noiseprofile_1.width, noiseprofile_1.height = 139.053955078125, 100.0
        noiseprofile_2.width, noiseprofile_2.height = 140.9459228515625, 100.0
        npblur.width, npblur.height = 140.0, 100.0
        noiseprofile_3.width, noiseprofile_3.height = 140.0, 100.0
        noiseprofile_4.width, noiseprofile_4.height = 140.0, 100.0
        npgammamult.width, npgammamult.height = 140.0, 100.0
        noiseprofile_5.width, noiseprofile_5.height = 140.0, 100.0
        noiseprofile_6.width, noiseprofile_6.height = 140.0, 100.0
        _frame.width, _frame.height = 140.0, 100.0
        smnpsoftlight.width, smnpsoftlight.height = 140.0, 100.0
        colornoisenode.width, colornoisenode.height = 272.5135498046875, 100.0
        cnblur.width, cnblur.height = 140.0, 100.0
        noiseprofilegammaset.width, noiseprofilegammaset.height = 140.0, 100.0
        cnblurgama.width, cnblurgama.height = 140.0, 100.0
        npgamma.width, npgamma.height = 140.0, 100.0
        npblurscale.width, npblurscale.height = 140.0, 100.0
        cnblurscale.width, cnblurscale.height = 140.0, 100.0
        profilemix1.width, profilemix1.height = 140.0, 100.0
        profilemix2.width, profilemix2.height = 140.0, 100.0
        profilemix3.width, profilemix3.height = 140.0, 100.0
        profilemix4.width, profilemix4.height = 140.0, 100.0
        profilemix5.width, profilemix5.height = 140.0, 100.0
        profilesub1.width, profilesub1.height = 140.0, 100.0
        profilesub2.width, profilesub2.height = 140.0, 100.0
        profilesub3.width, profilesub3.height = 140.0, 100.0
        profilesub4.width, profilesub4.height = 140.0, 100.0
        profilesub5.width, profilesub5.height = 140.0, 100.0
        smmix.width, smmix.height = 140.0, 100.0
        reroute.width, reroute.height = 10.0, 100.0
        npgeneralmix.width, npgeneralmix.height = 140.0, 100.0

        # Initialize aptpro_advanced_noise links

        # npblurscale.Vector -> npblur.Size
        aptpro_advanced_noise.links.new(npblurscale.outputs[0], npblur.inputs[1])
        # profilemix4.Result -> profilemix5.A
        aptpro_advanced_noise.links.new(profilemix4.outputs[2], profilemix5.inputs[6])
        # npden.Image -> npgammamult.A
        aptpro_advanced_noise.links.new(npden.outputs[0], npgammamult.inputs[6])
        # noiseprofile_5.Image -> profilemix4.B
        aptpro_advanced_noise.links.new(noiseprofile_5.outputs[0], profilemix4.inputs[7])
        # _frame.Value -> noiseprofile_4.Offset
        aptpro_advanced_noise.links.new(_frame.outputs[0], noiseprofile_4.inputs[0])
        # noiseprofile_1.Image -> profilemix1.A
        aptpro_advanced_noise.links.new(noiseprofile_1.outputs[0], profilemix1.inputs[6])
        # noiseprofile_4.Image -> profilemix3.B
        aptpro_advanced_noise.links.new(noiseprofile_4.outputs[0], profilemix3.inputs[7])
        # _frame.Value -> noiseprofile_2.Offset
        aptpro_advanced_noise.links.new(_frame.outputs[0], noiseprofile_2.inputs[0])
        # profilemix5.Result -> noiseprofilegammaset.Image
        aptpro_advanced_noise.links.new(profilemix5.outputs[2], noiseprofilegammaset.inputs[0])
        # _frame.Value -> noiseprofile_3.Offset
        aptpro_advanced_noise.links.new(_frame.outputs[0], noiseprofile_3.inputs[0])
        # cnblurscale.Vector -> cnblur.Size
        aptpro_advanced_noise.links.new(cnblurscale.outputs[0], cnblur.inputs[1])
        # _frame.Value -> noiseprofile_6.Offset
        aptpro_advanced_noise.links.new(_frame.outputs[0], noiseprofile_6.inputs[0])
        # _frame.Value -> noiseprofile_1.Offset
        aptpro_advanced_noise.links.new(_frame.outputs[0], noiseprofile_1.inputs[0])
        # noiseprofilegammaset.Image -> npblur.Image
        aptpro_advanced_noise.links.new(noiseprofilegammaset.outputs[0], npblur.inputs[0])
        # profilemix1.Result -> profilemix2.A
        aptpro_advanced_noise.links.new(profilemix1.outputs[2], profilemix2.inputs[6])
        # profilesub5.Value -> profilemix5.Factor
        aptpro_advanced_noise.links.new(profilesub5.outputs[0], profilemix5.inputs[0])
        # noiseprofile_2.Image -> profilemix1.B
        aptpro_advanced_noise.links.new(noiseprofile_2.outputs[0], profilemix1.inputs[7])
        # npblur.Image -> npgamma.Image
        aptpro_advanced_noise.links.new(npblur.outputs[0], npgamma.inputs[0])
        # profilesub2.Value -> profilemix2.Factor
        aptpro_advanced_noise.links.new(profilesub2.outputs[0], profilemix2.inputs[0])
        # cnblur.Image -> cnblurgama.Image
        aptpro_advanced_noise.links.new(cnblur.outputs[0], cnblurgama.inputs[0])
        # noiseprofile_3.Image -> profilemix2.B
        aptpro_advanced_noise.links.new(noiseprofile_3.outputs[0], profilemix2.inputs[7])
        # profilesub4.Value -> profilemix4.Factor
        aptpro_advanced_noise.links.new(profilesub4.outputs[0], profilemix4.inputs[0])
        # profilemix2.Result -> profilemix3.A
        aptpro_advanced_noise.links.new(profilemix2.outputs[2], profilemix3.inputs[6])
        # profilesub3.Value -> profilemix3.Factor
        aptpro_advanced_noise.links.new(profilesub3.outputs[0], profilemix3.inputs[0])
        # profilesub1.Value -> profilemix1.Factor
        aptpro_advanced_noise.links.new(profilesub1.outputs[0], profilemix1.inputs[0])
        # noiseprofile_6.Image -> profilemix5.B
        aptpro_advanced_noise.links.new(noiseprofile_6.outputs[0], profilemix5.inputs[7])
        # profilemix3.Result -> profilemix4.A
        aptpro_advanced_noise.links.new(profilemix3.outputs[2], profilemix4.inputs[6])
        # _frame.Value -> noiseprofile_5.Offset
        aptpro_advanced_noise.links.new(_frame.outputs[0], noiseprofile_5.inputs[0])
        # advnoisein.Color Noise scale -> colornoisenode.Scale
        aptpro_advanced_noise.links.new(advnoisein.outputs[3], colornoisenode.inputs[1])
        # advnoisein.Image -> npden.Image
        aptpro_advanced_noise.links.new(advnoisein.outputs[0], npden.inputs[0])
        # advnoisein.Scale -> cnblurscale.Scale
        aptpro_advanced_noise.links.new(advnoisein.outputs[5], cnblurscale.inputs[3])
        # advnoisein.Scale -> npblurscale.Scale
        aptpro_advanced_noise.links.new(advnoisein.outputs[4], npblurscale.inputs[3])
        # advnoisein.Noise Profile -> profilesub1.Value
        aptpro_advanced_noise.links.new(advnoisein.outputs[6], profilesub1.inputs[0])
        # advnoisein.Noise Profile -> profilesub2.Value
        aptpro_advanced_noise.links.new(advnoisein.outputs[6], profilesub2.inputs[0])
        # advnoisein.Noise Profile -> profilesub3.Value
        aptpro_advanced_noise.links.new(advnoisein.outputs[6], profilesub3.inputs[0])
        # advnoisein.Noise Profile -> profilesub4.Value
        aptpro_advanced_noise.links.new(advnoisein.outputs[6], profilesub4.inputs[0])
        # advnoisein.Noise Profile -> profilesub5.Value
        aptpro_advanced_noise.links.new(advnoisein.outputs[6], profilesub5.inputs[0])
        # advnoisein.Factor -> smnpsoftlight.Factor
        aptpro_advanced_noise.links.new(advnoisein.outputs[2], smnpsoftlight.inputs[0])
        # npgammamult.Result -> smmix.B
        aptpro_advanced_noise.links.new(npgammamult.outputs[2], smmix.inputs[7])
        # smmix.Result -> smnpsoftlight.A
        aptpro_advanced_noise.links.new(smmix.outputs[2], smnpsoftlight.inputs[6])
        # advnoisein.Image -> smmix.A
        aptpro_advanced_noise.links.new(advnoisein.outputs[0], smmix.inputs[6])
        # npgeneralmix.Result -> advnoiseout.Result
        aptpro_advanced_noise.links.new(npgeneralmix.outputs[2], advnoiseout.inputs[0])
        # smnpsoftlight.Result -> npgeneralmix.B
        aptpro_advanced_noise.links.new(smnpsoftlight.outputs[2], npgeneralmix.inputs[7])
        # advnoisein.General Noise -> npgeneralmix.Factor
        aptpro_advanced_noise.links.new(advnoisein.outputs[1], npgeneralmix.inputs[0])
        # advnoisein.Image -> npgeneralmix.A
        aptpro_advanced_noise.links.new(advnoisein.outputs[0], npgeneralmix.inputs[6])
        # advnoisein.Noise scale -> noiseprofile_1.Scale
        aptpro_advanced_noise.links.new(advnoisein.outputs[8], noiseprofile_1.inputs[1])
        # advnoisein.Noise scale -> noiseprofile_2.Scale
        aptpro_advanced_noise.links.new(advnoisein.outputs[8], noiseprofile_2.inputs[1])
        # advnoisein.Noise scale -> noiseprofile_3.Scale
        aptpro_advanced_noise.links.new(advnoisein.outputs[8], noiseprofile_3.inputs[1])
        # advnoisein.Noise scale -> noiseprofile_4.Scale
        aptpro_advanced_noise.links.new(advnoisein.outputs[8], noiseprofile_4.inputs[1])
        # advnoisein.Noise scale -> noiseprofile_5.Scale
        aptpro_advanced_noise.links.new(advnoisein.outputs[8], noiseprofile_5.inputs[1])
        # advnoisein.Noise scale -> noiseprofile_6.Scale
        aptpro_advanced_noise.links.new(advnoisein.outputs[8], noiseprofile_6.inputs[1])
        # advnoisein.Shadow Mask -> reroute.Input
        aptpro_advanced_noise.links.new(advnoisein.outputs[7], reroute.inputs[0])
        # reroute.Output -> npgammamult.Factor
        aptpro_advanced_noise.links.new(reroute.outputs[0], npgammamult.inputs[0])
        # reroute.Output -> smmix.Factor
        aptpro_advanced_noise.links.new(reroute.outputs[0], smmix.inputs[0])
        # npgamma.Image -> npgammamult.B
        aptpro_advanced_noise.links.new(npgamma.outputs[0], npgammamult.inputs[7])
        # colornoisenode.Color -> cnblur.Image
        aptpro_advanced_noise.links.new(colornoisenode.outputs[1], cnblur.inputs[0])
        # cnblurgama.Image -> smnpsoftlight.B
        aptpro_advanced_noise.links.new(cnblurgama.outputs[0], smnpsoftlight.inputs[7])

        return aptpro_advanced_noise

    aptpro_advanced_noise = aptpro_advanced_noise_node_group()

    def aptpro_noise_patterns_node_group():
        """Initialize AptPro NOISE PATTERNS node group"""
        aptpro_noise_patterns = bpy.data.node_groups.new(type = 'CompositorNodeTree', name = "AptPro NOISE PATTERNS")

        aptpro_noise_patterns.color_tag = 'NONE'
        aptpro_noise_patterns.description = ""
        aptpro_noise_patterns.default_group_node_width = 140
        aptpro_noise_patterns.use_fake_user = True
        # aptpro_noise_patterns interface

        # Socket Image
        image_socket_12 = aptpro_noise_patterns.interface.new_socket(name="Image", in_out='OUTPUT', socket_type='NodeSocketColor')
        image_socket_12.default_value = (0.800000011920929, 0.800000011920929, 0.800000011920929, 1.0)
        image_socket_12.attribute_domain = 'POINT'
        image_socket_12.default_input = 'VALUE'
        image_socket_12.structure_type = 'AUTO'

        # Socket Shadow Mask preview
        shadow_mask_preview_socket = aptpro_noise_patterns.interface.new_socket(name="Shadow Mask preview", in_out='OUTPUT', socket_type='NodeSocketColor')
        shadow_mask_preview_socket.default_value = (0.800000011920929, 0.800000011920929, 0.800000011920929, 1.0)
        shadow_mask_preview_socket.attribute_domain = 'POINT'
        shadow_mask_preview_socket.default_input = 'VALUE'
        shadow_mask_preview_socket.structure_type = 'AUTO'

        # Socket Image
        image_socket_13 = aptpro_noise_patterns.interface.new_socket(name="Image", in_out='INPUT', socket_type='NodeSocketColor')
        image_socket_13.default_value = (1.0, 1.0, 1.0, 1.0)
        image_socket_13.attribute_domain = 'POINT'
        image_socket_13.default_input = 'VALUE'
        image_socket_13.structure_type = 'AUTO'

        # Socket Profile
        profile_socket = aptpro_noise_patterns.interface.new_socket(name="Profile", in_out='INPUT', socket_type='NodeSocketInt')
        profile_socket.default_value = 0
        profile_socket.min_value = 1
        profile_socket.max_value = 6
        profile_socket.subtype = 'NONE'
        profile_socket.attribute_domain = 'POINT'
        profile_socket.default_input = 'VALUE'
        profile_socket.structure_type = 'AUTO'

        # Socket GENERAL NOISE
        general_noise_socket_1 = aptpro_noise_patterns.interface.new_socket(name="GENERAL NOISE", in_out='INPUT', socket_type='NodeSocketFloat')
        general_noise_socket_1.default_value = 0.10000000149011612
        general_noise_socket_1.min_value = 0.0
        general_noise_socket_1.max_value = 0.10000000149011612
        general_noise_socket_1.subtype = 'FACTOR'
        general_noise_socket_1.attribute_domain = 'POINT'
        general_noise_socket_1.default_input = 'VALUE'
        general_noise_socket_1.structure_type = 'AUTO'

        # Socket NOISE BLEND
        noise_blend_socket = aptpro_noise_patterns.interface.new_socket(name="NOISE BLEND", in_out='INPUT', socket_type='NodeSocketFloat')
        noise_blend_socket.default_value = 0.15000000596046448
        noise_blend_socket.min_value = 0.0
        noise_blend_socket.max_value = 1.0
        noise_blend_socket.subtype = 'NONE'
        noise_blend_socket.attribute_domain = 'POINT'
        noise_blend_socket.default_input = 'VALUE'
        noise_blend_socket.structure_type = 'AUTO'

        # Socket COLOR NOISE SCALE
        color_noise_scale_socket_1 = aptpro_noise_patterns.interface.new_socket(name="COLOR NOISE SCALE", in_out='INPUT', socket_type='NodeSocketVector')
        color_noise_scale_socket_1.default_value = (100.0, 100.0, 100.0)
        color_noise_scale_socket_1.min_value = 0.0
        color_noise_scale_socket_1.max_value = 100.0
        color_noise_scale_socket_1.subtype = 'XYZ'
        color_noise_scale_socket_1.attribute_domain = 'POINT'
        color_noise_scale_socket_1.default_input = 'VALUE'
        color_noise_scale_socket_1.structure_type = 'AUTO'

        # Socket COLOR NOISE BLEND
        color_noise_blend_socket = aptpro_noise_patterns.interface.new_socket(name="COLOR NOISE BLEND", in_out='INPUT', socket_type='NodeSocketFloat')
        color_noise_blend_socket.default_value = 0.10000000149011612
        color_noise_blend_socket.min_value = 0.0
        color_noise_blend_socket.max_value = 1.0
        color_noise_blend_socket.subtype = 'NONE'
        color_noise_blend_socket.attribute_domain = 'POINT'
        color_noise_blend_socket.default_input = 'VALUE'
        color_noise_blend_socket.structure_type = 'AUTO'

        # Socket COLOR NOISE INTENSITY
        color_noise_intensity_socket = aptpro_noise_patterns.interface.new_socket(name="COLOR NOISE INTENSITY", in_out='INPUT', socket_type='NodeSocketFloat')
        color_noise_intensity_socket.default_value = 0.5
        color_noise_intensity_socket.min_value = 0.0
        color_noise_intensity_socket.max_value = 1.0
        color_noise_intensity_socket.subtype = 'FACTOR'
        color_noise_intensity_socket.attribute_domain = 'POINT'
        color_noise_intensity_socket.default_input = 'VALUE'
        color_noise_intensity_socket.structure_type = 'AUTO'

        # Socket Shadow Mask
        shadow_mask_socket_2 = aptpro_noise_patterns.interface.new_socket(name="Shadow Mask", in_out='INPUT', socket_type='NodeSocketColor')
        shadow_mask_socket_2.default_value = (0.0, 0.0, 0.0, 1.0)
        shadow_mask_socket_2.attribute_domain = 'POINT'
        shadow_mask_socket_2.default_input = 'VALUE'
        shadow_mask_socket_2.structure_type = 'AUTO'

        # Socket Advanced Noise
        advanced_noise_socket = aptpro_noise_patterns.interface.new_socket(name="Advanced Noise", in_out='INPUT', socket_type='NodeSocketBool')
        advanced_noise_socket.default_value = False
        advanced_noise_socket.attribute_domain = 'POINT'
        advanced_noise_socket.description = "Amount of mixing between the A and B inputs"
        advanced_noise_socket.default_input = 'VALUE'
        advanced_noise_socket.structure_type = 'AUTO'

        # Socket Shadow Mask lift
        shadow_mask_lift_socket = aptpro_noise_patterns.interface.new_socket(name="Shadow Mask lift", in_out='INPUT', socket_type='NodeSocketFloat')
        shadow_mask_lift_socket.default_value = 0.0
        shadow_mask_lift_socket.min_value = -1.0
        shadow_mask_lift_socket.max_value = 1.0
        shadow_mask_lift_socket.subtype = 'FACTOR'
        shadow_mask_lift_socket.attribute_domain = 'POINT'
        shadow_mask_lift_socket.description = "Correction for shadows"
        shadow_mask_lift_socket.default_input = 'VALUE'
        shadow_mask_lift_socket.structure_type = 'AUTO'

        # Socket Shadow Mask gamma
        shadow_mask_gamma_socket = aptpro_noise_patterns.interface.new_socket(name="Shadow Mask gamma", in_out='INPUT', socket_type='NodeSocketFloat')
        shadow_mask_gamma_socket.default_value = 1.0
        shadow_mask_gamma_socket.min_value = 0.0
        shadow_mask_gamma_socket.max_value = 2.0
        shadow_mask_gamma_socket.subtype = 'FACTOR'
        shadow_mask_gamma_socket.attribute_domain = 'POINT'
        shadow_mask_gamma_socket.description = "Correction for midtones"
        shadow_mask_gamma_socket.default_input = 'VALUE'
        shadow_mask_gamma_socket.structure_type = 'AUTO'

        # Socket Shadow Mask gain
        shadow_mask_gain_socket = aptpro_noise_patterns.interface.new_socket(name="Shadow Mask gain", in_out='INPUT', socket_type='NodeSocketFloat')
        shadow_mask_gain_socket.default_value = 1.0
        shadow_mask_gain_socket.min_value = 0.0
        shadow_mask_gain_socket.max_value = 2.0
        shadow_mask_gain_socket.subtype = 'FACTOR'
        shadow_mask_gain_socket.attribute_domain = 'POINT'
        shadow_mask_gain_socket.description = "Correction for highlights"
        shadow_mask_gain_socket.default_input = 'VALUE'
        shadow_mask_gain_socket.structure_type = 'AUTO'

        # Socket Noise scale
        noise_scale_socket_1 = aptpro_noise_patterns.interface.new_socket(name="Noise scale", in_out='INPUT', socket_type='NodeSocketFloat')
        noise_scale_socket_1.default_value = 0.0
        noise_scale_socket_1.min_value = 0.0
        noise_scale_socket_1.max_value = 1.0
        noise_scale_socket_1.subtype = 'NONE'
        noise_scale_socket_1.attribute_domain = 'POINT'
        noise_scale_socket_1.default_input = 'VALUE'
        noise_scale_socket_1.structure_type = 'AUTO'

        # Socket General Noise
        general_noise_socket_2 = aptpro_noise_patterns.interface.new_socket(name="General Noise", in_out='INPUT', socket_type='NodeSocketFloat')
        general_noise_socket_2.default_value = 0.25
        general_noise_socket_2.min_value = 0.0
        general_noise_socket_2.max_value = 0.25
        general_noise_socket_2.subtype = 'FACTOR'
        general_noise_socket_2.attribute_domain = 'POINT'
        general_noise_socket_2.description = "Amount of mixing between the A and B inputs"
        general_noise_socket_2.default_input = 'VALUE'
        general_noise_socket_2.structure_type = 'AUTO'

        # Socket Shadow Noise amount
        shadow_noise_amount_socket = aptpro_noise_patterns.interface.new_socket(name="Shadow Noise amount", in_out='INPUT', socket_type='NodeSocketFloat')
        shadow_noise_amount_socket.default_value = 0.25
        shadow_noise_amount_socket.min_value = 0.0
        shadow_noise_amount_socket.max_value = 0.5
        shadow_noise_amount_socket.subtype = 'FACTOR'
        shadow_noise_amount_socket.attribute_domain = 'POINT'
        shadow_noise_amount_socket.description = "Amount of mixing between the A and B inputs"
        shadow_noise_amount_socket.default_input = 'VALUE'
        shadow_noise_amount_socket.structure_type = 'AUTO'

        # Initialize aptpro_noise_patterns nodes

        # Node NPout
        npout = aptpro_noise_patterns.nodes.new("NodeGroupOutput")
        npout.label = "NPout"
        npout.name = "NPout"
        npout.is_active_output = True

        # Node NPin
        npin = aptpro_noise_patterns.nodes.new("NodeGroupInput")
        npin.label = "NPin"
        npin.name = "NPin"

        # Node AptPro ADVANCED NOISE
        aptpro_advanced_noise_1 = aptpro_noise_patterns.nodes.new("CompositorNodeGroup")
        aptpro_advanced_noise_1.label = "AptPro ADVANCED NOISE"
        aptpro_advanced_noise_1.name = "AptPro ADVANCED NOISE"
        aptpro_advanced_noise_1.node_tree = aptpro_advanced_noise

        # Node NoiseAdvancedMix
        noiseadvancedmix = aptpro_noise_patterns.nodes.new("ShaderNodeMix")
        noiseadvancedmix.label = "NoiseAdvancedMix"
        noiseadvancedmix.name = "NoiseAdvancedMix"
        noiseadvancedmix.blend_type = 'MIX'
        noiseadvancedmix.clamp_factor = True
        noiseadvancedmix.clamp_result = False
        noiseadvancedmix.data_type = 'RGBA'
        noiseadvancedmix.factor_mode = 'UNIFORM'

        # Node SMCB
        smcb = aptpro_noise_patterns.nodes.new("CompositorNodeColorBalance")
        smcb.label = "SMCB"
        smcb.name = "SMCB"
        smcb.correction_method = 'LIFT_GAMMA_GAIN'
        smcb.input_whitepoint = mathutils.Color((0.9991403222084045, 1.0003736019134521, 0.998818039894104))
        smcb.output_whitepoint = mathutils.Color((0.9991403222084045, 1.0003736019134521, 0.998818039894104))
        # Fac
        smcb.inputs[0].default_value = 1.0
        # Color Lift
        smcb.inputs[3].default_value = (1.0, 1.0, 1.0, 1.0)
        # Color Gamma
        smcb.inputs[5].default_value = (1.0, 1.0, 1.0, 1.0)
        # Color Gain
        smcb.inputs[7].default_value = (1.0, 1.0, 1.0, 1.0)

        # Node SMgeneralnoise
        smgeneralnoise = aptpro_noise_patterns.nodes.new("ShaderNodeTexNoise")
        smgeneralnoise.label = "SMgeneralnoise"
        smgeneralnoise.name = "SMgeneralnoise"
        smgeneralnoise.hide = True
        smgeneralnoise.noise_dimensions = '2D'
        smgeneralnoise.noise_type = 'FBM'
        smgeneralnoise.normalize = True
        # Vector
        smgeneralnoise.inputs[0].default_value = (0.0, 0.0, 0.0)
        # Scale
        smgeneralnoise.inputs[2].default_value = 500.0
        # Detail
        smgeneralnoise.inputs[3].default_value = 15.0
        # Roughness
        smgeneralnoise.inputs[4].default_value = 1.0
        # Lacunarity
        smgeneralnoise.inputs[5].default_value = 100.0
        # Distortion
        smgeneralnoise.inputs[8].default_value = 5.0

        # Node SMnoiseOverlay
        smnoiseoverlay = aptpro_noise_patterns.nodes.new("ShaderNodeMix")
        smnoiseoverlay.label = "SMnoiseOverlay"
        smnoiseoverlay.name = "SMnoiseOverlay"
        smnoiseoverlay.blend_type = 'OVERLAY'
        smnoiseoverlay.clamp_factor = True
        smnoiseoverlay.clamp_result = False
        smnoiseoverlay.data_type = 'RGBA'
        smnoiseoverlay.factor_mode = 'UNIFORM'

        # Node Reroute
        reroute_1 = aptpro_noise_patterns.nodes.new("NodeReroute")
        reroute_1.name = "Reroute"
        reroute_1.socket_idname = "NodeSocketColor"
        # Node Reroute.001
        reroute_001 = aptpro_noise_patterns.nodes.new("NodeReroute")
        reroute_001.name = "Reroute.001"
        reroute_001.socket_idname = "NodeSocketColor"
        # Node SMWhiteNoiseTex
        smwhitenoisetex = aptpro_noise_patterns.nodes.new("ShaderNodeTexWhiteNoise")
        smwhitenoisetex.label = "SMWhiteNoiseTex"
        smwhitenoisetex.name = "SMWhiteNoiseTex"
        smwhitenoisetex.noise_dimensions = '2D'
        # Vector
        smwhitenoisetex.inputs[0].default_value = (0.0, 0.0, 0.0)

        # Node WhitenoiseOverlay
        whitenoiseoverlay = aptpro_noise_patterns.nodes.new("ShaderNodeMix")
        whitenoiseoverlay.label = "WhitenoiseOverlay"
        whitenoiseoverlay.name = "WhitenoiseOverlay"
        whitenoiseoverlay.blend_type = 'OVERLAY'
        whitenoiseoverlay.clamp_factor = True
        whitenoiseoverlay.clamp_result = False
        whitenoiseoverlay.data_type = 'RGBA'
        whitenoiseoverlay.factor_mode = 'UNIFORM'

        # Node SMnoiseMix
        smnoisemix = aptpro_noise_patterns.nodes.new("ShaderNodeMix")
        smnoisemix.label = "SMnoiseMix"
        smnoisemix.name = "SMnoiseMix"
        smnoisemix.blend_type = 'MIX'
        smnoisemix.clamp_factor = True
        smnoisemix.clamp_result = False
        smnoisemix.data_type = 'RGBA'
        smnoisemix.factor_mode = 'UNIFORM'

        # Node WhitenoiseDen
        whitenoiseden = aptpro_noise_patterns.nodes.new("CompositorNodeDenoise")
        whitenoiseden.label = "WhitenoiseDen"
        whitenoiseden.name = "WhitenoiseDen"
        whitenoiseden.prefilter = 'NONE'
        whitenoiseden.quality = 'FAST'
        # Normal
        whitenoiseden.inputs[1].default_value = (0.0, 0.0, 0.0)
        # Albedo
        whitenoiseden.inputs[2].default_value = (1.0, 1.0, 1.0, 1.0)
        # HDR
        whitenoiseden.inputs[3].default_value = True

        # Node SMNoiseTex
        smnoisetex = aptpro_noise_patterns.nodes.new("ShaderNodeTexNoise")
        smnoisetex.label = "SMNoiseTex"
        smnoisetex.name = "SMNoiseTex"
        smnoisetex.noise_dimensions = '3D'
        smnoisetex.noise_type = 'FBM'
        smnoisetex.normalize = True
        # Vector
        smnoisetex.inputs[0].default_value = (0.0, 0.0, 0.0)
        # Scale
        smnoisetex.inputs[2].default_value = 500.0
        # Detail
        smnoisetex.inputs[3].default_value = 15.0
        # Roughness
        smnoisetex.inputs[4].default_value = 1.0
        # Lacunarity
        smnoisetex.inputs[5].default_value = 100.0
        # Distortion
        smnoisetex.inputs[8].default_value = 1.0

        # Node SMNoiseOverlay
        smnoiseoverlay_1 = aptpro_noise_patterns.nodes.new("ShaderNodeMix")
        smnoiseoverlay_1.label = "SMNoiseOverlay"
        smnoiseoverlay_1.name = "SMNoiseOverlay"
        smnoiseoverlay_1.blend_type = 'OVERLAY'
        smnoiseoverlay_1.clamp_factor = True
        smnoiseoverlay_1.clamp_result = False
        smnoiseoverlay_1.data_type = 'RGBA'
        smnoiseoverlay_1.factor_mode = 'UNIFORM'

        # Node SMnoiseMix2
        smnoisemix2 = aptpro_noise_patterns.nodes.new("ShaderNodeMix")
        smnoisemix2.label = "SMnoiseMix2"
        smnoisemix2.name = "SMnoiseMix2"
        smnoisemix2.blend_type = 'MIX'
        smnoisemix2.clamp_factor = True
        smnoisemix2.clamp_result = False
        smnoisemix2.data_type = 'RGBA'
        smnoisemix2.factor_mode = 'UNIFORM'

        # Set locations
        npout.location = (220.2206573486328, -420.8663024902344)
        npin.location = (-2092.0810546875, -181.6009979248047)
        aptpro_advanced_noise_1.location = (-309.4876708984375, -657.0430908203125)
        noiseadvancedmix.location = (-123.68879699707031, -412.3822326660156)
        smcb.location = (-1828.2686767578125, -542.8429565429688)
        smgeneralnoise.location = (-681.5836181640625, -663.1905517578125)
        smnoiseoverlay.location = (-499.544677734375, -421.56878662109375)
        reroute_1.location = (-21.786170959472656, -1143.7618408203125)
        reroute_001.location = (-569.051025390625, -1147.7056884765625)
        smwhitenoisetex.location = (-1663.8125, 77.17880249023438)
        whitenoiseoverlay.location = (-1459.75146484375, 116.00523376464844)
        smnoisemix.location = (-897.31787109375, -110.62161254882812)
        whitenoiseden.location = (-1260.625244140625, 99.75944519042969)
        smnoisetex.location = (-1848.149169921875, 217.01629638671875)
        smnoiseoverlay_1.location = (-1080.2860107421875, 17.759368896484375)
        smnoisemix2.location = (-699.40673828125, -248.6365966796875)

        # Set dimensions
        npout.width, npout.height = 140.0, 100.0
        npin.width, npin.height = 140.0, 100.0
        aptpro_advanced_noise_1.width, aptpro_advanced_noise_1.height = 140.0, 100.0
        noiseadvancedmix.width, noiseadvancedmix.height = 140.0, 100.0
        smcb.width, smcb.height = 140.0, 100.0
        smgeneralnoise.width, smgeneralnoise.height = 140.0, 100.0
        smnoiseoverlay.width, smnoiseoverlay.height = 140.0, 100.0
        reroute_1.width, reroute_1.height = 10.0, 100.0
        reroute_001.width, reroute_001.height = 10.0, 100.0
        smwhitenoisetex.width, smwhitenoisetex.height = 140.0, 100.0
        whitenoiseoverlay.width, whitenoiseoverlay.height = 140.0, 100.0
        smnoisemix.width, smnoisemix.height = 140.0, 100.0
        whitenoiseden.width, whitenoiseden.height = 140.0, 100.0
        smnoisetex.width, smnoisetex.height = 140.0, 100.0
        smnoiseoverlay_1.width, smnoiseoverlay_1.height = 140.0, 100.0
        smnoisemix2.width, smnoisemix2.height = 140.0, 100.0

        # Initialize aptpro_noise_patterns links

        # noiseadvancedmix.Result -> npout.Image
        aptpro_noise_patterns.links.new(noiseadvancedmix.outputs[2], npout.inputs[0])
        # npin.COLOR NOISE SCALE -> aptpro_advanced_noise_1.Color Noise scale
        aptpro_noise_patterns.links.new(npin.outputs[4], aptpro_advanced_noise_1.inputs[3])
        # npin.GENERAL NOISE -> aptpro_advanced_noise_1.General Noise
        aptpro_noise_patterns.links.new(npin.outputs[2], aptpro_advanced_noise_1.inputs[1])
        # npin.COLOR NOISE BLEND -> aptpro_advanced_noise_1.Scale
        aptpro_noise_patterns.links.new(npin.outputs[5], aptpro_advanced_noise_1.inputs[5])
        # npin.NOISE BLEND -> aptpro_advanced_noise_1.Scale
        aptpro_noise_patterns.links.new(npin.outputs[3], aptpro_advanced_noise_1.inputs[4])
        # npin.Profile -> aptpro_advanced_noise_1.Noise Profile
        aptpro_noise_patterns.links.new(npin.outputs[1], aptpro_advanced_noise_1.inputs[6])
        # npin.COLOR NOISE INTENSITY -> aptpro_advanced_noise_1.Factor
        aptpro_noise_patterns.links.new(npin.outputs[6], aptpro_advanced_noise_1.inputs[2])
        # aptpro_advanced_noise_1.Result -> noiseadvancedmix.B
        aptpro_noise_patterns.links.new(aptpro_advanced_noise_1.outputs[0], noiseadvancedmix.inputs[7])
        # npin.Advanced Noise -> noiseadvancedmix.Factor
        aptpro_noise_patterns.links.new(npin.outputs[8], noiseadvancedmix.inputs[0])
        # npin.Noise scale -> aptpro_advanced_noise_1.Noise scale
        aptpro_noise_patterns.links.new(npin.outputs[12], aptpro_advanced_noise_1.inputs[8])
        # npin.Shadow Mask lift -> smcb.Lift
        aptpro_noise_patterns.links.new(npin.outputs[9], smcb.inputs[2])
        # npin.Shadow Mask gamma -> smcb.Gamma
        aptpro_noise_patterns.links.new(npin.outputs[10], smcb.inputs[4])
        # npin.Shadow Mask gain -> smcb.Gain
        aptpro_noise_patterns.links.new(npin.outputs[11], smcb.inputs[6])
        # npin.Shadow Mask -> smcb.Image
        aptpro_noise_patterns.links.new(npin.outputs[7], smcb.inputs[1])
        # smcb.Image -> aptpro_advanced_noise_1.Shadow Mask
        aptpro_noise_patterns.links.new(smcb.outputs[0], aptpro_advanced_noise_1.inputs[7])
        # smgeneralnoise.Fac -> smnoiseoverlay.B
        aptpro_noise_patterns.links.new(smgeneralnoise.outputs[0], smnoiseoverlay.inputs[7])
        # smnoiseoverlay.Result -> aptpro_advanced_noise_1.Image
        aptpro_noise_patterns.links.new(smnoiseoverlay.outputs[2], aptpro_advanced_noise_1.inputs[0])
        # smnoiseoverlay.Result -> noiseadvancedmix.A
        aptpro_noise_patterns.links.new(smnoiseoverlay.outputs[2], noiseadvancedmix.inputs[6])
        # reroute_1.Output -> npout.Shadow Mask preview
        aptpro_noise_patterns.links.new(reroute_1.outputs[0], npout.inputs[1])
        # smcb.Image -> reroute_001.Input
        aptpro_noise_patterns.links.new(smcb.outputs[0], reroute_001.inputs[0])
        # npin.General Noise -> smnoiseoverlay.Factor
        aptpro_noise_patterns.links.new(npin.outputs[13], smnoiseoverlay.inputs[0])
        # npin.Image -> whitenoiseoverlay.A
        aptpro_noise_patterns.links.new(npin.outputs[0], whitenoiseoverlay.inputs[6])
        # smcb.Image -> smnoisemix.Factor
        aptpro_noise_patterns.links.new(smcb.outputs[0], smnoisemix.inputs[0])
        # npin.Image -> smnoisemix.A
        aptpro_noise_patterns.links.new(npin.outputs[0], smnoisemix.inputs[6])
        # smnoisemix2.Result -> smnoiseoverlay.A
        aptpro_noise_patterns.links.new(smnoisemix2.outputs[2], smnoiseoverlay.inputs[6])
        # reroute_001.Output -> reroute_1.Input
        aptpro_noise_patterns.links.new(reroute_001.outputs[0], reroute_1.inputs[0])
        # npin.Shadow Noise amount -> whitenoiseoverlay.Factor
        aptpro_noise_patterns.links.new(npin.outputs[14], whitenoiseoverlay.inputs[0])
        # whitenoiseoverlay.Result -> whitenoiseden.Image
        aptpro_noise_patterns.links.new(whitenoiseoverlay.outputs[2], whitenoiseden.inputs[0])
        # smwhitenoisetex.Value -> whitenoiseoverlay.B
        aptpro_noise_patterns.links.new(smwhitenoisetex.outputs[0], whitenoiseoverlay.inputs[7])
        # whitenoiseden.Image -> smnoiseoverlay_1.A
        aptpro_noise_patterns.links.new(whitenoiseden.outputs[0], smnoiseoverlay_1.inputs[6])
        # smnoisetex.Fac -> smnoiseoverlay_1.B
        aptpro_noise_patterns.links.new(smnoisetex.outputs[0], smnoiseoverlay_1.inputs[7])
        # npin.Shadow Noise amount -> smnoiseoverlay_1.Factor
        aptpro_noise_patterns.links.new(npin.outputs[14], smnoiseoverlay_1.inputs[0])
        # smnoisemix.Result -> smnoisemix2.B
        aptpro_noise_patterns.links.new(smnoisemix.outputs[2], smnoisemix2.inputs[7])
        # npin.Image -> smnoisemix2.A
        aptpro_noise_patterns.links.new(npin.outputs[0], smnoisemix2.inputs[6])
        # smnoiseoverlay_1.Result -> smnoisemix.B
        aptpro_noise_patterns.links.new(smnoiseoverlay_1.outputs[2], smnoisemix.inputs[7])
        # smcb.Image -> smnoisemix2.Factor
        aptpro_noise_patterns.links.new(smcb.outputs[0], smnoisemix2.inputs[0])

        return aptpro_noise_patterns

    aptpro_noise_patterns = aptpro_noise_patterns_node_group()

    def aptpro_dirt_node_group():
        """Initialize AptPro DIRT node group"""
        aptpro_dirt = bpy.data.node_groups.new(type = 'CompositorNodeTree', name = "AptPro DIRT")

        aptpro_dirt.color_tag = 'NONE'
        aptpro_dirt.description = ""
        aptpro_dirt.default_group_node_width = 140
        aptpro_dirt.use_fake_user = True
        # aptpro_dirt interface

        # Socket Image
        image_socket_14 = aptpro_dirt.interface.new_socket(name="Image", in_out='OUTPUT', socket_type='NodeSocketColor')
        image_socket_14.default_value = (0.800000011920929, 0.800000011920929, 0.800000011920929, 1.0)
        image_socket_14.attribute_domain = 'POINT'
        image_socket_14.default_input = 'VALUE'
        image_socket_14.structure_type = 'AUTO'

        # Socket Image
        image_socket_15 = aptpro_dirt.interface.new_socket(name="Image", in_out='INPUT', socket_type='NodeSocketColor')
        image_socket_15.default_value = (1.0, 1.0, 1.0, 1.0)
        image_socket_15.attribute_domain = 'POINT'
        image_socket_15.default_input = 'VALUE'
        image_socket_15.structure_type = 'AUTO'

        # Socket FINGERPRINT AMOUNT
        fingerprint_amount_socket = aptpro_dirt.interface.new_socket(name="FINGERPRINT AMOUNT", in_out='INPUT', socket_type='NodeSocketFloat')
        fingerprint_amount_socket.default_value = 0.25
        fingerprint_amount_socket.min_value = 0.0
        fingerprint_amount_socket.max_value = 1.0
        fingerprint_amount_socket.subtype = 'NONE'
        fingerprint_amount_socket.attribute_domain = 'POINT'
        fingerprint_amount_socket.default_input = 'VALUE'
        fingerprint_amount_socket.structure_type = 'AUTO'

        # Socket FINGERPRINT INTENSITY
        fingerprint_intensity_socket = aptpro_dirt.interface.new_socket(name="FINGERPRINT INTENSITY", in_out='INPUT', socket_type='NodeSocketFloat')
        fingerprint_intensity_socket.default_value = 0.25
        fingerprint_intensity_socket.min_value = 0.0
        fingerprint_intensity_socket.max_value = 1.0
        fingerprint_intensity_socket.subtype = 'NONE'
        fingerprint_intensity_socket.attribute_domain = 'POINT'
        fingerprint_intensity_socket.default_input = 'VALUE'
        fingerprint_intensity_socket.structure_type = 'AUTO'

        # Socket SMUDGE AMOUNT
        smudge_amount_socket = aptpro_dirt.interface.new_socket(name="SMUDGE AMOUNT", in_out='INPUT', socket_type='NodeSocketFloat')
        smudge_amount_socket.default_value = 0.25
        smudge_amount_socket.min_value = 0.0
        smudge_amount_socket.max_value = 1.0
        smudge_amount_socket.subtype = 'NONE'
        smudge_amount_socket.attribute_domain = 'POINT'
        smudge_amount_socket.default_input = 'VALUE'
        smudge_amount_socket.structure_type = 'AUTO'

        # Socket SMUDGE INTENSITY
        smudge_intensity_socket = aptpro_dirt.interface.new_socket(name="SMUDGE INTENSITY", in_out='INPUT', socket_type='NodeSocketFloat')
        smudge_intensity_socket.default_value = 0.25
        smudge_intensity_socket.min_value = 0.0
        smudge_intensity_socket.max_value = 1.0
        smudge_intensity_socket.subtype = 'NONE'
        smudge_intensity_socket.attribute_domain = 'POINT'
        smudge_intensity_socket.default_input = 'VALUE'
        smudge_intensity_socket.structure_type = 'AUTO'

        # Socket SEED
        seed_socket = aptpro_dirt.interface.new_socket(name="SEED", in_out='INPUT', socket_type='NodeSocketInt')
        seed_socket.default_value = 0
        seed_socket.min_value = 0
        seed_socket.max_value = 2147483647
        seed_socket.subtype = 'NONE'
        seed_socket.attribute_domain = 'POINT'
        seed_socket.default_input = 'VALUE'
        seed_socket.structure_type = 'AUTO'

        # Initialize aptpro_dirt nodes

        # Node Gout
        gout = aptpro_dirt.nodes.new("NodeGroupOutput")
        gout.label = "Gout"
        gout.name = "Gout"
        gout.is_active_output = True

        # Node Gin
        gin = aptpro_dirt.nodes.new("NodeGroupInput")
        gin.label = "Gin"
        gin.name = "Gin"

        # Node FingerprintsLight
        fingerprintslight = aptpro_dirt.nodes.new("CompositorNodeImage")
        fingerprintslight.label = "FingerprintsLight"
        fingerprintslight.name = "FingerprintsLight"
        fingerprintslight.frame_duration = 1
        fingerprintslight.frame_offset = 0
        fingerprintslight.frame_start = 1
        # Load image AperturiaFX_Fingerprints_Light.png
        base_dir = os.path.dirname(os.path.abspath(__file__))
        image_path = os.path.join(base_dir, "imgs", "AperturiaFX_Fingerprints_Light.png")
        fingerprintslight.image = bpy.data.images.load(image_path, check_existing = True)
        # Set image settings
        fingerprintslight.image.source = 'FILE'
        fingerprintslight.image.colorspace_settings.name = 'sRGB'
        fingerprintslight.image.alpha_mode = 'STRAIGHT'
        fingerprintslight.use_auto_refresh = True
        fingerprintslight.use_cyclic = False

        # Node FingerprintsHeavy
        fingerprintsheavy = aptpro_dirt.nodes.new("CompositorNodeImage")
        fingerprintsheavy.label = "FingerprintsHeavy"
        fingerprintsheavy.name = "FingerprintsHeavy"
        fingerprintsheavy.frame_duration = 1
        fingerprintsheavy.frame_offset = 0
        fingerprintsheavy.frame_start = 1
        # Load image AperturiaFX_Fingerprints_Heavy.png
        base_dir = os.path.dirname(os.path.abspath(__file__))
        image_path = os.path.join(base_dir, "imgs", "AperturiaFX_Fingerprints_Heavy.png")
        fingerprintsheavy.image = bpy.data.images.load(image_path, check_existing = True)
        # Set image settings
        fingerprintsheavy.image.source = 'FILE'
        fingerprintsheavy.image.colorspace_settings.name = 'sRGB'
        fingerprintsheavy.image.alpha_mode = 'STRAIGHT'
        fingerprintsheavy.use_auto_refresh = True
        fingerprintsheavy.use_cyclic = False

        # Node SmudgesLight
        smudgeslight = aptpro_dirt.nodes.new("CompositorNodeImage")
        smudgeslight.label = "SmudgesLight"
        smudgeslight.name = "SmudgesLight"
        smudgeslight.frame_duration = 1
        smudgeslight.frame_offset = 0
        smudgeslight.frame_start = 1
        # Load image AperturiaFX_Smudges_Light.png
        base_dir = os.path.dirname(os.path.abspath(__file__))
        image_path = os.path.join(base_dir, "imgs", "AperturiaFX_Smudges_Light.png")
        smudgeslight.image = bpy.data.images.load(image_path, check_existing = True)
        # Set image settings
        smudgeslight.image.source = 'FILE'
        smudgeslight.image.colorspace_settings.name = 'sRGB'
        smudgeslight.image.alpha_mode = 'STRAIGHT'
        smudgeslight.use_auto_refresh = True
        smudgeslight.use_cyclic = False

        # Node SmudgesHeavy
        smudgesheavy = aptpro_dirt.nodes.new("CompositorNodeImage")
        smudgesheavy.label = "SmudgesHeavy"
        smudgesheavy.name = "SmudgesHeavy"
        smudgesheavy.frame_duration = 1
        smudgesheavy.frame_offset = 0
        smudgesheavy.frame_start = 1
        # Load image AperturiaFX_Smudges_Heavy.png
        base_dir = os.path.dirname(os.path.abspath(__file__))
        image_path = os.path.join(base_dir, "imgs", "AperturiaFX_Smudges_Heavy.png")
        smudgesheavy.image = bpy.data.images.load(image_path, check_existing = True)
        # Set image settings
        smudgesheavy.image.source = 'FILE'
        smudgesheavy.image.colorspace_settings.name = 'sRGB'
        smudgesheavy.image.alpha_mode = 'STRAIGHT'
        smudgesheavy.use_auto_refresh = True
        smudgesheavy.use_cyclic = False

        # Node FLTScale
        fltscale = aptpro_dirt.nodes.new("CompositorNodeScale")
        fltscale.label = "FLTScale"
        fltscale.name = "FLTScale"
        fltscale.frame_method = 'CROP'
        fltscale.interpolation = 'BILINEAR'
        fltscale.space = 'RENDER_SIZE'

        # Node FHTScale
        fhtscale = aptpro_dirt.nodes.new("CompositorNodeScale")
        fhtscale.label = "FHTScale"
        fhtscale.name = "FHTScale"
        fhtscale.frame_method = 'CROP'
        fhtscale.interpolation = 'BILINEAR'
        fhtscale.space = 'RENDER_SIZE'

        # Node SLTScale
        sltscale = aptpro_dirt.nodes.new("CompositorNodeScale")
        sltscale.label = "SLTScale"
        sltscale.name = "SLTScale"
        sltscale.frame_method = 'CROP'
        sltscale.interpolation = 'BILINEAR'
        sltscale.space = 'RENDER_SIZE'

        # Node SHTScale
        shtscale = aptpro_dirt.nodes.new("CompositorNodeScale")
        shtscale.label = "SHTScale"
        shtscale.name = "SHTScale"
        shtscale.frame_method = 'CROP'
        shtscale.interpolation = 'BILINEAR'
        shtscale.space = 'RENDER_SIZE'

        # Node FingerLeveler
        fingerleveler = aptpro_dirt.nodes.new("ShaderNodeMix")
        fingerleveler.label = "FingerLeveler"
        fingerleveler.name = "FingerLeveler"
        fingerleveler.blend_type = 'ADD'
        fingerleveler.clamp_factor = False
        fingerleveler.clamp_result = False
        fingerleveler.data_type = 'RGBA'
        fingerleveler.factor_mode = 'UNIFORM'

        # Node SmudgeLeveler
        smudgeleveler = aptpro_dirt.nodes.new("ShaderNodeMix")
        smudgeleveler.label = "SmudgeLeveler"
        smudgeleveler.name = "SmudgeLeveler"
        smudgeleveler.blend_type = 'ADD'
        smudgeleveler.clamp_factor = False
        smudgeleveler.clamp_result = False
        smudgeleveler.data_type = 'RGBA'
        smudgeleveler.factor_mode = 'UNIFORM'

        # Node FingerIntensity
        fingerintensity = aptpro_dirt.nodes.new("ShaderNodeMix")
        fingerintensity.label = "FingerIntensity"
        fingerintensity.name = "FingerIntensity"
        fingerintensity.blend_type = 'ADD'
        fingerintensity.clamp_factor = False
        fingerintensity.clamp_result = False
        fingerintensity.data_type = 'RGBA'
        fingerintensity.factor_mode = 'UNIFORM'

        # Node SmudgeIntensity
        smudgeintensity = aptpro_dirt.nodes.new("ShaderNodeMix")
        smudgeintensity.label = "SmudgeIntensity"
        smudgeintensity.name = "SmudgeIntensity"
        smudgeintensity.blend_type = 'ADD'
        smudgeintensity.clamp_factor = False
        smudgeintensity.clamp_result = False
        smudgeintensity.data_type = 'RGBA'
        smudgeintensity.factor_mode = 'UNIFORM'

        # Node SHT
        sht = aptpro_dirt.nodes.new("CompositorNodeTransform")
        sht.label = "SHT"
        sht.name = "SHT"
        sht.filter_type = 'NEAREST'
        # X
        sht.inputs[1].default_value = 0.0
        # Y
        sht.inputs[2].default_value = 0.0
        # Scale
        sht.inputs[4].default_value = 1.5

        # Node FHT
        fht = aptpro_dirt.nodes.new("CompositorNodeTransform")
        fht.label = "FHT"
        fht.name = "FHT"
        fht.filter_type = 'NEAREST'
        # X
        fht.inputs[1].default_value = 0.0
        # Y
        fht.inputs[2].default_value = 0.0
        # Scale
        fht.inputs[4].default_value = 1.5

        # Node SeedRotation
        seedrotation = aptpro_dirt.nodes.new("ShaderNodeMath")
        seedrotation.label = "SeedRotation"
        seedrotation.name = "SeedRotation"
        seedrotation.operation = 'SINH'
        seedrotation.use_clamp = False

        # Node FLT
        flt = aptpro_dirt.nodes.new("CompositorNodeTransform")
        flt.label = "FLT"
        flt.name = "FLT"
        flt.filter_type = 'NEAREST'
        # X
        flt.inputs[1].default_value = 0.0
        # Y
        flt.inputs[2].default_value = 0.0
        # Scale
        flt.inputs[4].default_value = 1.5

        # Node SLT
        slt = aptpro_dirt.nodes.new("CompositorNodeTransform")
        slt.label = "SLT"
        slt.name = "SLT"
        slt.filter_type = 'NEAREST'
        # X
        slt.inputs[1].default_value = 0.0
        # Y
        slt.inputs[2].default_value = 0.0
        # Scale
        slt.inputs[4].default_value = 1.5

        # Set locations
        gout.location = (1345.0205078125, -325.9886169433594)
        gin.location = (-1183.832763671875, -298.6406555175781)
        fingerprintslight.location = (-960.362548828125, 291.3128356933594)
        fingerprintsheavy.location = (-1130.304443359375, 92.49411010742188)
        smudgeslight.location = (59.87236022949219, 285.7851867675781)
        smudgesheavy.location = (-36.12577819824219, -66.07778930664062)
        fltscale.location = (-472.26690673828125, 145.2794189453125)
        fhtscale.location = (-474.868896484375, -98.69021606445312)
        sltscale.location = (443.85772705078125, 201.74972534179688)
        shtscale.location = (430.6823425292969, -118.10858154296875)
        fingerleveler.location = (-270.2724914550781, -61.5997314453125)
        smudgeleveler.location = (692.8756713867188, -196.86795043945312)
        fingerintensity.location = (135.0630340576172, -386.8564453125)
        smudgeintensity.location = (1070.4232177734375, -276.7294921875)
        sht.location = (248.63804626464844, -97.88773345947266)
        fht.location = (-664.0372314453125, -60.051212310791016)
        seedrotation.location = (-969.3111572265625, -145.3251190185547)
        flt.location = (-656.8720092773438, 189.60447692871094)
        slt.location = (263.9999694824219, 228.11712646484375)

        # Set dimensions
        gout.width, gout.height = 140.0, 100.0
        gin.width, gin.height = 140.0, 100.0
        fingerprintslight.width, fingerprintslight.height = 140.0, 100.0
        fingerprintsheavy.width, fingerprintsheavy.height = 140.0, 100.0
        smudgeslight.width, smudgeslight.height = 140.0, 100.0
        smudgesheavy.width, smudgesheavy.height = 140.0, 100.0
        fltscale.width, fltscale.height = 140.0, 100.0
        fhtscale.width, fhtscale.height = 140.0, 100.0
        sltscale.width, sltscale.height = 140.0, 100.0
        shtscale.width, shtscale.height = 140.0, 100.0
        fingerleveler.width, fingerleveler.height = 140.0, 100.0
        smudgeleveler.width, smudgeleveler.height = 140.0, 100.0
        fingerintensity.width, fingerintensity.height = 140.0, 100.0
        smudgeintensity.width, smudgeintensity.height = 140.0, 100.0
        sht.width, sht.height = 140.0, 100.0
        fht.width, fht.height = 140.0, 100.0
        seedrotation.width, seedrotation.height = 140.0, 100.0
        flt.width, flt.height = 140.0, 100.0
        slt.width, slt.height = 140.0, 100.0

        # Initialize aptpro_dirt links

        # fltscale.Image -> fingerleveler.B
        aptpro_dirt.links.new(fltscale.outputs[0], fingerleveler.inputs[7])
        # smudgeleveler.Result -> smudgeintensity.B
        aptpro_dirt.links.new(smudgeleveler.outputs[2], smudgeintensity.inputs[7])
        # sltscale.Image -> smudgeleveler.B
        aptpro_dirt.links.new(sltscale.outputs[0], smudgeleveler.inputs[7])
        # fingerintensity.Result -> smudgeintensity.A
        aptpro_dirt.links.new(fingerintensity.outputs[2], smudgeintensity.inputs[6])
        # sht.Image -> shtscale.Image
        aptpro_dirt.links.new(sht.outputs[0], shtscale.inputs[0])
        # fht.Image -> fhtscale.Image
        aptpro_dirt.links.new(fht.outputs[0], fhtscale.inputs[0])
        # slt.Image -> sltscale.Image
        aptpro_dirt.links.new(slt.outputs[0], sltscale.inputs[0])
        # shtscale.Image -> smudgeleveler.A
        aptpro_dirt.links.new(shtscale.outputs[0], smudgeleveler.inputs[6])
        # fhtscale.Image -> fingerleveler.A
        aptpro_dirt.links.new(fhtscale.outputs[0], fingerleveler.inputs[6])
        # fingerleveler.Result -> fingerintensity.B
        aptpro_dirt.links.new(fingerleveler.outputs[2], fingerintensity.inputs[7])
        # gin.Image -> fingerintensity.A
        aptpro_dirt.links.new(gin.outputs[0], fingerintensity.inputs[6])
        # gin.FINGERPRINT AMOUNT -> fingerleveler.Factor
        aptpro_dirt.links.new(gin.outputs[1], fingerleveler.inputs[0])
        # gin.SMUDGE AMOUNT -> smudgeleveler.Factor
        aptpro_dirt.links.new(gin.outputs[3], smudgeleveler.inputs[0])
        # gin.SMUDGE INTENSITY -> smudgeintensity.Factor
        aptpro_dirt.links.new(gin.outputs[4], smudgeintensity.inputs[0])
        # smudgesheavy.Image -> sht.Image
        aptpro_dirt.links.new(smudgesheavy.outputs[0], sht.inputs[0])
        # smudgeintensity.Result -> gout.Image
        aptpro_dirt.links.new(smudgeintensity.outputs[2], gout.inputs[0])
        # fingerprintsheavy.Image -> fht.Image
        aptpro_dirt.links.new(fingerprintsheavy.outputs[0], fht.inputs[0])
        # gin.SEED -> seedrotation.Value
        aptpro_dirt.links.new(gin.outputs[5], seedrotation.inputs[0])
        # seedrotation.Value -> fht.Angle
        aptpro_dirt.links.new(seedrotation.outputs[0], fht.inputs[3])
        # fingerprintslight.Image -> flt.Image
        aptpro_dirt.links.new(fingerprintslight.outputs[0], flt.inputs[0])
        # flt.Image -> fltscale.Image
        aptpro_dirt.links.new(flt.outputs[0], fltscale.inputs[0])
        # seedrotation.Value -> flt.Angle
        aptpro_dirt.links.new(seedrotation.outputs[0], flt.inputs[3])
        # smudgeslight.Image -> slt.Image
        aptpro_dirt.links.new(smudgeslight.outputs[0], slt.inputs[0])
        # seedrotation.Value -> slt.Angle
        aptpro_dirt.links.new(seedrotation.outputs[0], slt.inputs[3])
        # seedrotation.Value -> sht.Angle
        aptpro_dirt.links.new(seedrotation.outputs[0], sht.inputs[3])
        # gin.FINGERPRINT INTENSITY -> fingerintensity.Factor
        aptpro_dirt.links.new(gin.outputs[2], fingerintensity.inputs[0])

        return aptpro_dirt

    aptpro_dirt = aptpro_dirt_node_group()

    def aperturia_fx_pro_node_group():
        """Initialize Aperturia FX Pro node group"""
        aperturia_fx_pro = bpy.data.node_groups.new(type = 'CompositorNodeTree', name = "Aperturia FX Pro")

        aperturia_fx_pro.color_tag = 'FILTER'
        aperturia_fx_pro.description = ""
        aperturia_fx_pro.default_group_node_width = 280
        aperturia_fx_pro.use_fake_user = True
        # aperturia_fx_pro interface

        # Socket Image
        image_socket_16 = aperturia_fx_pro.interface.new_socket(name="Image", in_out='OUTPUT', socket_type='NodeSocketColor')
        image_socket_16.default_value = (0.800000011920929, 0.800000011920929, 0.800000011920929, 1.0)
        image_socket_16.attribute_domain = 'POINT'
        image_socket_16.default_input = 'VALUE'
        image_socket_16.structure_type = 'AUTO'

        # Socket Image
        image_socket_17 = aperturia_fx_pro.interface.new_socket(name="Image", in_out='INPUT', socket_type='NodeSocketColor')
        image_socket_17.default_value = (1.0, 1.0, 1.0, 1.0)
        image_socket_17.attribute_domain = 'POINT'
        image_socket_17.default_input = 'VALUE'
        image_socket_17.structure_type = 'AUTO'

        # Socket ENABLED
        enabled_socket = aperturia_fx_pro.interface.new_socket(name="ENABLED", in_out='INPUT', socket_type='NodeSocketBool')
        enabled_socket.default_value = True
        enabled_socket.attribute_domain = 'POINT'
        enabled_socket.description = "Toggle the node"
        enabled_socket.default_input = 'VALUE'
        enabled_socket.structure_type = 'AUTO'

        # Panel Noise
        noise_panel = aperturia_fx_pro.interface.new_panel("Noise", default_closed=True)
        noise_panel.description = "Noise controls"
        # Socket Noise
        noise_socket = aperturia_fx_pro.interface.new_socket(name="Noise", in_out='INPUT', socket_type='NodeSocketBool', parent = noise_panel)
        noise_socket.default_value = False
        noise_socket.attribute_domain = 'POINT'
        noise_socket.default_input = 'VALUE'
        noise_socket.is_panel_toggle = True
        noise_socket.structure_type = 'AUTO'

        # Panel Basic Noise
        basic_noise_panel = aperturia_fx_pro.interface.new_panel("Basic Noise", default_closed=True)
        basic_noise_panel.description = "Basic noise controls"
        # Socket General Noise
        general_noise_socket_3 = aperturia_fx_pro.interface.new_socket(name="General Noise", in_out='INPUT', socket_type='NodeSocketFloat', parent = basic_noise_panel)
        general_noise_socket_3.default_value = 0.25
        general_noise_socket_3.min_value = 0.0
        general_noise_socket_3.max_value = 0.5
        general_noise_socket_3.subtype = 'FACTOR'
        general_noise_socket_3.attribute_domain = 'POINT'
        general_noise_socket_3.description = "Steady noise across the whole render"
        general_noise_socket_3.default_input = 'VALUE'
        general_noise_socket_3.structure_type = 'AUTO'

        # Socket Shadow Noise amount
        shadow_noise_amount_socket_1 = aperturia_fx_pro.interface.new_socket(name="Shadow Noise amount", in_out='INPUT', socket_type='NodeSocketFloat', parent = basic_noise_panel)
        shadow_noise_amount_socket_1.default_value = 0.25
        shadow_noise_amount_socket_1.min_value = 0.0
        shadow_noise_amount_socket_1.max_value = 0.5
        shadow_noise_amount_socket_1.subtype = 'FACTOR'
        shadow_noise_amount_socket_1.attribute_domain = 'POINT'
        shadow_noise_amount_socket_1.description = "Amount of noise in shaded areas"
        shadow_noise_amount_socket_1.default_input = 'VALUE'
        shadow_noise_amount_socket_1.structure_type = 'AUTO'


        aperturia_fx_pro.interface.move_to_parent(basic_noise_panel, noise_panel, 5)
        # Panel Advanced Noise
        advanced_noise_panel = aperturia_fx_pro.interface.new_panel("Advanced Noise", default_closed=True)
        advanced_noise_panel.description = "Advanced noise controls"
        # Socket Advanced Noise
        advanced_noise_socket_1 = aperturia_fx_pro.interface.new_socket(name="Advanced Noise", in_out='INPUT', socket_type='NodeSocketBool', parent = advanced_noise_panel)
        advanced_noise_socket_1.default_value = False
        advanced_noise_socket_1.attribute_domain = 'POINT'
        advanced_noise_socket_1.default_input = 'VALUE'
        advanced_noise_socket_1.is_panel_toggle = True
        advanced_noise_socket_1.structure_type = 'AUTO'

        # Socket Noise profile
        noise_profile_socket_1 = aperturia_fx_pro.interface.new_socket(name="Noise profile", in_out='INPUT', socket_type='NodeSocketInt', parent = advanced_noise_panel)
        noise_profile_socket_1.default_value = 1
        noise_profile_socket_1.min_value = 1
        noise_profile_socket_1.max_value = 6
        noise_profile_socket_1.subtype = 'NONE'
        noise_profile_socket_1.attribute_domain = 'POINT'
        noise_profile_socket_1.description = "Type of noise pattern"
        noise_profile_socket_1.default_input = 'VALUE'
        noise_profile_socket_1.structure_type = 'AUTO'

        # Socket Noise scale
        noise_scale_socket_2 = aperturia_fx_pro.interface.new_socket(name="Noise scale", in_out='INPUT', socket_type='NodeSocketFloat', parent = advanced_noise_panel)
        noise_scale_socket_2.default_value = 1.0
        noise_scale_socket_2.min_value = 0.0
        noise_scale_socket_2.max_value = 4.0
        noise_scale_socket_2.subtype = 'NONE'
        noise_scale_socket_2.attribute_domain = 'POINT'
        noise_scale_socket_2.description = "Noise pattern scale"
        noise_scale_socket_2.default_input = 'VALUE'
        noise_scale_socket_2.structure_type = 'AUTO'

        # Socket General noise
        general_noise_socket_4 = aperturia_fx_pro.interface.new_socket(name="General noise", in_out='INPUT', socket_type='NodeSocketFloat', parent = advanced_noise_panel)
        general_noise_socket_4.default_value = 0.10000000149011612
        general_noise_socket_4.min_value = 0.0
        general_noise_socket_4.max_value = 1.0
        general_noise_socket_4.subtype = 'FACTOR'
        general_noise_socket_4.attribute_domain = 'POINT'
        general_noise_socket_4.description = "Amount of noise"
        general_noise_socket_4.default_input = 'VALUE'
        general_noise_socket_4.structure_type = 'AUTO'

        # Socket Noise blend
        noise_blend_socket_1 = aperturia_fx_pro.interface.new_socket(name="Noise blend", in_out='INPUT', socket_type='NodeSocketFloat', parent = advanced_noise_panel)
        noise_blend_socket_1.default_value = 0.15000000596046448
        noise_blend_socket_1.min_value = 0.0
        noise_blend_socket_1.max_value = 1.0
        noise_blend_socket_1.subtype = 'NONE'
        noise_blend_socket_1.attribute_domain = 'POINT'
        noise_blend_socket_1.description = "Noise smoothness"
        noise_blend_socket_1.default_input = 'VALUE'
        noise_blend_socket_1.structure_type = 'AUTO'

        # Socket Color Noise intensity
        color_noise_intensity_socket_1 = aperturia_fx_pro.interface.new_socket(name="Color Noise intensity", in_out='INPUT', socket_type='NodeSocketFloat', parent = advanced_noise_panel)
        color_noise_intensity_socket_1.default_value = 1.0
        color_noise_intensity_socket_1.min_value = 0.0
        color_noise_intensity_socket_1.max_value = 1.0
        color_noise_intensity_socket_1.subtype = 'FACTOR'
        color_noise_intensity_socket_1.attribute_domain = 'POINT'
        color_noise_intensity_socket_1.description = "Amount of color noise"
        color_noise_intensity_socket_1.default_input = 'VALUE'
        color_noise_intensity_socket_1.structure_type = 'AUTO'

        # Socket Color Noise scale
        color_noise_scale_socket_2 = aperturia_fx_pro.interface.new_socket(name="Color Noise scale", in_out='INPUT', socket_type='NodeSocketFloat', parent = advanced_noise_panel)
        color_noise_scale_socket_2.default_value = 1.0
        color_noise_scale_socket_2.min_value = -10000.0
        color_noise_scale_socket_2.max_value = 10000.0
        color_noise_scale_socket_2.subtype = 'NONE'
        color_noise_scale_socket_2.attribute_domain = 'POINT'
        color_noise_scale_socket_2.description = "Size of color noise"
        color_noise_scale_socket_2.default_input = 'VALUE'
        color_noise_scale_socket_2.structure_type = 'AUTO'

        # Socket Color Noise blend
        color_noise_blend_socket_1 = aperturia_fx_pro.interface.new_socket(name="Color Noise blend", in_out='INPUT', socket_type='NodeSocketFloat', parent = advanced_noise_panel)
        color_noise_blend_socket_1.default_value = 0.10000000149011612
        color_noise_blend_socket_1.min_value = 0.0
        color_noise_blend_socket_1.max_value = 1.0
        color_noise_blend_socket_1.subtype = 'NONE'
        color_noise_blend_socket_1.attribute_domain = 'POINT'
        color_noise_blend_socket_1.description = "Color noise smoothness"
        color_noise_blend_socket_1.default_input = 'VALUE'
        color_noise_blend_socket_1.structure_type = 'AUTO'


        aperturia_fx_pro.interface.move_to_parent(advanced_noise_panel, noise_panel, 8)
        # Panel Shadow Mask editing
        shadow_mask_editing_panel = aperturia_fx_pro.interface.new_panel("Shadow Mask editing")
        shadow_mask_editing_panel.description = "Shadow mask editing"
        # Socket Shadow Mask preview
        shadow_mask_preview_socket_1 = aperturia_fx_pro.interface.new_socket(name="Shadow Mask preview", in_out='OUTPUT', socket_type='NodeSocketColor', parent = shadow_mask_editing_panel)
        shadow_mask_preview_socket_1.default_value = (0.0, 0.0, 0.0, 1.0)
        shadow_mask_preview_socket_1.attribute_domain = 'POINT'
        shadow_mask_preview_socket_1.description = "White = Shadow & Black = Light"
        shadow_mask_preview_socket_1.default_input = 'VALUE'
        shadow_mask_preview_socket_1.structure_type = 'AUTO'

        # Socket Shadow Mask lift
        shadow_mask_lift_socket_1 = aperturia_fx_pro.interface.new_socket(name="Shadow Mask lift", in_out='INPUT', socket_type='NodeSocketFloat', parent = shadow_mask_editing_panel)
        shadow_mask_lift_socket_1.default_value = 0.0
        shadow_mask_lift_socket_1.min_value = -1.0
        shadow_mask_lift_socket_1.max_value = 1.0
        shadow_mask_lift_socket_1.subtype = 'FACTOR'
        shadow_mask_lift_socket_1.attribute_domain = 'POINT'
        shadow_mask_lift_socket_1.description = "Correction for shadows"
        shadow_mask_lift_socket_1.default_input = 'VALUE'
        shadow_mask_lift_socket_1.structure_type = 'AUTO'

        # Socket Shadow Mask gamma
        shadow_mask_gamma_socket_1 = aperturia_fx_pro.interface.new_socket(name="Shadow Mask gamma", in_out='INPUT', socket_type='NodeSocketFloat', parent = shadow_mask_editing_panel)
        shadow_mask_gamma_socket_1.default_value = 1.0
        shadow_mask_gamma_socket_1.min_value = 0.0
        shadow_mask_gamma_socket_1.max_value = 2.0
        shadow_mask_gamma_socket_1.subtype = 'FACTOR'
        shadow_mask_gamma_socket_1.attribute_domain = 'POINT'
        shadow_mask_gamma_socket_1.description = "Correction for midtones"
        shadow_mask_gamma_socket_1.default_input = 'VALUE'
        shadow_mask_gamma_socket_1.structure_type = 'AUTO'

        # Socket Shadow Mask gain
        shadow_mask_gain_socket_1 = aperturia_fx_pro.interface.new_socket(name="Shadow Mask gain", in_out='INPUT', socket_type='NodeSocketFloat', parent = shadow_mask_editing_panel)
        shadow_mask_gain_socket_1.default_value = 1.0
        shadow_mask_gain_socket_1.min_value = 0.0
        shadow_mask_gain_socket_1.max_value = 2.0
        shadow_mask_gain_socket_1.subtype = 'FACTOR'
        shadow_mask_gain_socket_1.attribute_domain = 'POINT'
        shadow_mask_gain_socket_1.description = "Correction for highlights"
        shadow_mask_gain_socket_1.default_input = 'VALUE'
        shadow_mask_gain_socket_1.structure_type = 'AUTO'


        aperturia_fx_pro.interface.move_to_parent(shadow_mask_editing_panel, noise_panel, 17)

        # Panel Glare
        glare_panel = aperturia_fx_pro.interface.new_panel("Glare", default_closed=True)
        glare_panel.description = "Glare controls"
        # Socket Glare
        glare_socket = aperturia_fx_pro.interface.new_socket(name="Glare", in_out='INPUT', socket_type='NodeSocketBool', parent = glare_panel)
        glare_socket.default_value = False
        glare_socket.attribute_domain = 'POINT'
        glare_socket.default_input = 'VALUE'
        glare_socket.is_panel_toggle = True
        glare_socket.structure_type = 'AUTO'

        # Socket Glare Intensity
        glare_intensity_socket = aperturia_fx_pro.interface.new_socket(name="Glare Intensity", in_out='INPUT', socket_type='NodeSocketFloat', parent = glare_panel)
        glare_intensity_socket.default_value = 0.0
        glare_intensity_socket.min_value = 0.0
        glare_intensity_socket.max_value = 1.0
        glare_intensity_socket.subtype = 'NONE'
        glare_intensity_socket.attribute_domain = 'POINT'
        glare_intensity_socket.description = "Glare spill"
        glare_intensity_socket.default_input = 'VALUE'
        glare_intensity_socket.structure_type = 'AUTO'

        # Socket Glare Bloom
        glare_bloom_socket = aperturia_fx_pro.interface.new_socket(name="Glare Bloom", in_out='INPUT', socket_type='NodeSocketFloat', parent = glare_panel)
        glare_bloom_socket.default_value = 0.0
        glare_bloom_socket.min_value = 0.0
        glare_bloom_socket.max_value = 1.0
        glare_bloom_socket.subtype = 'NONE'
        glare_bloom_socket.attribute_domain = 'POINT'
        glare_bloom_socket.description = "Glare effect"
        glare_bloom_socket.default_input = 'VALUE'
        glare_bloom_socket.structure_type = 'AUTO'

        # Socket Emission pass
        emission_pass_socket_1 = aperturia_fx_pro.interface.new_socket(name="Emission pass", in_out='INPUT', socket_type='NodeSocketColor', parent = glare_panel)
        emission_pass_socket_1.default_value = (0.0, 0.0, 0.0, 1.0)
        emission_pass_socket_1.attribute_domain = 'POINT'
        emission_pass_socket_1.description = "Emission pass for light separation"
        emission_pass_socket_1.default_input = 'VALUE'
        emission_pass_socket_1.structure_type = 'AUTO'


        # Panel Vignette
        vignette_panel = aperturia_fx_pro.interface.new_panel("Vignette", default_closed=True)
        vignette_panel.description = "Vignette controls"
        # Socket Vignette
        vignette_socket = aperturia_fx_pro.interface.new_socket(name="Vignette", in_out='INPUT', socket_type='NodeSocketBool', parent = vignette_panel)
        vignette_socket.default_value = False
        vignette_socket.attribute_domain = 'POINT'
        vignette_socket.default_input = 'VALUE'
        vignette_socket.is_panel_toggle = True
        vignette_socket.structure_type = 'AUTO'

        # Socket Vignette amount
        vignette_amount_socket_2 = aperturia_fx_pro.interface.new_socket(name="Vignette amount", in_out='INPUT', socket_type='NodeSocketFloat', parent = vignette_panel)
        vignette_amount_socket_2.default_value = 0.0
        vignette_amount_socket_2.min_value = 0.0
        vignette_amount_socket_2.max_value = 1.0
        vignette_amount_socket_2.subtype = 'NONE'
        vignette_amount_socket_2.attribute_domain = 'POINT'
        vignette_amount_socket_2.default_input = 'VALUE'
        vignette_amount_socket_2.structure_type = 'AUTO'

        # Socket Vignette intensity
        vignette_intensity_socket_1 = aperturia_fx_pro.interface.new_socket(name="Vignette intensity", in_out='INPUT', socket_type='NodeSocketFloat', parent = vignette_panel)
        vignette_intensity_socket_1.default_value = 0.0
        vignette_intensity_socket_1.min_value = 0.0
        vignette_intensity_socket_1.max_value = 1.0
        vignette_intensity_socket_1.subtype = 'NONE'
        vignette_intensity_socket_1.attribute_domain = 'POINT'
        vignette_intensity_socket_1.default_input = 'VALUE'
        vignette_intensity_socket_1.structure_type = 'AUTO'

        # Socket Vignette softness
        vignette_softness_socket = aperturia_fx_pro.interface.new_socket(name="Vignette softness", in_out='INPUT', socket_type='NodeSocketFloat', parent = vignette_panel)
        vignette_softness_socket.default_value = 0.0
        vignette_softness_socket.min_value = 0.0
        vignette_softness_socket.max_value = 1.0
        vignette_softness_socket.subtype = 'NONE'
        vignette_softness_socket.attribute_domain = 'POINT'
        vignette_softness_socket.description = "Vignette fade"
        vignette_softness_socket.default_input = 'VALUE'
        vignette_softness_socket.structure_type = 'AUTO'


        # Panel Compression FX
        compression_fx_panel = aperturia_fx_pro.interface.new_panel("Compression FX", default_closed=True)
        compression_fx_panel.description = "Compression controls"
        # Socket Compression FX
        compression_fx_socket = aperturia_fx_pro.interface.new_socket(name="Compression FX", in_out='INPUT', socket_type='NodeSocketBool', parent = compression_fx_panel)
        compression_fx_socket.default_value = False
        compression_fx_socket.attribute_domain = 'POINT'
        compression_fx_socket.default_input = 'VALUE'
        compression_fx_socket.is_panel_toggle = True
        compression_fx_socket.structure_type = 'AUTO'

        # Socket Lens Distortion
        lens_distortion_socket = aperturia_fx_pro.interface.new_socket(name="Lens Distortion", in_out='INPUT', socket_type='NodeSocketFloat', parent = compression_fx_panel)
        lens_distortion_socket.default_value = 0.0
        lens_distortion_socket.min_value = 0.0
        lens_distortion_socket.max_value = 0.10000000149011612
        lens_distortion_socket.subtype = 'FACTOR'
        lens_distortion_socket.attribute_domain = 'POINT'
        lens_distortion_socket.description = "The amount of distortion. 0 means no distortion, -1 means full Pincushion distortion, and 1 means full Barrel distortion"
        lens_distortion_socket.default_input = 'VALUE'
        lens_distortion_socket.structure_type = 'AUTO'

        # Socket Lens Dispersion
        lens_dispersion_socket = aperturia_fx_pro.interface.new_socket(name="Lens Dispersion", in_out='INPUT', socket_type='NodeSocketFloat', parent = compression_fx_panel)
        lens_dispersion_socket.default_value = 0.004999999888241291
        lens_dispersion_socket.min_value = 0.0
        lens_dispersion_socket.max_value = 0.019999999552965164
        lens_dispersion_socket.subtype = 'FACTOR'
        lens_dispersion_socket.attribute_domain = 'POINT'
        lens_dispersion_socket.description = "The amount of chromatic aberration to add to the distortion"
        lens_dispersion_socket.default_input = 'VALUE'
        lens_dispersion_socket.structure_type = 'AUTO'

        # Socket Pixelation Size
        pixelation_size_socket_1 = aperturia_fx_pro.interface.new_socket(name="Pixelation Size", in_out='INPUT', socket_type='NodeSocketInt', parent = compression_fx_panel)
        pixelation_size_socket_1.default_value = 5
        pixelation_size_socket_1.min_value = 1
        pixelation_size_socket_1.max_value = 100
        pixelation_size_socket_1.subtype = 'NONE'
        pixelation_size_socket_1.attribute_domain = 'POINT'
        pixelation_size_socket_1.description = "The number of pixels that correspond to the same output pixel"
        pixelation_size_socket_1.default_input = 'VALUE'
        pixelation_size_socket_1.structure_type = 'AUTO'

        # Socket Compression intensity
        compression_intensity_socket_1 = aperturia_fx_pro.interface.new_socket(name="Compression intensity", in_out='INPUT', socket_type='NodeSocketFloat', parent = compression_fx_panel)
        compression_intensity_socket_1.default_value = 0.02500000037252903
        compression_intensity_socket_1.min_value = 0.0
        compression_intensity_socket_1.max_value = 0.05000000074505806
        compression_intensity_socket_1.subtype = 'FACTOR'
        compression_intensity_socket_1.attribute_domain = 'POINT'
        compression_intensity_socket_1.description = "Compression effect intensity"
        compression_intensity_socket_1.default_input = 'VALUE'
        compression_intensity_socket_1.structure_type = 'AUTO'

        # Socket Compression softness
        compression_softness_socket_1 = aperturia_fx_pro.interface.new_socket(name="Compression softness", in_out='INPUT', socket_type='NodeSocketFloat', parent = compression_fx_panel)
        compression_softness_socket_1.default_value = 0.0
        compression_softness_socket_1.min_value = 0.0
        compression_softness_socket_1.max_value = 100.0
        compression_softness_socket_1.subtype = 'NONE'
        compression_softness_socket_1.attribute_domain = 'POINT'
        compression_softness_socket_1.description = "Effect blend"
        compression_softness_socket_1.default_input = 'VALUE'
        compression_softness_socket_1.structure_type = 'AUTO'

        # Socket Compression Noise scale
        compression_noise_scale_socket_1 = aperturia_fx_pro.interface.new_socket(name="Compression Noise scale", in_out='INPUT', socket_type='NodeSocketFloat', parent = compression_fx_panel)
        compression_noise_scale_socket_1.default_value = 100.0
        compression_noise_scale_socket_1.min_value = 0.0
        compression_noise_scale_socket_1.max_value = 100.0
        compression_noise_scale_socket_1.subtype = 'FACTOR'
        compression_noise_scale_socket_1.attribute_domain = 'POINT'
        compression_noise_scale_socket_1.description = "Noise scale"
        compression_noise_scale_socket_1.default_input = 'VALUE'
        compression_noise_scale_socket_1.structure_type = 'AUTO'

        # Socket Compression Noise blend
        compression_noise_blend_socket_1 = aperturia_fx_pro.interface.new_socket(name="Compression Noise blend", in_out='INPUT', socket_type='NodeSocketFloat', parent = compression_fx_panel)
        compression_noise_blend_socket_1.default_value = 1.0
        compression_noise_blend_socket_1.min_value = 0.0
        compression_noise_blend_socket_1.max_value = 1.0
        compression_noise_blend_socket_1.subtype = 'NONE'
        compression_noise_blend_socket_1.attribute_domain = 'POINT'
        compression_noise_blend_socket_1.description = "Noise smoothness"
        compression_noise_blend_socket_1.default_input = 'VALUE'
        compression_noise_blend_socket_1.structure_type = 'AUTO'


        # Panel Smudge FX
        smudge_fx_panel = aperturia_fx_pro.interface.new_panel("Smudge FX", default_closed=True)
        smudge_fx_panel.description = "Smudge controls"
        # Socket Smudge FX
        smudge_fx_socket = aperturia_fx_pro.interface.new_socket(name="Smudge FX", in_out='INPUT', socket_type='NodeSocketBool', parent = smudge_fx_panel)
        smudge_fx_socket.default_value = False
        smudge_fx_socket.attribute_domain = 'POINT'
        smudge_fx_socket.default_input = 'VALUE'
        smudge_fx_socket.is_panel_toggle = True
        smudge_fx_socket.structure_type = 'AUTO'

        # Socket Seed
        seed_socket_1 = aperturia_fx_pro.interface.new_socket(name="Seed", in_out='INPUT', socket_type='NodeSocketInt', parent = smudge_fx_panel)
        seed_socket_1.default_value = 0
        seed_socket_1.min_value = 0
        seed_socket_1.max_value = 2147483647
        seed_socket_1.subtype = 'NONE'
        seed_socket_1.attribute_domain = 'POINT'
        seed_socket_1.description = "Random pattern seed"
        seed_socket_1.default_input = 'VALUE'
        seed_socket_1.structure_type = 'AUTO'

        # Socket Fingerprint amount
        fingerprint_amount_socket_1 = aperturia_fx_pro.interface.new_socket(name="Fingerprint amount", in_out='INPUT', socket_type='NodeSocketFloat', parent = smudge_fx_panel)
        fingerprint_amount_socket_1.default_value = 0.10000000149011612
        fingerprint_amount_socket_1.min_value = 0.0
        fingerprint_amount_socket_1.max_value = 1.0
        fingerprint_amount_socket_1.subtype = 'NONE'
        fingerprint_amount_socket_1.attribute_domain = 'POINT'
        fingerprint_amount_socket_1.description = "Quantity of effect"
        fingerprint_amount_socket_1.default_input = 'VALUE'
        fingerprint_amount_socket_1.structure_type = 'AUTO'

        # Socket Fingerprint intensity
        fingerprint_intensity_socket_1 = aperturia_fx_pro.interface.new_socket(name="Fingerprint intensity", in_out='INPUT', socket_type='NodeSocketFloat', parent = smudge_fx_panel)
        fingerprint_intensity_socket_1.default_value = 0.10000000149011612
        fingerprint_intensity_socket_1.min_value = 0.0
        fingerprint_intensity_socket_1.max_value = 1.0
        fingerprint_intensity_socket_1.subtype = 'NONE'
        fingerprint_intensity_socket_1.attribute_domain = 'POINT'
        fingerprint_intensity_socket_1.description = "Intensity of effect"
        fingerprint_intensity_socket_1.default_input = 'VALUE'
        fingerprint_intensity_socket_1.structure_type = 'AUTO'

        # Socket Smudge amount
        smudge_amount_socket_1 = aperturia_fx_pro.interface.new_socket(name="Smudge amount", in_out='INPUT', socket_type='NodeSocketFloat', parent = smudge_fx_panel)
        smudge_amount_socket_1.default_value = 0.10000000149011612
        smudge_amount_socket_1.min_value = 0.0
        smudge_amount_socket_1.max_value = 1.0
        smudge_amount_socket_1.subtype = 'NONE'
        smudge_amount_socket_1.attribute_domain = 'POINT'
        smudge_amount_socket_1.description = "Quantity of effect"
        smudge_amount_socket_1.default_input = 'VALUE'
        smudge_amount_socket_1.structure_type = 'AUTO'

        # Socket Smudge intensity
        smudge_intensity_socket_1 = aperturia_fx_pro.interface.new_socket(name="Smudge intensity", in_out='INPUT', socket_type='NodeSocketFloat', parent = smudge_fx_panel)
        smudge_intensity_socket_1.default_value = 0.10000000149011612
        smudge_intensity_socket_1.min_value = 0.0
        smudge_intensity_socket_1.max_value = 1.0
        smudge_intensity_socket_1.subtype = 'NONE'
        smudge_intensity_socket_1.attribute_domain = 'POINT'
        smudge_intensity_socket_1.description = "Intensity of effect"
        smudge_intensity_socket_1.default_input = 'VALUE'
        smudge_intensity_socket_1.structure_type = 'AUTO'


        # Panel Advanced Shadow Mask (OPTIONAL)
        advanced_shadow_mask__optional__panel = aperturia_fx_pro.interface.new_panel("Advanced Shadow Mask (OPTIONAL)", default_closed=True)
        advanced_shadow_mask__optional__panel.description = "Advanced shadow mask"
        # Socket Advanced Shadow Mask (OPTIONAL)
        advanced_shadow_mask__optional__socket = aperturia_fx_pro.interface.new_socket(name="Advanced Shadow Mask (OPTIONAL)", in_out='INPUT', socket_type='NodeSocketBool', parent = advanced_shadow_mask__optional__panel)
        advanced_shadow_mask__optional__socket.default_value = False
        advanced_shadow_mask__optional__socket.attribute_domain = 'POINT'
        advanced_shadow_mask__optional__socket.default_input = 'VALUE'
        advanced_shadow_mask__optional__socket.is_panel_toggle = True
        advanced_shadow_mask__optional__socket.structure_type = 'AUTO'

        # Socket Diffuse Direct
        diffuse_direct_socket_1 = aperturia_fx_pro.interface.new_socket(name="Diffuse Direct", in_out='INPUT', socket_type='NodeSocketColor', parent = advanced_shadow_mask__optional__panel)
        diffuse_direct_socket_1.default_value = (1.0, 1.0, 1.0, 1.0)
        diffuse_direct_socket_1.attribute_domain = 'POINT'
        diffuse_direct_socket_1.description = "View Layer > Diffuse Direct"
        diffuse_direct_socket_1.default_input = 'VALUE'
        diffuse_direct_socket_1.structure_type = 'AUTO'

        # Socket Glossy Direct
        glossy_direct_socket_1 = aperturia_fx_pro.interface.new_socket(name="Glossy Direct", in_out='INPUT', socket_type='NodeSocketColor', parent = advanced_shadow_mask__optional__panel)
        glossy_direct_socket_1.default_value = (1.0, 1.0, 1.0, 1.0)
        glossy_direct_socket_1.attribute_domain = 'POINT'
        glossy_direct_socket_1.description = "View Layer > Glossy Direct"
        glossy_direct_socket_1.default_input = 'VALUE'
        glossy_direct_socket_1.structure_type = 'AUTO'

        # Socket Transmission Indirect
        transmission_indirect_socket_1 = aperturia_fx_pro.interface.new_socket(name="Transmission Indirect", in_out='INPUT', socket_type='NodeSocketColor', parent = advanced_shadow_mask__optional__panel)
        transmission_indirect_socket_1.default_value = (1.0, 1.0, 1.0, 1.0)
        transmission_indirect_socket_1.attribute_domain = 'POINT'
        transmission_indirect_socket_1.description = "View Layer > Transmission Indirect"
        transmission_indirect_socket_1.default_input = 'VALUE'
        transmission_indirect_socket_1.structure_type = 'AUTO'

        # Socket Volume Direct
        volume_direct_socket_1 = aperturia_fx_pro.interface.new_socket(name="Volume Direct", in_out='INPUT', socket_type='NodeSocketColor', parent = advanced_shadow_mask__optional__panel)
        volume_direct_socket_1.default_value = (1.0, 1.0, 1.0, 1.0)
        volume_direct_socket_1.attribute_domain = 'POINT'
        volume_direct_socket_1.description = "View Layer > Volume Direct"
        volume_direct_socket_1.default_input = 'VALUE'
        volume_direct_socket_1.structure_type = 'AUTO'

        # Socket Emission
        emission_socket_1 = aperturia_fx_pro.interface.new_socket(name="Emission", in_out='INPUT', socket_type='NodeSocketColor', parent = advanced_shadow_mask__optional__panel)
        emission_socket_1.default_value = (1.0, 1.0, 1.0, 1.0)
        emission_socket_1.attribute_domain = 'POINT'
        emission_socket_1.description = "View Layer > Emission"
        emission_socket_1.default_input = 'VALUE'
        emission_socket_1.structure_type = 'AUTO'

        # Socket Environment
        environment_socket_1 = aperturia_fx_pro.interface.new_socket(name="Environment", in_out='INPUT', socket_type='NodeSocketColor', parent = advanced_shadow_mask__optional__panel)
        environment_socket_1.default_value = (1.0, 1.0, 1.0, 1.0)
        environment_socket_1.attribute_domain = 'POINT'
        environment_socket_1.description = "View Layer > Environment"
        environment_socket_1.default_input = 'VALUE'
        environment_socket_1.structure_type = 'AUTO'

        # Socket Ambient Occlusion
        ambient_occlusion_socket_1 = aperturia_fx_pro.interface.new_socket(name="Ambient Occlusion", in_out='INPUT', socket_type='NodeSocketColor', parent = advanced_shadow_mask__optional__panel)
        ambient_occlusion_socket_1.default_value = (1.0, 1.0, 1.0, 1.0)
        ambient_occlusion_socket_1.attribute_domain = 'POINT'
        ambient_occlusion_socket_1.description = "View Layer > Ambient Occlusion"
        ambient_occlusion_socket_1.default_input = 'VALUE'
        ambient_occlusion_socket_1.structure_type = 'AUTO'


        # Initialize aperturia_fx_pro nodes

        # Node Group Output
        group_output_6 = aperturia_fx_pro.nodes.new("NodeGroupOutput")
        group_output_6.name = "Group Output"
        group_output_6.is_active_output = True

        # Node Group Input
        group_input_6 = aperturia_fx_pro.nodes.new("NodeGroupInput")
        group_input_6.name = "Group Input"

        # Node AptPro LENS FLARE
        aptpro_lens_flare_1 = aperturia_fx_pro.nodes.new("CompositorNodeGroup")
        aptpro_lens_flare_1.label = "AptPro LENS FLARE"
        aptpro_lens_flare_1.name = "AptPro LENS FLARE"
        aptpro_lens_flare_1.node_tree = aptpro_lens_flare

        # Node SMandLF
        smandlf = aperturia_fx_pro.nodes.new("ShaderNodeMix")
        smandlf.label = "SMandLF"
        smandlf.name = "SMandLF"
        smandlf.blend_type = 'SCREEN'
        smandlf.clamp_factor = False
        smandlf.clamp_result = True
        smandlf.data_type = 'RGBA'
        smandlf.factor_mode = 'UNIFORM'
        # Factor_Float
        smandlf.inputs[0].default_value = 1.0

        # Node LensFlareBW
        lensflarebw = aperturia_fx_pro.nodes.new("CompositorNodeRGBToBW")
        lensflarebw.label = "LensFlareBW"
        lensflarebw.name = "LensFlareBW"

        # Node AptPro SHADOW MASK
        aptpro_shadow_mask_1 = aperturia_fx_pro.nodes.new("CompositorNodeGroup")
        aptpro_shadow_mask_1.label = "AptPro SHADOW MASK"
        aptpro_shadow_mask_1.name = "AptPro SHADOW MASK"
        aptpro_shadow_mask_1.node_tree = aptpro_shadow_mask

        # Node GlareandVig
        glareandvig = aperturia_fx_pro.nodes.new("ShaderNodeMix")
        glareandvig.label = "GlareandVig"
        glareandvig.name = "GlareandVig"
        glareandvig.blend_type = 'MULTIPLY'
        glareandvig.clamp_factor = False
        glareandvig.clamp_result = False
        glareandvig.data_type = 'RGBA'
        glareandvig.factor_mode = 'UNIFORM'

        # Node AptPro VIGNETTE
        aptpro_vignette_1 = aperturia_fx_pro.nodes.new("CompositorNodeGroup")
        aptpro_vignette_1.label = "AptPro VIGNETTE"
        aptpro_vignette_1.name = "AptPro VIGNETTE"
        aptpro_vignette_1.node_tree = aptpro_vignette

        # Node AptPro COMPRESSION EFFECTS
        aptpro_compression_effects_1 = aperturia_fx_pro.nodes.new("CompositorNodeGroup")
        aptpro_compression_effects_1.label = "AptPro COMPRESSION EFFECTS"
        aptpro_compression_effects_1.name = "AptPro COMPRESSION EFFECTS"
        aptpro_compression_effects_1.node_tree = aptpro_compression_effects

        # Node AptPro NOISE PATTERNS
        aptpro_noise_patterns_1 = aperturia_fx_pro.nodes.new("CompositorNodeGroup")
        aptpro_noise_patterns_1.label = "AptPro NOISE PATTERNS"
        aptpro_noise_patterns_1.name = "AptPro NOISE PATTERNS"
        aptpro_noise_patterns_1.node_tree = aptpro_noise_patterns

        # Node AptPro DIRT
        aptpro_dirt_1 = aperturia_fx_pro.nodes.new("CompositorNodeGroup")
        aptpro_dirt_1.label = "AptPro DIRT"
        aptpro_dirt_1.name = "AptPro DIRT"
        aptpro_dirt_1.node_tree = aptpro_dirt

        # Node ImageToBW
        imagetobw = aperturia_fx_pro.nodes.new("CompositorNodeRGBToBW")
        imagetobw.label = "ImageToBW"
        imagetobw.name = "ImageToBW"

        # Node ShadowMaskINV
        shadowmaskinv = aperturia_fx_pro.nodes.new("CompositorNodeInvert")
        shadowmaskinv.label = "ShadowMaskINV"
        shadowmaskinv.name = "ShadowMaskINV"
        # Fac
        shadowmaskinv.inputs[0].default_value = 1.0
        # Invert Color
        shadowmaskinv.inputs[2].default_value = True
        # Invert Alpha
        shadowmaskinv.inputs[3].default_value = False

        # Node GlareToImage
        glaretoimage = aperturia_fx_pro.nodes.new("ShaderNodeMix")
        glaretoimage.label = "GlareToImage"
        glaretoimage.name = "GlareToImage"
        glaretoimage.blend_type = 'LIGHTEN'
        glaretoimage.clamp_factor = False
        glaretoimage.clamp_result = False
        glaretoimage.data_type = 'RGBA'
        glaretoimage.factor_mode = 'UNIFORM'
        # Factor_Float
        glaretoimage.inputs[0].default_value = 1.0

        # Node Reroute
        reroute_2 = aperturia_fx_pro.nodes.new("NodeReroute")
        reroute_2.name = "Reroute"
        reroute_2.socket_idname = "NodeSocketColor"
        # Node VectorMathColornoiseScale
        vectormathcolornoisescale = aperturia_fx_pro.nodes.new("ShaderNodeVectorMath")
        vectormathcolornoisescale.label = "VectorMathColornoiseScale"
        vectormathcolornoisescale.name = "VectorMathColornoiseScale"
        vectormathcolornoisescale.operation = 'SCALE'
        # Vector
        vectormathcolornoisescale.inputs[0].default_value = (100.0, 100.0, 100.0)

        # Node NoiseToggle
        noisetoggle = aperturia_fx_pro.nodes.new("ShaderNodeMix")
        noisetoggle.label = "NoiseToggle"
        noisetoggle.name = "NoiseToggle"
        noisetoggle.blend_type = 'MIX'
        noisetoggle.clamp_factor = True
        noisetoggle.clamp_result = False
        noisetoggle.data_type = 'RGBA'
        noisetoggle.factor_mode = 'UNIFORM'

        # Node CompressionToggle
        compressiontoggle = aperturia_fx_pro.nodes.new("ShaderNodeMix")
        compressiontoggle.label = "CompresionToggle"
        compressiontoggle.name = "CompressionToggle"
        compressiontoggle.blend_type = 'MIX'
        compressiontoggle.clamp_factor = True
        compressiontoggle.clamp_result = False
        compressiontoggle.data_type = 'RGBA'
        compressiontoggle.factor_mode = 'UNIFORM'

        # Node DirtToggle
        dirttoggle = aperturia_fx_pro.nodes.new("ShaderNodeMix")
        dirttoggle.label = "DirtToggle"
        dirttoggle.name = "DirtToggle"
        dirttoggle.blend_type = 'MIX'
        dirttoggle.clamp_factor = True
        dirttoggle.clamp_result = False
        dirttoggle.data_type = 'RGBA'
        dirttoggle.factor_mode = 'UNIFORM'

        # Node ShadowMaskToggle
        shadowmasktoggle = aperturia_fx_pro.nodes.new("ShaderNodeMix")
        shadowmasktoggle.label = "ShadowMaskToggle"
        shadowmasktoggle.name = "ShadowMaskToggle"
        shadowmasktoggle.hide = True
        shadowmasktoggle.blend_type = 'MIX'
        shadowmasktoggle.clamp_factor = True
        shadowmasktoggle.clamp_result = False
        shadowmasktoggle.data_type = 'RGBA'
        shadowmasktoggle.factor_mode = 'UNIFORM'

        # Node GlareToggle
        glaretoggle = aperturia_fx_pro.nodes.new("ShaderNodeMix")
        glaretoggle.label = "GlareToggle"
        glaretoggle.name = "GlareToggle"
        glaretoggle.hide = True
        glaretoggle.blend_type = 'MIX'
        glaretoggle.clamp_factor = True
        glaretoggle.clamp_result = False
        glaretoggle.data_type = 'RGBA'
        glaretoggle.factor_mode = 'UNIFORM'
        # A_Color
        glaretoggle.inputs[6].default_value = (0.0, 0.0, 0.0, 1.0)

        # Node VignetteToggle
        vignettetoggle = aperturia_fx_pro.nodes.new("ShaderNodeMix")
        vignettetoggle.label = "VignetteToggle"
        vignettetoggle.name = "VignetteToggle"
        vignettetoggle.blend_type = 'MIX'
        vignettetoggle.clamp_factor = False
        vignettetoggle.clamp_result = False
        vignettetoggle.data_type = 'RGBA'
        vignettetoggle.factor_mode = 'UNIFORM'
        # A_Color
        vignettetoggle.inputs[6].default_value = (1.0, 1.0, 1.0, 1.0)

        # Node EffectEnabler
        effectenabler = aperturia_fx_pro.nodes.new("ShaderNodeMix")
        effectenabler.label = "EffectEnabler"
        effectenabler.name = "EffectEnabler"
        effectenabler.blend_type = 'MIX'
        effectenabler.clamp_factor = True
        effectenabler.clamp_result = False
        effectenabler.data_type = 'RGBA'
        effectenabler.factor_mode = 'UNIFORM'

        # Node Reroute.001
        reroute_001_1 = aperturia_fx_pro.nodes.new("NodeReroute")
        reroute_001_1.name = "Reroute.001"
        reroute_001_1.socket_idname = "NodeSocketColor"
        # Node Reroute.002
        reroute_002 = aperturia_fx_pro.nodes.new("NodeReroute")
        reroute_002.name = "Reroute.002"
        reroute_002.socket_idname = "NodeSocketColor"
        # Node ImageCC
        imagecc = aperturia_fx_pro.nodes.new("CompositorNodeColorCorrection")
        imagecc.label = "ImageCC"
        imagecc.name = "ImageCC"
        # Mask
        imagecc.inputs[1].default_value = 1.0
        # Master Saturation
        imagecc.inputs[2].default_value = 1.0
        # Master Contrast
        imagecc.inputs[3].default_value = 1.0
        # Master Gamma
        imagecc.inputs[4].default_value = 1.0
        # Master Gain
        imagecc.inputs[5].default_value = 1.0
        # Master Lift
        imagecc.inputs[6].default_value = 0.0
        # Highlights Saturation
        imagecc.inputs[7].default_value = 1.0
        # Highlights Contrast
        imagecc.inputs[8].default_value = 1.0
        # Highlights Gamma
        imagecc.inputs[9].default_value = 1.0
        # Highlights Gain
        imagecc.inputs[10].default_value = 1.0
        # Highlights Lift
        imagecc.inputs[11].default_value = 0.0
        # Midtones Saturation
        imagecc.inputs[12].default_value = 1.0
        # Midtones Contrast
        imagecc.inputs[13].default_value = 1.0
        # Midtones Gamma
        imagecc.inputs[14].default_value = 1.0
        # Midtones Gain
        imagecc.inputs[15].default_value = 1.0
        # Midtones Lift
        imagecc.inputs[16].default_value = 0.0
        # Shadows Saturation
        imagecc.inputs[17].default_value = 0.8999999761581421
        # Shadows Contrast
        imagecc.inputs[18].default_value = 0.9800000190734863
        # Shadows Gamma
        imagecc.inputs[19].default_value = 1.0499999523162842
        # Shadows Gain
        imagecc.inputs[20].default_value = 1.0
        # Shadows Lift
        imagecc.inputs[21].default_value = 0.0
        # Midtones Start
        imagecc.inputs[22].default_value = 0.20000000298023224
        # Midtones End
        imagecc.inputs[23].default_value = 0.699999988079071
        # Apply On Red
        imagecc.inputs[24].default_value = True
        # Apply On Green
        imagecc.inputs[25].default_value = True
        # Apply On Blue
        imagecc.inputs[26].default_value = True

        # Node LDmain
        ldmain = aperturia_fx_pro.nodes.new("CompositorNodeLensdist")
        ldmain.label = "LDmain"
        ldmain.name = "LDmain"
        ldmain.distortion_type = 'RADIAL'
        # Jitter
        ldmain.inputs[3].default_value = False
        # Fit
        ldmain.inputs[4].default_value = True

        # Set locations
        group_output_6.location = (2777.1435546875, 34.947628021240234)
        group_input_6.location = (-2203.71435546875, -30.557939529418945)
        aptpro_lens_flare_1.location = (-1467.7418212890625, -106.50316619873047)
        smandlf.location = (-832.7799682617188, -266.4405212402344)
        lensflarebw.location = (-1091.591552734375, -113.55021667480469)
        aptpro_shadow_mask_1.location = (-1464.843505859375, -313.6114501953125)
        glareandvig.location = (-437.79241943359375, 183.40538024902344)
        aptpro_vignette_1.location = (-1467.0501708984375, 275.04168701171875)
        aptpro_compression_effects_1.location = (1405.2425537109375, 67.09741973876953)
        aptpro_noise_patterns_1.location = (354.41607666015625, 72.36261749267578)
        aptpro_dirt_1.location = (2006.4580078125, 66.65879821777344)
        imagetobw.location = (-1345.5596923828125, -634.0414428710938)
        shadowmaskinv.location = (-365.9837951660156, -374.7533264160156)
        glaretoimage.location = (-608.4063720703125, -17.780288696289062)
        reroute_2.location = (149.646728515625, -14.069398880004883)
        vectormathcolornoisescale.location = (131.726318359375, -289.7618408203125)
        noisetoggle.location = (656.7740478515625, -206.5253448486328)
        compressiontoggle.location = (1745.7706298828125, -200.57044982910156)
        dirttoggle.location = (2309.838134765625, -200.57044982910156)
        shadowmasktoggle.location = (-1046.9134521484375, -452.5921936035156)
        glaretoggle.location = (-910.0542602539062, -81.56927490234375)
        vignettetoggle.location = (-911.13671875, 256.91351318359375)
        effectenabler.location = (2512.927490234375, 35.711883544921875)
        reroute_001_1.location = (1365.821044921875, 161.6981964111328)
        reroute_002.location = (2612.1728515625, 161.3381805419922)
        imagecc.location = (-248.49563598632812, 176.67005920410156)
        ldmain.location = (1026.914306640625, -193.9180145263672)

        # Set dimensions
        group_output_6.width, group_output_6.height = 140.0, 100.0
        group_input_6.width, group_input_6.height = 140.0, 100.0
        aptpro_lens_flare_1.width, aptpro_lens_flare_1.height = 353.7291259765625, 100.0
        smandlf.width, smandlf.height = 140.0, 100.0
        lensflarebw.width, lensflarebw.height = 140.0, 100.0
        aptpro_shadow_mask_1.width, aptpro_shadow_mask_1.height = 341.9908447265625, 100.0
        glareandvig.width, glareandvig.height = 140.0, 100.0
        aptpro_vignette_1.width, aptpro_vignette_1.height = 335.9400634765625, 100.0
        aptpro_compression_effects_1.width, aptpro_compression_effects_1.height = 273.59521484375, 100.0
        aptpro_noise_patterns_1.width, aptpro_noise_patterns_1.height = 240.81103515625, 100.0
        aptpro_dirt_1.width, aptpro_dirt_1.height = 240.037353515625, 100.0
        imagetobw.width, imagetobw.height = 140.0, 100.0
        shadowmaskinv.width, shadowmaskinv.height = 140.0, 100.0
        glaretoimage.width, glaretoimage.height = 140.0, 100.0
        reroute_2.width, reroute_2.height = 10.0, 100.0
        vectormathcolornoisescale.width, vectormathcolornoisescale.height = 140.0, 100.0
        noisetoggle.width, noisetoggle.height = 140.0, 100.0
        compressiontoggle.width, compressiontoggle.height = 140.0, 100.0
        dirttoggle.width, dirttoggle.height = 140.0, 100.0
        shadowmasktoggle.width, shadowmasktoggle.height = 140.0, 100.0
        glaretoggle.width, glaretoggle.height = 140.0, 100.0
        vignettetoggle.width, vignettetoggle.height = 140.0, 100.0
        effectenabler.width, effectenabler.height = 140.0, 100.0
        reroute_001_1.width, reroute_001_1.height = 10.0, 100.0
        reroute_002.width, reroute_002.height = 10.0, 100.0
        imagecc.width, imagecc.height = 286.35882568359375, 100.0
        ldmain.width, ldmain.height = 140.0, 100.0

        # Initialize aperturia_fx_pro links

        # aptpro_lens_flare_1.Image -> lensflarebw.Image
        aperturia_fx_pro.links.new(aptpro_lens_flare_1.outputs[0], lensflarebw.inputs[0])
        # group_input_6.Image -> aptpro_lens_flare_1.Image
        aperturia_fx_pro.links.new(group_input_6.outputs[0], aptpro_lens_flare_1.inputs[0])
        # group_input_6.Emission pass -> aptpro_lens_flare_1.Emission pass
        aperturia_fx_pro.links.new(group_input_6.outputs[19], aptpro_lens_flare_1.inputs[1])
        # group_input_6.Glare Bloom -> aptpro_lens_flare_1.General Bloom
        aperturia_fx_pro.links.new(group_input_6.outputs[18], aptpro_lens_flare_1.inputs[2])
        # group_input_6.Glare Intensity -> aptpro_lens_flare_1.Lens Flare intensity
        aperturia_fx_pro.links.new(group_input_6.outputs[17], aptpro_lens_flare_1.inputs[3])
        # group_input_6.Vignette intensity -> aptpro_vignette_1.VIGNETTE INTENSITY
        aperturia_fx_pro.links.new(group_input_6.outputs[22], aptpro_vignette_1.inputs[0])
        # group_input_6.Vignette softness -> aptpro_vignette_1.VIGNETTE SHARPNESS
        aperturia_fx_pro.links.new(group_input_6.outputs[23], aptpro_vignette_1.inputs[1])
        # group_input_6.Vignette amount -> aptpro_vignette_1.VIGNETTE AMOUNT
        aperturia_fx_pro.links.new(group_input_6.outputs[21], aptpro_vignette_1.inputs[2])
        # group_input_6.Image -> imagetobw.Image
        aperturia_fx_pro.links.new(group_input_6.outputs[0], imagetobw.inputs[0])
        # aptpro_vignette_1.VIGNETTE AMOUNT -> glareandvig.Factor
        aperturia_fx_pro.links.new(aptpro_vignette_1.outputs[1], glareandvig.inputs[0])
        # lensflarebw.Val -> smandlf.A
        aperturia_fx_pro.links.new(lensflarebw.outputs[0], smandlf.inputs[6])
        # smandlf.Result -> shadowmaskinv.Color
        aperturia_fx_pro.links.new(smandlf.outputs[2], shadowmaskinv.inputs[1])
        # group_input_6.Image -> glaretoimage.A
        aperturia_fx_pro.links.new(group_input_6.outputs[0], glaretoimage.inputs[6])
        # glaretoimage.Result -> glareandvig.A
        aperturia_fx_pro.links.new(glaretoimage.outputs[2], glareandvig.inputs[6])
        # group_input_6.Noise profile -> aptpro_noise_patterns_1.Profile
        aperturia_fx_pro.links.new(group_input_6.outputs[6], aptpro_noise_patterns_1.inputs[1])
        # group_input_6.General noise -> aptpro_noise_patterns_1.GENERAL NOISE
        aperturia_fx_pro.links.new(group_input_6.outputs[8], aptpro_noise_patterns_1.inputs[2])
        # group_input_6.Noise blend -> aptpro_noise_patterns_1.NOISE BLEND
        aperturia_fx_pro.links.new(group_input_6.outputs[9], aptpro_noise_patterns_1.inputs[3])
        # vectormathcolornoisescale.Vector -> aptpro_noise_patterns_1.COLOR NOISE SCALE
        aperturia_fx_pro.links.new(vectormathcolornoisescale.outputs[0], aptpro_noise_patterns_1.inputs[4])
        # group_input_6.Color Noise scale -> vectormathcolornoisescale.Scale
        aperturia_fx_pro.links.new(group_input_6.outputs[11], vectormathcolornoisescale.inputs[3])
        # group_input_6.Color Noise blend -> aptpro_noise_patterns_1.COLOR NOISE BLEND
        aperturia_fx_pro.links.new(group_input_6.outputs[12], aptpro_noise_patterns_1.inputs[5])
        # group_input_6.Color Noise intensity -> aptpro_noise_patterns_1.COLOR NOISE INTENSITY
        aperturia_fx_pro.links.new(group_input_6.outputs[10], aptpro_noise_patterns_1.inputs[6])
        # group_input_6.Noise -> noisetoggle.Factor
        aperturia_fx_pro.links.new(group_input_6.outputs[2], noisetoggle.inputs[0])
        # aptpro_noise_patterns_1.Image -> noisetoggle.B
        aperturia_fx_pro.links.new(aptpro_noise_patterns_1.outputs[0], noisetoggle.inputs[7])
        # aptpro_compression_effects_1.Image -> compressiontoggle.B
        aperturia_fx_pro.links.new(aptpro_compression_effects_1.outputs[0], compressiontoggle.inputs[7])
        # aptpro_dirt_1.Image -> dirttoggle.B
        aperturia_fx_pro.links.new(aptpro_dirt_1.outputs[0], dirttoggle.inputs[7])
        # compressiontoggle.Result -> dirttoggle.A
        aperturia_fx_pro.links.new(compressiontoggle.outputs[2], dirttoggle.inputs[6])
        # effectenabler.Result -> group_output_6.Image
        aperturia_fx_pro.links.new(effectenabler.outputs[2], group_output_6.inputs[0])
        # group_input_6.Compression FX -> compressiontoggle.Factor
        aperturia_fx_pro.links.new(group_input_6.outputs[24], compressiontoggle.inputs[0])
        # group_input_6.Compression intensity -> aptpro_compression_effects_1.COMPRESSION INTENSITY
        aperturia_fx_pro.links.new(group_input_6.outputs[28], aptpro_compression_effects_1.inputs[1])
        # group_input_6.Compression Noise scale -> aptpro_compression_effects_1.COMPRESSION NOISE SCALE
        aperturia_fx_pro.links.new(group_input_6.outputs[30], aptpro_compression_effects_1.inputs[2])
        # group_input_6.Compression Noise blend -> aptpro_compression_effects_1.COMPRESSION NOISE BLEND
        aperturia_fx_pro.links.new(group_input_6.outputs[31], aptpro_compression_effects_1.inputs[3])
        # group_input_6.Fingerprint amount -> aptpro_dirt_1.FINGERPRINT AMOUNT
        aperturia_fx_pro.links.new(group_input_6.outputs[34], aptpro_dirt_1.inputs[1])
        # group_input_6.Smudge FX -> dirttoggle.Factor
        aperturia_fx_pro.links.new(group_input_6.outputs[32], dirttoggle.inputs[0])
        # group_input_6.Fingerprint intensity -> aptpro_dirt_1.FINGERPRINT INTENSITY
        aperturia_fx_pro.links.new(group_input_6.outputs[35], aptpro_dirt_1.inputs[2])
        # group_input_6.Seed -> aptpro_dirt_1.SEED
        aperturia_fx_pro.links.new(group_input_6.outputs[33], aptpro_dirt_1.inputs[5])
        # group_input_6.Smudge amount -> aptpro_dirt_1.SMUDGE AMOUNT
        aperturia_fx_pro.links.new(group_input_6.outputs[36], aptpro_dirt_1.inputs[3])
        # group_input_6.Smudge intensity -> aptpro_dirt_1.SMUDGE INTENSITY
        aperturia_fx_pro.links.new(group_input_6.outputs[37], aptpro_dirt_1.inputs[4])
        # compressiontoggle.Result -> aptpro_dirt_1.Image
        aperturia_fx_pro.links.new(compressiontoggle.outputs[2], aptpro_dirt_1.inputs[0])
        # group_input_6.Advanced Shadow Mask (OPTIONAL) -> shadowmasktoggle.Factor
        aperturia_fx_pro.links.new(group_input_6.outputs[38], shadowmasktoggle.inputs[0])
        # aptpro_shadow_mask_1.Shadow Mask -> shadowmasktoggle.B
        aperturia_fx_pro.links.new(aptpro_shadow_mask_1.outputs[0], shadowmasktoggle.inputs[7])
        # imagetobw.Val -> shadowmasktoggle.A
        aperturia_fx_pro.links.new(imagetobw.outputs[0], shadowmasktoggle.inputs[6])
        # shadowmasktoggle.Result -> smandlf.B
        aperturia_fx_pro.links.new(shadowmasktoggle.outputs[2], smandlf.inputs[7])
        # glaretoggle.Result -> glaretoimage.B
        aperturia_fx_pro.links.new(glaretoggle.outputs[2], glaretoimage.inputs[7])
        # lensflarebw.Val -> glaretoggle.B
        aperturia_fx_pro.links.new(lensflarebw.outputs[0], glaretoggle.inputs[7])
        # group_input_6.Glare -> glaretoggle.Factor
        aperturia_fx_pro.links.new(group_input_6.outputs[16], glaretoggle.inputs[0])
        # group_input_6.Vignette -> vignettetoggle.Factor
        aperturia_fx_pro.links.new(group_input_6.outputs[20], vignettetoggle.inputs[0])
        # aptpro_vignette_1.Image -> vignettetoggle.B
        aperturia_fx_pro.links.new(aptpro_vignette_1.outputs[0], vignettetoggle.inputs[7])
        # vignettetoggle.Result -> glareandvig.B
        aperturia_fx_pro.links.new(vignettetoggle.outputs[2], glareandvig.inputs[7])
        # group_input_6.Pixelation Size -> aptpro_compression_effects_1.Pixelation Size
        aperturia_fx_pro.links.new(group_input_6.outputs[27], aptpro_compression_effects_1.inputs[4])
        # group_input_6.Compression softness -> aptpro_compression_effects_1.Compression softness
        aperturia_fx_pro.links.new(group_input_6.outputs[29], aptpro_compression_effects_1.inputs[5])
        # shadowmaskinv.Color -> aptpro_noise_patterns_1.Shadow Mask
        aperturia_fx_pro.links.new(shadowmaskinv.outputs[0], aptpro_noise_patterns_1.inputs[7])
        # dirttoggle.Result -> effectenabler.B
        aperturia_fx_pro.links.new(dirttoggle.outputs[2], effectenabler.inputs[7])
        # group_input_6.Image -> effectenabler.A
        aperturia_fx_pro.links.new(group_input_6.outputs[0], effectenabler.inputs[6])
        # group_input_6.ENABLED -> effectenabler.Factor
        aperturia_fx_pro.links.new(group_input_6.outputs[1], effectenabler.inputs[0])
        # group_input_6.Advanced Noise -> aptpro_noise_patterns_1.Advanced Noise
        aperturia_fx_pro.links.new(group_input_6.outputs[5], aptpro_noise_patterns_1.inputs[8])
        # reroute_002.Output -> group_output_6.Shadow Mask preview
        aperturia_fx_pro.links.new(reroute_002.outputs[0], group_output_6.inputs[1])
        # group_input_6.Shadow Mask lift -> aptpro_noise_patterns_1.Shadow Mask lift
        aperturia_fx_pro.links.new(group_input_6.outputs[13], aptpro_noise_patterns_1.inputs[9])
        # group_input_6.Shadow Mask gamma -> aptpro_noise_patterns_1.Shadow Mask gamma
        aperturia_fx_pro.links.new(group_input_6.outputs[14], aptpro_noise_patterns_1.inputs[10])
        # group_input_6.Shadow Mask gain -> aptpro_noise_patterns_1.Shadow Mask gain
        aperturia_fx_pro.links.new(group_input_6.outputs[15], aptpro_noise_patterns_1.inputs[11])
        # group_input_6.Noise scale -> aptpro_noise_patterns_1.Noise scale
        aperturia_fx_pro.links.new(group_input_6.outputs[7], aptpro_noise_patterns_1.inputs[12])
        # group_input_6.General Noise -> aptpro_noise_patterns_1.General Noise
        aperturia_fx_pro.links.new(group_input_6.outputs[3], aptpro_noise_patterns_1.inputs[13])
        # group_input_6.Diffuse Direct -> aptpro_shadow_mask_1.Diffuse Direct
        aperturia_fx_pro.links.new(group_input_6.outputs[39], aptpro_shadow_mask_1.inputs[0])
        # group_input_6.Glossy Direct -> aptpro_shadow_mask_1.Glossy Direct
        aperturia_fx_pro.links.new(group_input_6.outputs[40], aptpro_shadow_mask_1.inputs[1])
        # group_input_6.Transmission Indirect -> aptpro_shadow_mask_1.Transmission Indirect
        aperturia_fx_pro.links.new(group_input_6.outputs[41], aptpro_shadow_mask_1.inputs[2])
        # group_input_6.Volume Direct -> aptpro_shadow_mask_1.Volume Direct
        aperturia_fx_pro.links.new(group_input_6.outputs[42], aptpro_shadow_mask_1.inputs[3])
        # group_input_6.Emission -> aptpro_shadow_mask_1.Emission
        aperturia_fx_pro.links.new(group_input_6.outputs[43], aptpro_shadow_mask_1.inputs[4])
        # group_input_6.Environment -> aptpro_shadow_mask_1.Environment
        aperturia_fx_pro.links.new(group_input_6.outputs[44], aptpro_shadow_mask_1.inputs[5])
        # group_input_6.Ambient Occlusion -> aptpro_shadow_mask_1.Ambient Occlusion
        aperturia_fx_pro.links.new(group_input_6.outputs[45], aptpro_shadow_mask_1.inputs[6])
        # group_input_6.Shadow Noise amount -> aptpro_noise_patterns_1.Shadow Noise amount
        aperturia_fx_pro.links.new(group_input_6.outputs[4], aptpro_noise_patterns_1.inputs[14])
        # aptpro_noise_patterns_1.Shadow Mask preview -> reroute_001_1.Input
        aperturia_fx_pro.links.new(aptpro_noise_patterns_1.outputs[1], reroute_001_1.inputs[0])
        # reroute_001_1.Output -> reroute_002.Input
        aperturia_fx_pro.links.new(reroute_001_1.outputs[0], reroute_002.inputs[0])
        # glareandvig.Result -> imagecc.Image
        aperturia_fx_pro.links.new(glareandvig.outputs[2], imagecc.inputs[0])
        # reroute_2.Output -> aptpro_noise_patterns_1.Image
        aperturia_fx_pro.links.new(reroute_2.outputs[0], aptpro_noise_patterns_1.inputs[0])
        # reroute_2.Output -> noisetoggle.A
        aperturia_fx_pro.links.new(reroute_2.outputs[0], noisetoggle.inputs[6])
        # imagecc.Image -> reroute_2.Input
        aperturia_fx_pro.links.new(imagecc.outputs[0], reroute_2.inputs[0])
        # noisetoggle.Result -> ldmain.Image
        aperturia_fx_pro.links.new(noisetoggle.outputs[2], ldmain.inputs[0])
        # ldmain.Image -> aptpro_compression_effects_1.Image
        aperturia_fx_pro.links.new(ldmain.outputs[0], aptpro_compression_effects_1.inputs[0])
        # ldmain.Image -> compressiontoggle.A
        aperturia_fx_pro.links.new(ldmain.outputs[0], compressiontoggle.inputs[6])
        # group_input_6.Lens Distortion -> ldmain.Distortion
        aperturia_fx_pro.links.new(group_input_6.outputs[25], ldmain.inputs[1])
        # group_input_6.Lens Dispersion -> ldmain.Dispersion
        aperturia_fx_pro.links.new(group_input_6.outputs[26], ldmain.inputs[2])

        return aperturia_fx_pro

    aperturia_fx_pro = aperturia_fx_pro_node_group()
    
    return {'FINISHED'}

class APERTURIA_PRO_OT_RefreshAll(bpy.types.Operator):
    bl_idname = "aperturia.refresh_all"
    bl_label = "Restore Aperturia FX Pro"
    bl_description = "Checks and restores Aperturia FX Pro node groups and textures"

    def execute(self, context):
        restored_fx = False

        # Standard FX check
        try:
            restored_fx = check_aperturia_integrity()
        except Exception as e:
            self.report({'WARNING'}, f"FX check failed: {e}")

        if restored_fx:
            self.report({'INFO'}, "Aperturia FX Pro rebuilt.")
        else:
            self.report({'INFO'}, "All Aperturia components are already intact.")

        return {'FINISHED'}
        
def preset_items(self, context):
    presets = load_presets()
    return [(name, name, "") for name in sorted(presets.keys())]

def update_active_preset(self, context):
    if self.active_preset:
        apply_preset_to_scene_node(self.active_preset)


class AperturiaPreferences(bpy.types.PropertyGroup):
    active_preset: bpy.props.EnumProperty(
        name="Presets",
        items=preset_items,
        update=update_active_preset
    )

class APERTURIA_PRO_OT_AddPreset(bpy.types.Operator):
    bl_idname = "aperturia.add_preset"
    bl_label = "Add Preset"

    preset_name: bpy.props.StringProperty(
        name="Preset name",
        default="New Preset",
        description="Name for the preset to save"
    )

    def execute(self, context):
        values_dict = capture_node_values_from_scene()
        if not values_dict:
            self.report({'WARNING'}, "No Aperturia FX Pro group node found in this scene.")
            return {'CANCELLED'}

        presets = load_presets()
        presets[self.preset_name] = values_dict
        save_presets(presets)

        # Select the newly saved preset
        prefs = context.scene.aperturia_prefs
        prefs.active_preset = self.preset_name

        self.report({'INFO'}, f"Preset '{self.preset_name}' saved.")
        return {'FINISHED'}

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

class APERTURIA_PRO_OT_RemovePreset(bpy.types.Operator):
    bl_idname = "aperturia.remove_preset"
    bl_label = "Remove Preset"

    def execute(self, context):
        prefs = context.scene.aperturia_prefs
        active = prefs.active_preset
        presets = load_presets()
        if active in presets:
            del presets[active]
            save_presets(presets)
            # Clear selection if it no longer exists
            prefs.active_preset = ""
            self.report({'INFO'}, f"Preset '{active}' removed.")
        else:
            self.report({'WARNING'}, "No active preset to remove.")
        return {'FINISHED'}

    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event)

class APERTURIA_PRO_PT_Tools(bpy.types.Panel):
    bl_label = "Aperturia FX Pro Tools"
    bl_idname = "APERTURIA_PRO_PT_Tools"
    bl_space_type = 'NODE_EDITOR'
    bl_region_type = 'UI'
    bl_category = "Aperturia"

    def draw(self, context):
        layout = self.layout
        prefs = context.scene.aperturia_prefs

        layout.operator("aperturia.refresh_all", icon='FILE_REFRESH')

        row = layout.row()
        row.prop(prefs, "active_preset", text="")

        row = layout.row(align=True)
        row.operator("aperturia.add_preset", icon='ADD')
        row.operator("aperturia.remove_preset", icon='REMOVE')

class CompositorNodeAperturiaFXPro(bpy.types.Node):
    bl_idname = "CompositorNodeAperturiaFXPro"
    bl_label = "Quick lens effects"
    bl_icon = 'CAMERA_DATA'

    def init(self, context):
        group_name = "Aperturia FX Pro"
        if group_name in bpy.data.node_groups:
            self.node_tree = bpy.data.node_groups[group_name]

    @classmethod
    def poll(cls, context):
        return context.space_data.tree_type == "CompositorNodeTree"


# --- Node Category ---
class AperturiaFXProCategory(NodeCategory):
    @classmethod
    def poll(cls, context):
        return context.space_data.tree_type == "CompositorNodeTree"

node_categories = [
    AperturiaFXProCategory("APERTURIA_NODES", "Aperturia FX Pro", items=[
        NodeItem("CompositorNodeAperturiaFXPro"),
    ]),
]

# === REGISTER / UNREGISTER ===
classes = (
    AperturiaPreferences,
    CompositorNodeAperturiaFXPro,
    APERTURIA_PRO_OT_RefreshAll,
    APERTURIA_PRO_OT_AddPreset,
    APERTURIA_PRO_OT_RemovePreset,
    APERTURIA_PRO_PT_Tools,
)

def register():
    for cls in classes:
        bpy.utils.register_class(cls)
        
    bpy.types.Scene.aperturia_prefs = bpy.props.PointerProperty(type=AperturiaPreferences)
    from nodeitems_utils import register_node_categories
    register_node_categories("APERTURIA_FX_PRO", node_categories)

    if on_file_load not in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.append(on_file_load)

    from bpy.app.timers import register as delay
    
    def deferred_node_group_build():
        ensure_aperturia_textures(force=True)
        if "Aperturia FX Pro" in bpy.data.node_groups:
            bpy.data.node_groups.remove(bpy.data.node_groups["Aperturia FX Pro"])
        group, node_map = create_custom_node_group()
        
    delay(deferred_node_group_build, first_interval=1.0)
    
    try:
        check_aperturia_integrity()
    except Exception as e:
        print("Aperturia FX Pro integrity check failed:", e)   

def unregister():
    from nodeitems_utils import unregister_node_categories
    unregister_node_categories("APERTURIA_FX_PRO")
    del bpy.types.Scene.aperturia_prefs
    
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)

    if on_file_load in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(on_file_load)

    if "Aperturia FX Pro" in bpy.data.node_groups:
        bpy.data.node_groups.remove(bpy.data.node_groups["Aperturia FX Pro"])