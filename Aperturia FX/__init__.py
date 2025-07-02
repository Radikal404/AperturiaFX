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
    "name": "Aperturia FX",
    "author": "Radikal",
    "version": (1, 0, 1),
    "blender": (4, 4, 0),
    "location": "Node Editor > Add > Compositor > Aperturia FX",
    "description": "Fast lens effect node for Compositor",
    "category": "Compositing"
}

import bpy
import nodeitems_utils
import os
from nodeitems_utils import NodeCategory, NodeItem

addon_dir = os.path.dirname(__file__)
texture_dir = os.path.join(addon_dir, "textures")

fingerprint_textures = [
    "AperturiaFX_Fingerprints_Light.png",
    "AperturiaFX_Fingerprints_Heavy.png",
    "AperturiaFX_Smudges_Light.png",
    "AperturiaFX_Smudges_Heavy.png"
]

def on_file_load(scene):
    ensure_aperturia_textures()

    group_missing = "Aperturia FX" not in bpy.data.node_groups
    was_restored = check_aperturia_integrity()

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
        img = load_image(filename)
        if img:
            loaded[filename] = img
    return loaded

def ensure_aperturia_textures():
    if "FX_ColorNoise" not in bpy.data.textures or bpy.data.textures["FX_ColorNoise"].type != 'DISTORTED_NOISE':
        reset_color_noise_texture()
    if "FX_CompressionNoise" not in bpy.data.textures:
        bpy.data.textures.new(name="FX_CompressionNoise", type='NOISE')

    # Load fingerprint/smudge images
    bulk_load_images()

def check_aperturia_integrity():
    restored = False

    if "FX_ColorNoise" not in bpy.data.textures or bpy.data.textures["FX_ColorNoise"].type != 'DISTORTED_NOISE':
        print("Restoring FX_ColorNoise...")
        reset_color_noise_texture()
        restored = True

    if "FX_CompressionNoise" not in bpy.data.textures:
        print("Restoring FX_CompressionNoise...")
        bpy.data.textures.new(name="FX_CompressionNoise", type='NOISE')
        restored = True

    if "Aperturia FX" not in bpy.data.node_groups:
        print("Rebuilding Aperturia FX node group...")
        group, node_map = create_custom_node_group()
        if group and node_map:
            wire_custom_node_group(group, node_map)
            restored = True
            
    bulk_load_images()

    return restored

# === NODE GROUP BUILDER ===
def create_custom_node_group():
    group_name = "Aperturia FX"
    group_tag = 'FILTER'
    if group_name in bpy.data.node_groups:
        print(">>> Node group already exists. Skipping creation.")
        return None, None

    ng = bpy.data.node_groups.new(name=group_name, type='CompositorNodeTree')
    nodes = ng.nodes
    links = ng.links
    ng.use_fake_user = True

    # Interface sockets
    ng.interface.new_socket(name="Image", in_out='INPUT', socket_type='NodeSocketColor')
    
    float_inputs = [
        ("Camera Era", 0.0, 1.0, 1.0),
        ("General Noise", 0.0, 0.5, 0.25),
        ("Shadow Contrast", 0.0, 1.0, 0.25),
        ("Shadow Noise intensity", 0.0, 1.0, 0.0),
        ("Color Noise intensity", 0.0, 1.0, 0.1),
        ("Color Noise scale", 0.0, 100.0, 100.0),
        ("Compression Noise intensity", 0.0, 0.002, 0.002),
        ("Image Scale", 0.0, 1000.0, 100.0),
        ("Lens Distortion", 0.0, 0.1, 0.01),
        ("Lens Dispersion", 0.0, 0.01, 0.002),
        ("Vignette Amount", 0.0, 1.0, 0.5),
        ("Fingerprint level", 0.0, 1.0, 0.0),
        ("Fingerprint intensity", 0.0, .01, 0.0),
        ("Smudge level", 0.0, 1.0, 0.0),
        ("Smudge intensity", 0.0, .01, 0.0)
    ]
    
    for label, min_v, max_v, default_v in float_inputs:
        sock = ng.interface.new_socket(name=label, in_out='INPUT', socket_type='NodeSocketFloat')
        sock.min_value = min_v
        sock.max_value = max_v
        sock.default_value = default_v
        sock.subtype = 'FACTOR'
        
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
    mix_2 = new("Mix.002", "CompositorNodeMixRGB", -1300, 440)
    mix_3 = new("Mix.003", "CompositorNodeMixRGB", -1090, 360)
    mix_4 = new("Mix.004", "CompositorNodeMixRGB", -630, 360); mix_4.blend_type = 'OVERLAY'
    mix_5 = new("Mix.005", "CompositorNodeMixRGB", 370, 265)
    mix_6 = new("Mix.006", "CompositorNodeMixRGB", 1060, 200); mix_6.blend_type = 'LIGHTEN'

    cc = new("Color Correction", "CompositorNodeColorCorrection", -80, 460)
    cc.shadows_contrast = 0.95; cc.master_gamma = 0.7
    math_divide = new("Math", "CompositorNodeMath", -330, -545); math_divide.operation = 'DIVIDE'; math_divide.inputs[1].default_value = 100.0
    scale_rel = new("Scale", "CompositorNodeScale", 1365, 140)
    scale_render = new("Scale.001", "CompositorNodeScale", 1560, 140); scale_render.space = 'RENDER_SIZE'; scale_render.frame_method = 'STRETCH'
    alpha_over = new("Alpha Over - DSLR", "CompositorNodeAlphaOver", 1880, 235); alpha_over.inputs[0].default_value = 0.002
    pixelate = new("Pixelate", "CompositorNodePixelate", 1360, 330); pixelate.pixel_size = 3

    texture_cn = new("FX_ColorNoise", "CompositorNodeTexture", -1200, 710); texture_cn.texture = bpy.data.textures.get("FX_ColorNoise")
    blur_cn = new("Blur.001", "CompositorNodeBlur", -890, 710)
    blur_cn.use_variable_size = True
    blur_cn.size_x = 3
    blur_cn.size_y = 3
    texture_comp = new("FX_CompressionNoise", "CompositorNodeTexture", 980, 570); texture_comp.texture = bpy.data.textures.get("FX_CompressionNoise")
    map_value = new("Map Value", "CompositorNodeMapValue", 700, 860)    

