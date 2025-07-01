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
    "name": "Aperturia FX Lite",
    "author": "Radikal",
    "version": (1, 0, 0),
    "blender": (4, 4, 0),
    "location": "Node Editor > Add > Compositor > Aperturia FX Lite",
    "description": "Fast lens effect node for Compositor",
    "category": "Compositing"
}

import bpy
import nodeitems_utils
from nodeitems_utils import NodeCategory, NodeItem

def on_file_load(scene):
    ensure_aperturia_textures()

    # Check if the main node group is missing or if any textures need restoring
    group_missing = "Aperturia FX Lite" not in bpy.data.node_groups
    was_restored = check_aperturia_integrity()

    # Only rebuild manually if the group is missing and integrity check didn’t already do it
    if group_missing and not was_restored:
        group, node_map = create_custom_node_group()
        if group and node_map:
            wire_custom_node_group(group, node_map)

# === TEXTURE SETUP ===

def reset_color_noise_texture():
    tex_name = "FX_ColorNoise"
    if tex_name in bpy.data.textures:
        try:
            bpy.data.textures[tex_name].type = 'DISTORTED_NOISE'
            tex = bpy.data.textures[tex_name]
        except:
            bpy.data.textures.remove(bpy.data.textures[tex_name])
            tex = bpy.data.textures.new(tex_name, type='DISTORTED_NOISE')
    else:
        tex = bpy.data.textures.new(tex_name, type='DISTORTED_NOISE')

    tex.noise_basis = 'CELL_NOISE'
    tex.noise_distortion = 'CELL_NOISE'
    tex.distortion = 5.9
    tex.noise_scale = 0.17
    tex.nabla = 0.1
    tex.use_color_ramp = True

    ramp = tex.color_ramp
    while len(ramp.elements) > 3:
        ramp.elements.remove(ramp.elements[-1])
    while len(ramp.elements) < 3:
        ramp.elements.new(0.5)

    ramp.elements[0].position = 0.0
    ramp.elements[0].color = (1, 0, 0, 1)
    ramp.elements[1].position = 0.5
    ramp.elements[1].color = (0, 1, 0, 1)
    ramp.elements[2].position = 1.0
    ramp.elements[2].color = (0, 0, 1, 1)

def ensure_aperturia_textures():
    if "FX_ColorNoise" not in bpy.data.textures or bpy.data.textures["FX_ColorNoise"].type != 'DISTORTED_NOISE':
        reset_color_noise_texture()
    if "FX_CompressionNoise" not in bpy.data.textures:
        bpy.data.textures.new(name="FX_CompressionNoise", type='NOISE')

def check_aperturia_integrity():
    restored = False

    # Color Noise
    if "FX_ColorNoise" not in bpy.data.textures or bpy.data.textures["FX_ColorNoise"].type != 'DISTORTED_NOISE':
        print("Restoring FX_ColorNoise...")
        reset_color_noise_texture()
        restored = True

    # Compression Noise
    if "FX_CompressionNoise" not in bpy.data.textures:
        print("Restoring FX_CompressionNoise...")
        bpy.data.textures.new(name="FX_CompressionNoise", type='NOISE')
        restored = True

    # Node Group
    if "Aperturia FX Lite" not in bpy.data.node_groups:
        print("Rebuilding Aperturia FX Lite node group...")
        group, node_map = create_custom_node_group()
        if group and node_map:
            wire_custom_node_group(group, node_map)
            restored = True

    return restored

# === NODE GROUP BUILDER ===
def create_custom_node_group():
    group_name = "Aperturia FX Lite"
    if group_name in bpy.data.node_groups:
        print(">>> Node group already exists. Skipping creation.")
        return None, None

    ng = bpy.data.node_groups.new(name=group_name, type='CompositorNodeTree')
    nodes = ng.nodes
    links = ng.links
    ng.use_fake_user = True

    # Interface sockets
    ng.interface.new_socket(name="Image", in_out='INPUT', socket_type='NodeSocketColor')
    ng.interface.new_socket(name="Image", in_out='OUTPUT', socket_type='NodeSocketColor')

    # Add Input/Output nodes
    input_node = nodes.new("NodeGroupInput")
    input_node.location = (-4000, 0)
    output_node = nodes.new("NodeGroupOutput")
    output_node.location = (4000, -550)

    # === NODE INITIALIZATION ===
    def new(name, bl_idname, x=0, y=0):
        n = nodes.new(type=bl_idname)
        n.name = name
        n.label = name
        n.location = (x, y)
        return n
    
    node_map = {n.name: n for n in nodes}

