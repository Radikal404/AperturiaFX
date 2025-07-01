Hey there!

Thank you for purchasing Aperturia FX, and say good-bye to time consuming manual node set-ups.
This is my first ever Blender add-on—and I had a blast making it. While the core system is built as a node group (rather than a native compiled node), 
I’ve wrapped it into a full add-on for your convenience. No more appending .blend files — just install, enable, and go.

----HOW TO INSTALL THE ADD-ON:----
- Open Blender and go to Edit → Preferences → Add-ons
- Click the drop-down arrow in the top-right and choose 'Install from Disk…'
- Navigate to your downloaded Aperturia_FX.zip
- Once installed, enable the checkbox next to the add-on in the list

----ALTERNATIVE METHOD:----
- Open Blender
- Drag the Aperturia_FX.zip file into the 3D Viewport
- When the 'Install from Disk...' dialog appears, confirm it
- Then go to Edit → Preferences → Add-ons to enable it if needed
- Search for “Aperturia” to locate it quickly
- Make sure the checkbox is enabled


----HOW TO USE:----
Once installed, head over to "Compositing" and Press Shift+A or click on 'Add' > 'Group' > 'Aperturia FX'. If the node does not show up immediately,
locate 'Aperturia' on the N-Panel and click on 'Restore Aperturia FX' - This will add the node if it wasn't added automatically.
Node consists of:
Image (input) - this is where you connect your render to in order to start processing it with the node.
Image (output) - processed render comes out of it. Since the node was meant to act as a "RAW filter" then Color Correction or Color Balance is recommended in some cases.
Camera Age - This let's you choose between a blend of 3 main camera effects:
	1.0 - Modern day camera
	0.5 - Mobile phone camera, lower quality
	0.0 - Retro camera with sepia filter, lowest quality.
General Noise - Amount of visible noise.
Shadow Contrast - Amount of noise in shadows.
Shadow Noise intensity - Size and intensity of shadow mask, used with Shadow Contrast.
Color Noise intensity - Strength of color splotches on the render.
Color Noise scale - Size of the color splotches.
Image Scale - Up- or downscale the image. Best used when rendering the scene at lower resolution, turning this up can make a 720p resolution fit into 1080p and so on.
	      Useful when replicating older devices, but wanting to keep the scene at 1080p or higher resolution. Values 0-200 are OK, go higher at your own risk.
Lens Distortion - Amount of perspective curving, "fish eye lens" effect.
Lens Dispersion - Amount of chromatic aberration, the red-blue visual effect that appears on edges and surfaces of objects.
Vignette Amount - Strength of the vignette, darker corners of the screen.


----FAQ:----
Do I have to re-enable it every time?
Nope. The node group is flagged with Fake User, meaning it stays in your file even if it’s not used in any node tree.
However, if the node or textures get manually deleted or purged, don’t worry—the add-on includes a failsafe system that 
checks for missing parts when you reload your .blend. Even better, you can restore everything instantly by opening the 
N-panel (press N) inside the compositor, selecting the “Aperturia” tab, and hitting the “Restore Aperturia FX” button.

What do I get from this add-on?
The add-on is meant to give you a node group that gives you a photorealistic Compositor node setup. It comes with various sliders to help you tailor the 
exact effect you wish to have.
It also has many numeral limits to avoid exaggerated values, which tend to be the "break" in the "Make or break" for photorealistic renders.

Can I edit the node group?
Absolutely. You’re free to dive in, tweak, expand, or remix it however you like. It’s made for instant realism, but you're encouraged to experiment.

If you have any more questions, you can e-mail me at radikalaa@outlook.com
or DM me on Discord: @radikal, just be sure to tell me you're there regarding the add-on, otherwise I may take you as another Discord scammer.