#--NODE SETUP FOR: CAMCORDER / POCKET QUALITY
    ellipse2 = new("Ellipse Mask.001", "CompositorNodeEllipseMask", -4280, -1065)
    ellipse2.mask_width = 1.0
    ellipse2.mask_height = 0.75
    blur2 = new("Blur.002", "CompositorNodeBlur", -3875, -1040)
    blur2.filter_type = "GAUSS"
    blur2.use_variable_size = True
    blur2.size_x = 250
    blur2.size_y = 250
    blur3 = new("Blur.003", "CompositorNodeBlur", 615, -1420)
    blur3.filter_type = 'GAUSS'
    blur3.use_variable_size = True
    blur3.size_x = 3
    blur3.size_y = 3
    blur3.use_extended_bounds = True
    denoise21 = new("Denoise.100", "CompositorNodeDenoise", -3395, -1110)
    glare2 = new("Glare.100", "CompositorNodeGlare", -3075, -1150); glare2.glare_type = "BLOOM"; glare2.quality = 'HIGH'; glare2.inputs["Threshold"].default_value = 25; glare2.inputs["Smoothness"].default_value = 1.0; glare2.inputs["Maximum"].default_value = 50.0; glare2.inputs["Size"].default_value = 0.5; glare2.inputs["Strength"].default_value = 0.1
    ld_10 = new("Lens Distortion.100", "CompositorNodeLensdist", -2885, -1120); ld_10.use_jitter = True; ld_10.use_fit = True
    ld_11 = new("Lens Distortion.101", "CompositorNodeLensdist", -2885, -1170); ld_11.use_fit = True
    ld_12 = new("Lens Distortion.102", "CompositorNodeLensdist", -2330, -900); ld_12.use_jitter = True
    ld_13 = new("Lens Distortion.103", "CompositorNodeLensdist", -635, -875); ld_13.use_jitter = True
    mix_10 = new("Mix.100", "CompositorNodeMixRGB", -2660, -1130)
    mix_11 = new("Mix.101", "CompositorNodeMixRGB", -1725, -840); mix_11.blend_type = 'COLOR'
    mix_12 = new("Mix.102", "CompositorNodeMixRGB", -1580, -1360)
    mix_13 = new("Mix.103", "CompositorNodeMixRGB", -1110, -1180)
    mix_14 = new("Mix.104", "CompositorNodeMixRGB", -305, -845); mix_14.blend_type = 'COLOR'
    mix_15 = new("Mix.105", "CompositorNodeMixRGB", 85, -1095)
    mix_16 = new("Mix.106", "CompositorNodeMixRGB", 1355, -835); mix_16.inputs[0].default_value = 0.5
    mix_17 = new("Mix.107", "CompositorNodeMixRGB", 1530, -1140)
    mix_18 = new("Mix.108", "CompositorNodeMixRGB", 1775, -1025); mix_18.blend_type = 'LIGHTEN'
    mix_19 = new("Mix.109", "CompositorNodeMixRGB", 805, -1270); mix_19.blend_type = 'OVERLAY'
    mix_20 = new("Mix.110", "CompositorNodeMixRGB", -3605, -1050); mix_20.blend_type = 'MULTIPLY'
    rgb_to_bw_10 = new("RGB to BW.100", "CompositorNodeRGBToBW", -2345, -1490)
    rgb_to_bw_11 = new("RGB to BW.101", "CompositorNodeRGBToBW", -470, -845)
    colorramp_0 = new("Color Ramp", "CompositorNodeValToRGB", -1970, -1280)
    colorramp_0.color_ramp.interpolation = 'EASE'
    while len(colorramp_0.color_ramp.elements) < 2:
        colorramp_0.color_ramp.elements.new(0.5)
    ramp_100 = colorramp_0.color_ramp
    ramp_100.elements[0].position = 0.0; ramp_100.elements[1].position = 0.032
    ramp_100.elements[0].color = (0, 0, 0, 1); ramp_100.elements[1].color = (1, 1, 1, 1)
    colorramp_1 = new("Color Ramp.001", "CompositorNodeValToRGB", -2000, -1515)
    colorramp_1.color_ramp.interpolation = 'EASE'
    while len(colorramp_1.color_ramp.elements) < 2:
        colorramp_1.color_ramp.elements.new(0.5)
    ramp_101 = colorramp_1.color_ramp
    ramp_101.elements[0].position = 0.032; ramp_101.elements[1].position = 0.159
    ramp_101.elements[0].color = (0, 0, 0, 1); ramp_101.elements[1].color = (1, 1, 1 ,1)
    hsv_0 = new("HSV", "CompositorNodeHueSat", -2050, -790); hsv_0.inputs[2].default_value = 0.0
    hsv_1 = new("HSV.001", "CompositorNodeHueSat", -125, -1000); hsv_1.inputs[3].default_value = 1.25
    pixelate_1 = new("Pixelate.100", "CompositorNodePixelate", -830, -1110); pixelate_1.pixel_size = 2
    pixelate_2 = new("Pixelate.101", "CompositorNodePixelate", 1020, -780); pixelate_2.pixel_size = 10
    pixelate_3 = new("Pixelate.102", "CompositorNodePixelate", 1020, -900); pixelate_3.pixel_size = 5
    invert_color = new("Invert Color", "CompositorNodeInvert", -1385, -1320)
    math_divide_1 = new("Math.100", "CompositorNodeMath", 1465, -1565); math_divide_1.operation = 'DIVIDE'; math_divide_1.inputs[1].default_value = 100.0
    scale_rel_1 = new("Scale.100", "CompositorNodeScale", 2160, -1055)
    scale_render_1 = new("Scale.101", "CompositorNodeScale", 2355, -1055); scale_render_1.space = 'RENDER_SIZE'; scale_render_1.frame_method = 'STRETCH'
    cc_1 = new("Color Correction.100", "CompositorNodeColorCorrection", 1020, -1160); cc_1.highlights_lift = -0.02; cc_1.highlights_contrast = 2.0; cc_1.master_contrast = 1.005; cc_1.shadows_lift = 0.01
    texture_comp_1 = new("FX_CompressionNoise.100", "CompositorNodeTexture", 525, -855); texture_comp_1.texture = bpy.data.textures.get("FX_CompressionNoise")
    texture_cn_2 = new("FX_ColorNoise.100", "CompositorNodeTexture", 280, -1585); texture_cn_2.texture = bpy.data.textures.get("FX_ColorNoise")
    map_value_1 = new("Map Value.100", "CompositorNodeMapValue", 305, -860)
    alpha_over_1 = new("Alpha Over - Camcorder", "CompositorNodeAlphaOver", 2620, -800); alpha_over_1.inputs[0].default_value = 0.002
    