#--NODE SETUP FOR: BEST CAMERA QUALITY PRESET
    ellipse = new("Ellipse Mask", "CompositorNodeEllipseMask", -3300, 700)
    ellipse.mask_width = 1.0
    ellipse.mask_height = 0.75
    blur = new("Blur", "CompositorNodeBlur", -2950, 700)
    blur.filter_type = "GAUSS"
    blur.use_variable_size = True
    blur.size_x = 250
    blur.size_y = 250
    glare = new("Glare", "CompositorNodeGlare", -2950, 420)
    glare.glare_type = "BLOOM"
    glare.inputs["Threshold"].default_value = 25
    glare.inputs["Smoothness"].default_value = 1.0
    glare.inputs["Maximum"].default_value = 5.0
    glare.inputs["Size"].default_value = 1.0
    mix = new("Mix", "CompositorNodeMixRGB", -2450, 330);mix.blend_type = 'MULTIPLY'
    mix.inputs[0].default_value = 0.3

    ld = []
    ld_0 = new("Lens Distortion", "CompositorNodeLensdist", -2000, 700)
    ld_0.use_jitter = True
    ld_1 = new("Lens Distortion.001", "CompositorNodeLensdist", -1800, 500)
    ld_1.use_jitter = True
    ld_2 = new("Lens Distortion.002", "CompositorNodeLensdist", -2000, 240)
    ld_3 = new("Lens Distortion.003", "CompositorNodeLensdist", -2150, -50)
    ld_4 = new("Lens Distortion.004", "CompositorNodeLensdist", -900, 360)
    ld_4.use_fit = True
    ld_5 = new("Lens Distortion.005", "CompositorNodeLensdist", 540, 460)
    ld_5.use_jitter = True

    rgb_to_bw = new("RGB to BW", "CompositorNodeRGBToBW", -2000, -50)
    rgb_to_bw_2 = new("RGB to BW.001", "CompositorNodeRGBToBW", 760, 360)
    denoise1 = new("Denoise", "CompositorNodeDenoise", -2000, 490)
    denoise1.use_hdr = True
    denoise2 = new("Denoise.001", "CompositorNodeDenoise", -1800, 310)
    denoise2.use_hdr = True
    denoise3 = new("Denoise.002", "CompositorNodeDenoise", -1800, -40)
    denoise3.use_hdr = False
    denoise4 = new("Denoise.003", "CompositorNodeDenoise", -50, 180)

    mix_1 = new("Mix.001", "CompositorNodeMixRGB", -1600, 670); mix_1.blend_type = 'DARKEN'
    mix_1.inputs[0].default_value = 0.5
    mix_2 = new("Mix.002", "CompositorNodeMixRGB", -1300, 440)
    mix_2.inputs[0].default_value = 0.15
    mix_3 = new("Mix.003", "CompositorNodeMixRGB", -1090, 360)
    mix_4 = new("Mix.004", "CompositorNodeMixRGB", -630, 360); mix_4.blend_type = 'OVERLAY'
    mix_4.inputs[0].default_value = 0.1
    mix_5 = new("Mix.005", "CompositorNodeMixRGB", 370, 265)
    mix_5.inputs[0].default_value = 0.5
    mix_6 = new("Mix.006", "CompositorNodeMixRGB", 1060, 200); mix_6.blend_type = 'LIGHTEN'
    mix_6.inputs[0].default_value = 0.25

    cc = new("Color Correction", "CompositorNodeColorCorrection", -80, 460)
    cc.shadows_contrast = 0.9
    alpha_over = new("Alpha Over - DSLR", "CompositorNodeAlphaOver", 1880, 235); alpha_over.inputs[0].default_value = 0.002
    pixelate = new("Pixelate", "CompositorNodePixelate", 1360, 330); pixelate.pixel_size = 3

    texture_cn = new("FX_ColorNoise", "CompositorNodeTexture", -1200, 710); texture_cn.texture = bpy.data.textures.get("FX_ColorNoise")
    blur_cn = new("Blur.001", "CompositorNodeBlur", -890, 710)
    blur_cn.use_variable_size = True
    blur_cn.size_x = 3
    blur_cn.size_y = 3
    texture_comp = new("FX_CompressionNoise", "CompositorNodeTexture", 980, 570); texture_comp.texture = bpy.data.textures.get("FX_CompressionNoise")
    map_value = new("Map Value", "CompositorNodeMapValue", 700, 860)    

    node_map = {n.name: n for n in nodes}
    return ng, node_map

