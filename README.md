# ZIT-Ideogram

ComfyUI custom node that reuses the KJNodes Ideogram 4 visual box editor pattern for Z-Image-Turbo regional prompting.

## Node

`Z-Image-Turbo Region Builder KJ`

Outputs:

- `positive` / `negative`: Z-Image text conditioning with per-region mask metadata.
- `region_masks`: one mask per drawn box, shape `N,H,W`.
- `combined_mask`: max-composited mask for img2img/inpaint noise masks.
- `source_image`: pass-through source image, or a blank image for text-to-image.
- `preview`: editor preview with regions and mask tint.
- `regions_json`, `bboxes`, `width`, `height`.

## Installation

1. Put this folder in `ComfyUI/custom_nodes/ZIT-Ideogram`.
2. Restart ComfyUI.
3. Add node: `ZIT-Ideogram/Z-Image > Z-Image-Turbo Region Builder KJ`.

No extra Python packages are required.

## Usage

Use ComfyUI's built-in Z-Image-Turbo workflow as the base graph, then replace the normal text encoders with this node:

1. Connect Z-Image/Qwen `CLIP` to `clip`.
2. Connect `positive` and `negative` to the sampler.
3. For text-to-image, connect `width` and `height` to your latent/image size nodes.
4. For image-to-image regional editing, connect a source image to `image`, use `combined_mask` as the inpaint/noise mask, and sample at a denoise/strength suitable for the edit.
5. Draw boxes in the editor and set each region prompt, optional region negative prompt, strength, and feather.

The node does not call any Ideogram API and does not emit Ideogram caption JSON. It produces native ComfyUI conditioning and masks.

## Examples

Example region presets are in `examples/`:

- `text_to_image_regional_prompting.json`
- `portrait_hair_editing.json`
- `clothing_replacement.json`
- `background_only_modification.json`

Open a Z-Image-Turbo workflow first, add this node, then use the node's `Paste` button to import the example region JSON.