#--NODE SETUP FOR: RETRO CAMERA
    #--NODE SETUP FOR: RETRO / 70s QUALITY
    math_divide_200 = new("Math.200", "CompositorNodeMath", -4350, -2210)
    math_divide_200.operation = 'DIVIDE'
    math_divide_200.inputs[1].default_value = 100.0

    scale_200 = new("Scale.200", "CompositorNodeScale", -4080, -2170)
    scale_200.space = 'RELATIVE'

    blur_200 = new("Blur.200", "CompositorNodeBlur", -3910, -2075)
    blur_200.filter_type = 'GAUSS'
    blur_200.use_variable_size = True
    blur_200.use_extended_bounds = True
    blur_200.size_x = 3
    blur_200.size_y = 3

    ellipse_200 = new("Ellipse Mask.200", "CompositorNodeEllipseMask", -4400, -2400)
    ellipse_200.mask_width = 1.0
    ellipse_200.mask_height = 0.75

    blur_201 = new("Blur.201", "CompositorNodeBlur", -3990, -2370)
    blur_201.filter_type = "GAUSS"
    blur_201.use_variable_size = True
    blur_201.use_extended_bounds = True
    blur_201.size_x = 250
    blur_201.size_y = 250

    mix_200 = new("Mix.200", "CompositorNodeMixRGB", -3595, -2335)
    mix_200.blend_type = 'MULTIPLY'

    ld_200 = new("Lens Distortion.200", "CompositorNodeLensdist", -3385, -2300)
    ld_200.use_jitter = True

    denoise_200 = new("Denoise.200", "CompositorNodeDenoise", -3200, -2340)

    glare_200 = new("Glare.200", "CompositorNodeGlare", -3020, -2330)
    glare_200.glare_type = "BLOOM"
    glare_200.quality = 'HIGH'
    glare_200.inputs["Threshold"].default_value = 25.0
    glare_200.inputs["Smoothness"].default_value = 1.0
    glare_200.inputs["Maximum"].default_value = 50.0
    glare_200.inputs["Size"].default_value = 1.0
    glare_200.inputs["Strength"].default_value = 0.1
    
    exposure_200 = new("Exposure.200", "CompositorNodeExposure", -2850, -2375)
    exposure_200.inputs["Exposure"].default_value = -0.1

    cc_200 = new("Color Correction.200", "CompositorNodeColorCorrection", -2685, -2375)
    cc_200.master_contrast = 1.1
    cc_200.highlights_contrast = 1.2
    cc_200.highlights_gain = 1.05
    cc_200.highlights_lift = 0.05
    cc_200.shadows_saturation = 0.8
    cc_200.shadows_contrast = 0.85
    cc_200.shadows_gamma = 0.95

    cb_200 = new("Color Balance.200", "CompositorNodeColorBalance", -2080, -2275)
    cb_200.lift = (1, 1, 1); cb_200.gamma = (1.07, 1.07, 1.07); cb_200.gain = (1.3, 1.073, 0.96)

    ld_201 = new("Lens Distortion.201", "CompositorNodeLensdist", -2240, -2555)
    ld_201.use_jitter = True

    rgb_to_bw_200 = new("RGB to BW.200", "CompositorNodeRGBToBW", -2080, -2555)

    colorramp_200 = new("Color Ramp.200", "CompositorNodeValToRGB", -1880, -2650)
    colorramp_200.color_ramp.interpolation = 'EASE'
    while len(colorramp_200.color_ramp.elements) < 2:
        colorramp_200.color_ramp.elements.new(0.5)
    ramp_200 = colorramp_200.color_ramp
    ramp_200.elements[0].position = 0.0; ramp_200.elements[1].position = 0.45
    ramp_200.elements[0].color = (0, 0, 0, 1); ramp_200.elements[1].color = (1, 1, 1 ,1)
    
    mix_201 = new("Mix.201", "CompositorNodeMixRGB", -1585, -2510)

    color_noise_mix_200 = new("ColorNoiseIntensity.200", "CompositorNodeMixRGB", -1365, -2300)

    math_multiply_200 = new("Multiply.200", "CompositorNodeMath", -1370, -2490)
    math_multiply_200.operation = 'MULTIPLY'
    math_multiply_200.inputs[1].default_value = 1.0
    math_multiply_200.use_clamp = True
    
    mix_207 = new("Mix.207", "CompositorNodeMixRGB", -1110, -2140)
    
    shadow_noise_intensity = new("Mix.202", "CompositorNodeMixRGB", -880, -2140)
    shadow_noise_intensity.blend_type = 'MULTIPLY'

    shadow_noise_mix_200 = new("Mix.203", "CompositorNodeMixRGB", -565, -2290)

    ld_202 = new("Lens Distortion.202", "CompositorNodeLensdist", -290, -2290)
    ld_202.use_fit = True
    ld_203 = new("Lens Distortion.203", "CompositorNodeLensdist", -520, -2525)
    ld_203.use_fit = True

    blur_202 = new("Blur.202", "CompositorNodeBlur", -30, -2495)
    blur_202.filter_type = 'GAUSS'
    blur_202.use_variable_size = True
    blur_202.use_extended_bounds = True
    blur_202.size_x = 3
    blur_202.size_y = 3

    texture_200 = new("FX_ColorNoise.200", "CompositorNodeTexture", -340, -2585)
    texture_200.texture = bpy.data.textures.get("FX_ColorNoise")

    mix_overlay_200 = new("Mix.204", "CompositorNodeMixRGB", 260, -2330)
    mix_overlay_200.blend_type = 'OVERLAY'
    
    map_value_200 = new("Map Value.200", "CompositorNodeMapValue", 260, -2550)

    texture_compression_200 = new("FX_CompressionNoise.200", "CompositorNodeTexture", 440, -2460)
    texture_compression_200.texture = bpy.data.textures.get("Aperturia-CompressionNoise")
    
    mix_lighten_200 = new("Mix.205", "CompositorNodeMixRGB", 860, -2210)
    mix_lighten_200.blend_type = 'LIGHTEN'
    mix_206 = new("Mix.206", "CompositorNodeMixRGB", 1260, -2410)
    mix_206.inputs[0].default_value = 0.1
    
    alpha_over_201 = new("Alpha Over - Retro", "CompositorNodeAlphaOver", 1500, -2200)
    alpha_over_201.inputs[0].default_value = 0.002
    
    scale_render_200 = new("Scale.201", "CompositorNodeScale", 1680, -2195)
    scale_render_200.space = 'RENDER_SIZE'
    scale_render_200.frame_method = 'STRETCH'

    pixelate_200 = new("Pixelate.200", "CompositorNodePixelate", 850, -2550)
    pixelate_200.pixel_size = 50  # Image shows large block size for pixelation
    
    blur_204 = new("Blur.204", "CompositorNodeBlur", 1020, -2570)
    blur_204.filter_type = 'GAUSS'
    blur_204.use_variable_size = True
    blur_204.use_extended_bounds = True
    blur_204.size_x = 50
    blur_204.size_y = 50

    # === DSLR Smoothstep Fake ===
    pres1_sub = new("Pres1_Sub", "CompositorNodeMath", 2285, 265); pres1_sub.operation = 'SUBTRACT'; pres1_sub.inputs[1].default_value = 0.4
    pres1_div = new("Pres1_Div", "CompositorNodeMath", 2435, 265); pres1_div.operation = 'DIVIDE'; pres1_div.inputs[1].default_value = 0.6
    pres1_div.use_clamp = True

    pres1_2t = new("Pres1_2t", "CompositorNodeMath", 2585, 225); pres1_2t.operation = 'MULTIPLY'; pres1_2t.inputs[1].default_value = 2.0
    # === Camcorder Blend Curve ===
    pres2_sub = new("Pres2_Subt", "CompositorNodeMath", 2720, -665); pres2_sub.operation = 'SUBTRACT'; pres2_sub.inputs[1].default_value = 0.5
    pres2_abs = new("Pres2_Abs", "CompositorNodeMath", 2890, -665); pres2_abs.operation = 'ABSOLUTE'
    pres2_mult = new("Pres2_Mult", "CompositorNodeMath", 3050, -665); pres2_mult.operation = 'MULTIPLY'; pres2_mult.inputs[1].default_value = 0.75
    pres2_inv = new("Pres2_Inv", "CompositorNodeMath", 3200, -665); pres2_inv.operation = 'SUBTRACT'; pres2_inv.inputs[0].default_value = 1.0
    pres2_inv.use_clamp = True
    # === Retro Smoothstep Fake ===
    pres3_sub0 = new("Pres3_Sub0", "CompositorNodeMath", 2675, -1245)
    pres3_sub0.operation = 'SUBTRACT'
    pres3_sub0.inputs[1].default_value = 0.0  # retro start range

    pres3_div = new("Pres3_Div", "CompositorNodeMath", 2825, -1245)
    pres3_div.operation = 'DIVIDE'
    pres3_div.inputs[1].default_value = 0.45    # (0.35 - 0.15) transition width
    pres3_div.use_clamp = True

    pres3_t2 = new("Pres3_T2", "CompositorNodeMath", 2975, -1205)
    pres3_t2.operation = 'MULTIPLY'

    pres3_2t = new("Pres3_2t", "CompositorNodeMath", 2975, -1285)
    pres3_2t.operation = 'MULTIPLY'
    pres3_2t.inputs[1].default_value = 2.0

    pres3_curve = new("Pres3_3minus2t", "CompositorNodeMath", 3125, -1285)
    pres3_curve.operation = 'SUBTRACT'
    pres3_curve.inputs[0].default_value = 3.0

    pres3_smooth = new("Pres3_Smooth", "CompositorNodeMath", 3275, -1245)
    pres3_smooth.operation = 'MULTIPLY'
    
    pres3_lessthan = new("Pres3_LessThan", "CompositorNodeMath", 3575, -1320)
    pres3_lessthan.operation = 'LESS_THAN'
    pres3_lessthan.inputs[1].default_value = 0.4  # Cut off Retro after 0.4
    pres3_lessthan.use_clamp = True

    pres3_masked = new("Pres3_Weight", "CompositorNodeMath", 3725, -1245)
    pres3_masked.operation = 'MULTIPLY'
    pres3_masked.use_clamp = True

    pres3_invert = new("Pres3_Subt", "CompositorNodeMath", 3425, -1245)
    pres3_invert.operation = 'SUBTRACT'
    pres3_invert.inputs[0].default_value = 1.0
    pres3_invert.use_clamp = True

    # Retro Multiply Node
    pres3_rgbmult = new("Pres3_RGB_Mult", "CompositorNodeMixRGB", 3575, -1245)
    pres3_rgbmult.blend_type = 'MULTIPLY'
    pres3_rgbmult.use_clamp = True
    
    dslr_set_alpha = new("DSLR_SetAlpha", "CompositorNodeSetAlpha", 3680, 260)
    cam_set_alpha  = new("Cam_SetAlpha", "CompositorNodeSetAlpha", 3460, -680)
    
    # === Camera Mixing nodes ===
    alpha1 = new("CamStack_1", "CompositorNodeAlphaOver", 3630, -650)
    alpha2 = new("CamStack_2", "CompositorNodeAlphaOver", 3845, -510)
    
    # === Fingerprints and Smudges ===
    finger_light = new("Fingerprints_Light", "CompositorNodeImage", 4000, -235)
    finger_light.image = bpy.data.images.get("AperturiaFX_Fingerprints_Light.png")
    finger_heavy = new("Fingerprints_Heavy", "CompositorNodeImage", 4020, 10)
    finger_heavy.image = bpy.data.images.get("AperturiaFX_Fingerprints_Heavy.png")
    
    smudge_light = new("Smudge_Light", "CompositorNodeImage", 4675, -80)
    smudge_light.image = bpy.data.images.get("AperturiaFX_Smudges_Light.png")
    smudge_heavy = new("Smudge_Heavy", "CompositorNodeImage", 4830, 15)
    smudge_heavy.image = bpy.data.images.get("AperturiaFX_Smudges_Heavy.png")
    
    finger_light_scaler = new("FinLightScale", "CompositorNodeScale", 4290, -255)
    finger_light_scaler.space = 'RENDER_SIZE'
    finger_light_scaler.frame_method = 'CROP'
    
    finger_heavy_scaler = new("FinHeavyScale", "CompositorNodeScale", 4290, -30)
    finger_heavy_scaler.space = 'RENDER_SIZE'
    finger_heavy_scaler.frame_method = 'CROP'
    
    smudge_light_scaler = new("SmuLightScale", "CompositorNodeScale", 4925, -225)
    smudge_light_scaler.space = 'RENDER_SIZE'
    smudge_light_scaler.frame_method = 'CROP'
    
    smudge_heavy_scaler = new("SmuHeavyScale", "CompositorNodeScale", 5050, -20)
    smudge_heavy_scaler.space = 'RENDER_SIZE'
    smudge_heavy_scaler.frame_method = 'CROP'
    
    finger_leveler = new("FingerLeveler", "CompositorNodeMixRGB", 4560, -320)
    finger_leveler.blend_type = 'ADD'
    
    smudge_leveler = new("SmudgeLeveler", "CompositorNodeMixRGB", 5275, -255)
    smudge_leveler.blend_type = 'ADD'
    
    finger_intensity = new("FingerIntensity", "CompositorNodeMixRGB", 4740, -475)
    finger_intensity.blend_type = 'ADD'
    
    smudge_intensity = new("SmudgeIntensity", "CompositorNodeMixRGB", 5520, -440)
    smudge_intensity.blend_type = 'ADD'

    node_map = {n.name: n for n in nodes}
    return ng, node_map