def wire_custom_node_group(group, node_map):
    link = group.links
    gi = node_map["Group Input"].outputs
    go = node_map["Group Output"].inputs
    
    # Connect vignette mask
    link.new(node_map["Ellipse Mask"].outputs[0], node_map["Blur"].inputs[0])
    link.new(node_map["Blur"].outputs[0], node_map["Mix"].inputs[2])
    link.new(node_map["Glare"].outputs[0], node_map["Mix"].inputs[1])
    link.new(gi["Image"], node_map["Glare"].inputs[0])

    # Pre-distort chain
    link.new(node_map["Mix"].outputs[0], node_map["Lens Distortion"].inputs[0])
    link.new(node_map["Mix"].outputs[0], node_map["Denoise"].inputs[0])
    link.new(node_map["Mix"].outputs[0], node_map["Lens Distortion.002"].inputs[0])
    link.new(node_map["Mix"].outputs[0], node_map["Lens Distortion.003"].inputs[0])
    link.new(node_map["Denoise"].outputs[0], node_map["Lens Distortion.001"].inputs[0])

    # Stack merge
    link.new(node_map["Lens Distortion"].outputs[0], node_map["Mix.001"].inputs[1])
    link.new(node_map["Lens Distortion.001"].outputs[0], node_map["Mix.001"].inputs[2])
    link.new(node_map["Lens Distortion.002"].outputs[0], node_map["Denoise.001"].inputs[0])
    link.new(node_map["Lens Distortion.003"].outputs[0], node_map["RGB to BW"].inputs[0])
    link.new(node_map["RGB to BW"].outputs[0], node_map["Denoise.002"].inputs[0])
    link.new(node_map["Denoise.001"].outputs[0], node_map["Mix.002"].inputs[1])
    link.new(node_map["Mix.001"].outputs[0], node_map["Mix.002"].inputs[2])
    link.new(node_map["Mix.002"].outputs[0], node_map["Mix.003"].inputs[1])
    link.new(node_map["Denoise.001"].outputs[0], node_map["Mix.003"].inputs[2])
    link.new(node_map["Denoise.002"].outputs[0], node_map["Mix.003"].inputs[0])

    # Post-distortion
    link.new(node_map["Mix.003"].outputs[0], node_map["Lens Distortion.004"].inputs[0])

    # Color noise overlay
    link.new(node_map["Lens Distortion.004"].outputs[0], node_map["Mix.004"].inputs[1])
    link.new(node_map["FX_ColorNoise"].outputs[1], node_map["Blur.001"].inputs[0])
    link.new(node_map["Blur.001"].outputs[0], node_map["Mix.004"].inputs[2])

    # Shadow contrast & denoise
    link.new(node_map["Mix.004"].outputs[0], node_map["Color Correction"].inputs[0])
    link.new(node_map["Mix.004"].outputs[0], node_map["Denoise.003"].inputs[0])
    link.new(node_map["Color Correction"].outputs[0], node_map["Mix.005"].inputs[1])
    link.new(node_map["Denoise.003"].outputs[0], node_map["Mix.005"].inputs[2])

    # Lighten merge
    link.new(node_map["Mix.005"].outputs[0], node_map["Lens Distortion.005"].inputs[0])
    link.new(node_map["Lens Distortion.005"].outputs[0], node_map["RGB to BW.001"].inputs[0])
    link.new(node_map["Mix.005"].outputs[0], node_map["Mix.006"].inputs[1])
    link.new(node_map["RGB to BW.001"].outputs[0], node_map["Mix.006"].inputs[2])

    # Scale and alpha composite
    link.new(node_map["Mix.006"].outputs[0], node_map["Alpha Over - DSLR"].inputs[1])
    link.new(node_map["Pixelate"].outputs[0], node_map["Alpha Over - DSLR"].inputs[2])
    link.new(node_map["Alpha Over - DSLR"].outputs[0], go["Image"])

    # Final FX texture link
    link.new(node_map["Map Value"].outputs[0], node_map["FX_CompressionNoise"].inputs[0])
    link.new(node_map["FX_CompressionNoise"].outputs[0], node_map["Pixelate"].inputs[0])
    
    # Animate mapping value
    fcurve = node_map["Map Value"].inputs[0].driver_add("default_value")
    fcurve.driver.expression = "frame"
    