def wire_custom_node_group(group, node_map):
    link = group.links
    gi = node_map["Group Input"].outputs
    go = node_map["Group Output"].inputs
#-- High Quality Camera wiring
    # Connect vignette mask
    link.new(node_map["Ellipse Mask"].outputs[0], node_map["Blur"].inputs[0])
    link.new(node_map["Blur"].outputs[0], node_map["Mix"].inputs[2])
    link.new(gi["Image"], node_map["Glare"].inputs[0])
    link.new(node_map["Glare"].outputs[0], node_map["Mix"].inputs[1])
    link.new(gi["Vignette Amount"], node_map["Mix"].inputs[0])

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
    link.new(gi["Shadow Noise intensity"], node_map["Mix.002"].inputs[0])
    link.new(node_map["Mix.002"].outputs[0], node_map["Mix.003"].inputs[1])
    link.new(node_map["Denoise.001"].outputs[0], node_map["Mix.003"].inputs[2])
    link.new(node_map["Denoise.002"].outputs[0], node_map["Mix.003"].inputs[0])

    # Post-distortion
    link.new(node_map["Mix.003"].outputs[0], node_map["Lens Distortion.004"].inputs[0])
    link.new(gi["Lens Distortion"], node_map["Lens Distortion.004"].inputs[1])
    link.new(gi["Lens Dispersion"], node_map["Lens Distortion.004"].inputs[2])

    # Color noise overlay
    link.new(node_map["Lens Distortion.004"].outputs[0], node_map["Mix.004"].inputs[1])
    link.new(gi["Color Noise intensity"], node_map["Mix.004"].inputs[0])
    link.new(gi["Color Noise scale"], node_map["FX_ColorNoise"].inputs[1])
    link.new(node_map["FX_ColorNoise"].outputs[1], node_map["Blur.001"].inputs[0])
    link.new(node_map["Blur.001"].outputs[0], node_map["Mix.004"].inputs[2])

    # Shadow contrast & denoise
    link.new(node_map["Mix.004"].outputs[0], node_map["Color Correction"].inputs[0])
    link.new(node_map["Mix.004"].outputs[0], node_map["Denoise.003"].inputs[0])
    link.new(node_map["Color Correction"].outputs[0], node_map["Mix.005"].inputs[1])
    link.new(node_map["Denoise.003"].outputs[0], node_map["Mix.005"].inputs[2])
    link.new(gi["Shadow Contrast"], node_map["Mix.005"].inputs[0])

    # Lighten merge
    link.new(node_map["Mix.005"].outputs[0], node_map["Lens Distortion.005"].inputs[0])
    link.new(node_map["Lens Distortion.005"].outputs[0], node_map["RGB to BW.001"].inputs[0])
    link.new(node_map["Mix.005"].outputs[0], node_map["Mix.006"].inputs[1])
    link.new(node_map["RGB to BW.001"].outputs[0], node_map["Mix.006"].inputs[2])
    link.new(gi["General Noise"], node_map["Mix.006"].inputs[0])

    # Scale and alpha composite
    link.new(node_map["Mix.006"].outputs[0], node_map["Scale"].inputs[0])
    link.new(gi["Image Scale"], node_map["Math"].inputs[0])
    link.new(node_map["Math"].outputs[0], node_map["Scale"].inputs[1])
    link.new(node_map["Math"].outputs[0], node_map["Scale"].inputs[2])
    link.new(node_map["Scale"].outputs[0], node_map["Scale.001"].inputs[0])
    link.new(node_map["Scale.001"].outputs[0], node_map["Alpha Over - DSLR"].inputs[1])
    link.new(node_map["Pixelate"].outputs[0], node_map["Alpha Over - DSLR"].inputs[2])

    # Final FX texture link
    link.new(node_map["Map Value"].outputs[0], node_map["FX_CompressionNoise"].inputs[0])
    link.new(gi["Compression Noise intensity"], node_map["Alpha Over - DSLR"].inputs[0])
    link.new(node_map["FX_CompressionNoise"].outputs[0], node_map["Pixelate"].inputs[0])
    
#--Camcorder / Pocket camera wiring
    link.new(gi["Image"], node_map["Mix.110"].inputs[1])
    link.new(gi["Vignette Amount"], node_map["Mix.110"].inputs[0])
    link.new(node_map["Ellipse Mask.001"].outputs[0], node_map["Blur.002"].inputs[0])
    link.new(node_map["Blur.002"].outputs[0], node_map["Mix.110"].inputs[2])
    link.new(node_map["Mix.110"].outputs[0], node_map["Denoise.100"].inputs[0])
    link.new(node_map["Denoise.100"].outputs[0], node_map["Glare.100"].inputs[0])
    link.new(node_map["Glare.100"].outputs[0], node_map["Lens Distortion.100"].inputs[0])
    link.new(node_map["Glare.100"].outputs[0], node_map["Lens Distortion.101"].inputs[0])
    link.new(node_map["Lens Distortion.100"].outputs[0], node_map["Mix.100"].inputs[2])
    link.new(node_map["Lens Distortion.101"].outputs[0], node_map["Mix.100"].inputs[1])
    link.new(gi["Color Noise intensity"], node_map["Mix.100"].inputs[0])
    link.new(gi["Lens Distortion"], node_map["Lens Distortion.100"].inputs[1])
    link.new(gi["Lens Dispersion"], node_map["Lens Distortion.100"].inputs[2])
    link.new(gi["Lens Distortion"], node_map["Lens Distortion.101"].inputs[1])
    link.new(gi["Lens Dispersion"], node_map["Lens Distortion.101"].inputs[2])
    
    link.new(node_map["Mix.100"].outputs[0], node_map["Lens Distortion.102"].inputs[0])
    link.new(node_map["Lens Distortion.102"].outputs[0], node_map["HSV"].inputs[0])
    link.new(node_map["HSV"].outputs[0], node_map["Mix.101"].inputs[1])
    link.new(node_map["Mix.100"].outputs[0], node_map["Mix.101"].inputs[2])
    link.new(node_map["Mix.100"].outputs[0], node_map["RGB to BW.100"].inputs[0])
    link.new(node_map["RGB to BW.100"].outputs[0], node_map["Color Ramp"].inputs[0])
    link.new(node_map["RGB to BW.100"].outputs[0], node_map["Color Ramp.001"].inputs[0])
    link.new(node_map["Color Ramp"].outputs[0], node_map["Mix.102"].inputs[1])
    link.new(node_map["Color Ramp.001"].outputs[0], node_map["Mix.102"].inputs[2])
    link.new(gi["Shadow Noise intensity"], node_map["Mix.102"].inputs[0])
    link.new(node_map["Mix.102"].outputs[0], node_map["Invert Color"].inputs[1])
    link.new(node_map["Mix.101"].outputs[0], node_map["Mix.103"].inputs[2])
    link.new(node_map["Invert Color"].outputs[0], node_map["Mix.103"].inputs[0])
    link.new(node_map["Mix.100"].outputs[0], node_map["Mix.103"].inputs[1])
    
    link.new(node_map["Mix.103"].outputs[0], node_map["Pixelate.100"].inputs[0])
    link.new(node_map["Pixelate.100"].outputs[0], node_map["Lens Distortion.103"].inputs[0])
    link.new(node_map["Lens Distortion.103"].outputs[0], node_map["RGB to BW.101"].inputs[0])
    link.new(node_map["RGB to BW.101"].outputs[0], node_map["Mix.104"].inputs[1])
    link.new(node_map["Pixelate.100"].outputs[0], node_map["Mix.104"].inputs[2])
    link.new(node_map["RGB to BW.101"].outputs[0], node_map["Mix.108"].inputs[2])
    link.new(node_map["Mix.104"].outputs[0], node_map["HSV.001"].inputs[0])
    link.new(node_map["HSV.001"].outputs[0], node_map["Mix.105"].inputs[2])
    link.new(node_map["Mix.103"].outputs[0], node_map["Mix.105"].inputs[1])
    link.new(gi["General Noise"], node_map["Mix.105"].inputs[0])
    
    link.new(gi["Color Noise scale"], node_map["FX_ColorNoise.100"].inputs[1])
    link.new(node_map["FX_ColorNoise.100"].outputs[1], node_map["Blur.003"].inputs[0])
    link.new(gi["Color Noise intensity"], node_map["Mix.109"].inputs[0])
    link.new(node_map["Mix.105"].outputs[0], node_map["Mix.109"].inputs[1])
    link.new(node_map["Blur.003"].outputs[0], node_map["Mix.109"].inputs[2])
    link.new(node_map["Mix.109"].outputs[0], node_map["Color Correction.100"].inputs[0])
    link.new(node_map["Mix.109"].outputs[0], node_map["Mix.107"].inputs[2])
    link.new(node_map["Color Correction.100"].outputs[0], node_map["Mix.107"].inputs[1])
    link.new(gi["Shadow Contrast"], node_map["Mix.107"].inputs[0])
    
    link.new(gi["Image Scale"], node_map["Math.100"].inputs[0])
    link.new(node_map["Math.100"].outputs[0], node_map["Scale.100"].inputs[1])
    link.new(node_map["Math.100"].outputs[0], node_map["Scale.100"].inputs[2])
    link.new(node_map["Mix.108"].outputs[0], node_map["Scale.100"].inputs[0])
    link.new(node_map["Mix.107"].outputs[0], node_map["Mix.108"].inputs[1])
    link.new(gi["General Noise"], node_map["Mix.108"].inputs[0])
    link.new(node_map["Scale.100"].outputs[0], node_map["Scale.101"].inputs[0])
    
    link.new(node_map["Map Value.100"].outputs[0], node_map["FX_CompressionNoise.100"].inputs[0])
    link.new(node_map["FX_CompressionNoise.100"].outputs[0], node_map["Pixelate.101"].inputs[0])
    link.new(node_map["FX_CompressionNoise.100"].outputs[0], node_map["Pixelate.102"].inputs[0])
    link.new(node_map["Pixelate.101"].outputs[0], node_map["Mix.106"].inputs[1])
    link.new(node_map["Pixelate.102"].outputs[0], node_map["Mix.106"].inputs[2])
    link.new(node_map["Mix.106"].outputs[0], node_map["Alpha Over - Camcorder"].inputs[2])
    link.new(node_map["Scale.101"].outputs[0], node_map["Alpha Over - Camcorder"].inputs[1])
    
    link.new(gi["Compression Noise intensity"], node_map["Alpha Over - Camcorder"].inputs[0])
    