# === INTEGRITY CHECK FOR LITE ===

def check_aperturia_lite_integrity():
    restored = False

    if "FXL_ColorNoise" not in bpy.data.textures or bpy.data.textures["FXL_ColorNoise"].type != 'DISTORTED_NOISE':
        # Define your texture setup here for Lite
        # Example fallback:
        tex = bpy.data.textures.new(name="FXL_ColorNoise", type='DISTORTED_NOISE')
        tex.use_color_ramp = True
        restored = True

    if "FXL_CompressionNoise" not in bpy.data.textures:
        bpy.data.textures.new(name="FXL_CompressionNoise", type='NOISE')
        restored = True

    if "Aperturia FX Lite" not in bpy.data.node_groups:
        group, node_map = create_custom_node_group()  # Lite-specific group builder
        if group and node_map:
            wire_custom_node_group(group, node_map)
            restored = True

    return restored

# === CUSTOM NODE CLASSES ===

class APERTURIA_LITE_OT_Refresh(bpy.types.Operator):
    bl_idname = "aperturia_lite.refresh_node_group"
    bl_label = "Restore Aperturia FX Lite"
    bl_description = "Checks and restores Aperturia FX Lite node group and textures"

    def execute(self, context):
        restored = check_aperturia_lite_integrity()
        if restored:
            self.report({'INFO'}, "Aperturia FX Lite was rebuilt.")
        else:
            self.report({'INFO'}, "Aperturia FX Lite is already intact.")
        return {'FINISHED'}


class APERTURIA_LITE_PT_Tools(bpy.types.Panel):
    bl_label = "Aperturia FX Lite Tools"
    bl_idname = "APERTURIA_LITE_PT_Tools"
    bl_space_type = 'NODE_EDITOR'
    bl_region_type = 'UI'
    bl_category = "Aperturia"  # Shared category

    def draw(self, context):
        layout = self.layout
        layout.operator("aperturia_lite.refresh_node_group", icon='FILE_REFRESH')


class CompositorNodeAperturiaFXLite(bpy.types.Node):
    bl_idname = "CompositorNodeAperturiaFXLite"
    bl_label = "Quick lens effects (Lite)"
    bl_icon = 'CAMERA_DATA'

    def init(self, context):
        group_name = "Aperturia FX Lite"
        if group_name in bpy.data.node_groups:
            self.node_tree = bpy.data.node_groups[group_name]

    @classmethod
    def poll(cls, context):
        return context.space_data.tree_type == "CompositorNodeTree"


class AperturiaFXLiteCategory(NodeCategory):
    @classmethod
    def poll(cls, context):
        return context.space_data.tree_type == "CompositorNodeTree"


node_categories = [
    AperturiaFXLiteCategory("APERTURIA_NODES_LITE", "Aperturia FX Lite", items=[
        NodeItem("CompositorNodeAperturiaFXLite"),
    ]),
]

# === REGISTER / UNREGISTER ===

classes = (
    CompositorNodeAperturiaFXLite,
    APERTURIA_LITE_OT_Refresh,
    APERTURIA_LITE_PT_Tools,
)

def on_file_load_lite(scene):
    check_aperturia_lite_integrity()

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

    nodeitems_utils.register_node_categories("APERTURIA_FX_LITE", node_categories)

    if on_file_load_lite not in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.append(on_file_load_lite)

    from bpy.app.timers import register as delay

    def deferred_node_group_build():
        if "Aperturia FX Lite" in bpy.data.node_groups:
            bpy.data.node_groups.remove(bpy.data.node_groups["Aperturia FX Lite"])
        group, node_map = create_custom_node_group()
        if group and node_map:
            wire_custom_node_group(group, node_map)
        return None

    delay(deferred_node_group_build, first_interval=1.0)


def unregister():
    nodeitems_utils.unregister_node_categories("APERTURIA_FX_LITE")

    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)

    if on_file_load_lite in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(on_file_load_lite)

    if "Aperturia FX Lite" in bpy.data.node_groups:
        bpy.data.node_groups.remove(bpy.data.node_groups["Aperturia FX Lite"])