#--Retro cam wiring
    link.new(gi["Image"], node_map["Blur.200"].inputs[0])
    link.new(gi["Image Scale"], node_map["Math.200"].inputs[0])
    link.new(node_map["Math.200"].outputs[0], node_map["Scale.200"].inputs[1])
    link.new(node_map["Math.200"].outputs[0], node_map["Scale.200"].inputs[2])
    link.new(node_map["Scale.200"].outputs[0], node_map["Scale.201"].inputs[0])
    link.new(node_map["Ellipse Mask.200"].outputs[0], node_map["Blur.201"].inputs[0])
    link.new(gi["Vignette Amount"], node_map["Mix.200"].inputs[0])
    link.new(node_map["Blur.200"].outputs[0], node_map["Mix.200"].inputs[1])
    link.new(node_map["Blur.201"].outputs[0], node_map["Mix.200"].inputs[2])
    
    link.new(node_map["Mix.200"].outputs[0], node_map["Lens Distortion.200"].inputs[0])
    link.new(node_map["Lens Distortion.200"].outputs[0], node_map["Denoise.200"].inputs[0])
    link.new(node_map["Denoise.200"].outputs[0], node_map["Glare.200"].inputs[0])
    link.new(node_map["Glare.200"].outputs[0], node_map["Exposure.200"].inputs[0])
    link.new(node_map["Exposure.200"].outputs[0], node_map["Color Correction.200"].inputs[0])
    
    link.new(node_map["Color Correction.200"].outputs[0], node_map["Color Balance.200"].inputs[1])
    link.new(node_map["Color Correction.200"].outputs[0], node_map["Lens Distortion.201"].inputs[0])
    link.new(node_map["Color Correction.200"].outputs[0], node_map["ColorNoiseIntensity.200"].inputs[2])
    
    link.new(node_map["Lens Distortion.201"].outputs[0], node_map["RGB to BW.200"].inputs[0])
    link.new(node_map["RGB to BW.200"].outputs[0], node_map["Color Ramp.200"].inputs[0])
    link.new(node_map["RGB to BW.200"].outputs[0], node_map["Mix.201"].inputs[2])
    link.new(node_map["Color Ramp.200"].outputs[0], node_map["Mix.201"].inputs[1])
    link.new(gi["Shadow Contrast"], node_map["Mix.201"].inputs[0])
    
    link.new(node_map["Mix.201"].outputs[0], node_map["Multiply.200"].inputs[0])
    link.new(gi["Color Noise intensity"], node_map["ColorNoiseIntensity.200"].inputs[0])
    link.new(node_map["Color Balance.200"].outputs[0], node_map["ColorNoiseIntensity.200"].inputs[1])
    link.new(node_map["Color Balance.200"].outputs[0], node_map["Mix.207"].inputs[2])
    link.new(node_map["Color Balance.200"].outputs[0], node_map["Mix.203"].inputs[2])
    link.new(node_map["ColorNoiseIntensity.200"].outputs[0], node_map["Mix.207"].inputs[1])
    link.new(node_map["Multiply.200"].outputs[0], node_map["Mix.207"].inputs[0])
    
    link.new(node_map["Mix.207"].outputs[0], node_map["Mix.202"].inputs[1])
    link.new(node_map["Multiply.200"].outputs[0], node_map["Mix.202"].inputs[2])
    link.new(gi["Shadow Noise intensity"], node_map["Mix.202"].inputs[0])
    
    link.new(node_map["Mix.202"].outputs[0], node_map["Mix.203"].inputs[1])
    link.new(node_map["Multiply.200"].outputs[0], node_map["Mix.203"].inputs[0])
    
    link.new(node_map["Multiply.200"].outputs[0], node_map["Lens Distortion.203"].inputs[0])
    link.new(gi["Lens Distortion"], node_map["Lens Distortion.203"].inputs[1])
    link.new(gi["Lens Distortion"], node_map["Lens Distortion.202"].inputs[1])
    link.new(node_map["Mix.203"].outputs[0], node_map["Lens Distortion.202"].inputs[0])
    link.new(gi["Lens Dispersion"], node_map["Lens Distortion.203"].inputs[2])
    link.new(gi["Lens Dispersion"], node_map["Lens Distortion.202"].inputs[2])
    
    link.new(node_map["Lens Distortion.202"].outputs[0], node_map["Mix.204"].inputs[1])
    link.new(gi["Color Noise scale"], node_map["FX_ColorNoise.200"].inputs[1])
    link.new(node_map["FX_ColorNoise.200"].outputs[1], node_map["Blur.202"].inputs[0])
    link.new(node_map["Blur.202"].outputs[0], node_map["Mix.204"].inputs[2])
    link.new(gi["Color Noise intensity"], node_map["Mix.204"].inputs[0])
    
    link.new(gi["General Noise"], node_map["Mix.205"].inputs[0])
    link.new(node_map["Mix.204"].outputs[0], node_map["Mix.205"].inputs[1])
    link.new(node_map["Lens Distortion.203"].outputs[0], node_map["Mix.205"].inputs[2])
    
    link.new(node_map["Map Value.200"].outputs[0], node_map["FX_CompressionNoise.200"].inputs[1])
    link.new(node_map["FX_CompressionNoise.200"].outputs[0], node_map["Pixelate.200"].inputs[0])
    link.new(node_map["FX_CompressionNoise.200"].outputs[0], node_map["Mix.206"].inputs[2])
    link.new(node_map["Pixelate.200"].outputs[0], node_map["Blur.204"].inputs[0])
    link.new(node_map["Blur.204"].outputs[0], node_map["Mix.206"].inputs[1])
    
    link.new(node_map["Mix.205"].outputs[0], node_map["Alpha Over - Retro"].inputs[1])
    link.new(node_map["Mix.206"].outputs[0], node_map["Alpha Over - Retro"].inputs[2])
    
    link.new(node_map["Alpha Over - Retro"].outputs[0], node_map["Scale.200"].inputs[0])
    link.new(gi["Compression Noise intensity"], node_map["Alpha Over - Retro"].inputs[0])
    
    # === DSLR Preset Weight ===
    link.new(gi["Camera Era"], node_map["Pres1_Sub"].inputs[0])
    link.new(node_map["Pres1_Sub"].outputs[0], node_map["Pres1_Div"].inputs[0])
    link.new(node_map["Pres1_Div"].outputs[0], node_map["Pres1_2t"].inputs[0])

    # === Camcorder Preset Weight ===
    link.new(gi["Camera Era"], node_map["Pres2_Subt"].inputs[0])
    link.new(node_map["Pres2_Subt"].outputs[0], node_map["Pres2_Abs"].inputs[0])
    link.new(node_map["Pres2_Abs"].outputs[0], node_map["Pres2_Mult"].inputs[0])
    link.new(node_map["Pres2_Mult"].outputs[0], node_map["Pres2_Inv"].inputs[1])

    # === Retro Preset Weight ===
    link.new(gi["Camera Era"], node_map["Pres3_Sub0"].inputs[0])
    link.new(node_map["Pres3_Sub0"].outputs[0], node_map["Pres3_Div"].inputs[0])
    link.new(node_map["Pres3_Div"].outputs[0], node_map["Pres3_T2"].inputs[0])
    link.new(node_map["Pres3_Div"].outputs[0], node_map["Pres3_2t"].inputs[0])
    link.new(node_map["Pres3_2t"].outputs[0], node_map["Pres3_3minus2t"].inputs[1])
    link.new(node_map["Pres3_T2"].outputs[0], node_map["Pres3_Smooth"].inputs[0])
    link.new(node_map["Pres3_3minus2t"].outputs[0], node_map["Pres3_Smooth"].inputs[1])
    link.new(node_map["Pres3_Smooth"].outputs[0], node_map["Pres3_Subt"].inputs[1])

    # === Retro Final Mask Gate (LESS_THAN limiter)
    link.new(gi["Camera Era"], node_map["Pres3_LessThan"].inputs[0])
    link.new(node_map["Pres3_Subt"].outputs[0], node_map["Pres3_Weight"].inputs[0])
    link.new(node_map["Pres3_LessThan"].outputs[0], node_map["Pres3_Weight"].inputs[1])

    # === Retro RGB Multiply
    link.new(node_map["Pres3_Weight"].outputs[0], node_map["Pres3_RGB_Mult"].inputs[1])
    link.new(node_map["Scale.201"].outputs[0], node_map["Pres3_RGB_Mult"].inputs[2])

    # === Final AlphaOver Stack ===
    # Stack 1: Camcorder over Retro
    link.new(node_map["Pres3_RGB_Mult"].outputs[0], node_map["CamStack_1"].inputs[1])
    link.new(node_map["Alpha Over - Camcorder"].outputs[0], node_map["Cam_SetAlpha"].inputs[0])
    link.new(node_map["Pres2_Inv"].outputs[0], node_map["Cam_SetAlpha"].inputs[1])

    # Stack 2: DSLR over previous
    link.new(node_map["CamStack_1"].outputs[0], node_map["CamStack_2"].inputs[1])
    link.new(node_map["Alpha Over - DSLR"].outputs[0], node_map["DSLR_SetAlpha"].inputs[0])
    link.new(node_map["Pres1_2t"].outputs[0], node_map["DSLR_SetAlpha"].inputs[1])  

    # Final Output
    link.new(node_map["Cam_SetAlpha"].outputs[0], node_map["CamStack_1"].inputs[2])
    link.new(node_map["DSLR_SetAlpha"].outputs[0], node_map["CamStack_2"].inputs[2])
    
    # Fingerprints and Smudges
    link.new(node_map["Fingerprints_Light"].outputs[0], node_map["FinLightScale"].inputs[0])
    link.new(node_map["Fingerprints_Heavy"].outputs[0], node_map["FinHeavyScale"].inputs[0])
    link.new(node_map["Smudge_Light"].outputs[0], node_map["SmuLightScale"].inputs[0])
    link.new(node_map["Smudge_Heavy"].outputs[0], node_map["SmuHeavyScale"].inputs[0])
    
    link.new(gi["Fingerprint level"], node_map["FingerLeveler"].inputs[0])
    link.new(gi["Smudge level"], node_map["SmudgeLeveler"].inputs[0])
    
    link.new(node_map["FinLightScale"].outputs[0], node_map["FingerLeveler"].inputs[1])
    link.new(node_map["FinHeavyScale"].outputs[0], node_map["FingerLeveler"].inputs[2])
    link.new(node_map["SmuLightScale"].outputs[0], node_map["SmudgeLeveler"].inputs[1])
    link.new(node_map["SmuHeavyScale"].outputs[0], node_map["SmudgeLeveler"].inputs[2])
    
    link.new(gi["Fingerprint intensity"], node_map["FingerIntensity"].inputs[0])
    link.new(node_map["CamStack_2"].outputs[0], node_map["FingerIntensity"].inputs[1])
    link.new(node_map["FingerLeveler"].outputs[0], node_map["FingerIntensity"].inputs[2])
    
    link.new(gi["Smudge intensity"], node_map["SmudgeIntensity"].inputs[0])
    link.new(node_map["FingerIntensity"].outputs[0], node_map["SmudgeIntensity"].inputs[1])
    link.new(node_map["SmudgeLeveler"].outputs[0], node_map["SmudgeIntensity"].inputs[2])
    
    link.new(node_map["SmudgeIntensity"].outputs[0], go["Image"])
    
  
    # Animate mapping value
    fcurve = node_map["Map Value"].inputs[0].driver_add("default_value")
    fcurve.driver.expression = "frame"
    fcurve = node_map["Map Value.100"].inputs[0].driver_add("default_value")
    fcurve.driver.expression = "frame"
    fcurve = node_map["Map Value.200"].inputs[0].driver_add("default_value")
    fcurve.driver.expression = "frame"
    
# === CUSTOM NODE CLASSES ===

class APERTURIA_OT_RefreshAll(bpy.types.Operator):
    bl_idname = "aperturia.refresh_all"
    bl_label = "Restore Aperturia FX"
    bl_description = "Checks and restores Aperturia FX and Lite node groups and textures"

    def execute(self, context):
        restored_fx = False
        restored_lite = False

        # Standard FX check
        try:
            restored_fx = check_aperturia_integrity()
        except Exception as e:
            self.report({'WARNING'}, f"FX check failed: {e}")

        # Lite check (optional – define this in your Lite add-on)
        try:
            from aperture_fx_lite import check_aperturia_lite_integrity  # Adjust import if needed
            restored_lite = check_aperturia_lite_integrity()
        except ImportError:
            pass  # Lite not installed – no problem
        except Exception as e:
            self.report({'WARNING'}, f"Lite check failed: {e}")

        if restored_fx or restored_lite:
            self.report({'INFO'}, "Aperturia FX and/or Lite were rebuilt.")
        else:
            self.report({'INFO'}, "All Aperturia components are already intact.")

        return {'FINISHED'}


class APERTURIA_PT_Tools(bpy.types.Panel):
    bl_label = "Aperturia FX Tools"
    bl_idname = "APERTURIA_PT_Tools"
    bl_space_type = 'NODE_EDITOR'
    bl_region_type = 'UI'
    bl_category = "Aperturia"

    def draw(self, context):
        layout = self.layout
        layout.operator("aperturia.refresh_all", icon='FILE_REFRESH')


class CompositorNodeAperturiaFX(bpy.types.Node):
    bl_idname = "CompositorNodeAperturiaFX"
    bl_label = "Quick lens effects"
    bl_icon = 'CAMERA_DATA'

    def init(self, context):
        group_name = "Aperturia FX"
        if group_name in bpy.data.node_groups:
            self.node_tree = bpy.data.node_groups[group_name]

    @classmethod
    def poll(cls, context):
        return context.space_data.tree_type == "CompositorNodeTree"


class AperturiaFXCategory(NodeCategory):
    @classmethod
    def poll(cls, context):
        return context.space_data.tree_type == "CompositorNodeTree"


node_categories = [
    AperturiaFXCategory("APERTURIA_NODES", "Aperturia FX", items=[
        NodeItem("CompositorNodeAperturiaFX"),
    ]),
]

# === REGISTER / UNREGISTER ===

classes = (
    CompositorNodeAperturiaFX,
    APERTURIA_OT_RefreshAll,
    APERTURIA_PT_Tools,
)

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

    nodeitems_utils.register_node_categories("APERTURIA_FX", node_categories)

    if on_file_load not in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.append(on_file_load)

    from bpy.app.timers import register as delay

    def deferred_node_group_build():
        ensure_aperturia_textures()
        if "Aperturia FX" in bpy.data.node_groups:
            bpy.data.node_groups.remove(bpy.data.node_groups["Aperturia FX"])
        group, node_map = create_custom_node_group()
        if group and node_map:
            wire_custom_node_group(group, node_map)
        return None

    delay(deferred_node_group_build, first_interval=1.0)


def unregister():
    nodeitems_utils.unregister_node_categories("APERTURIA_FX")

    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)

    if on_file_load in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(on_file_load)

    if "Aperturia FX" in bpy.data.node_groups:
        bpy.data.node_groups.remove(bpy.data.node_groups["Aperturia FX"])