# ZIT-Ideogram

> # HEAVY BETA TESTING NODE WITH LOTS OF BUGS</strong>

> **Warning:** This project is experimental, unstable, and actively changing. Expect broken workflows, UI issues, poor Z-Image-Turbo regional adherence, performance regressions, and compatibility bugs.

ComfyUI custom node that reuses the KJNodes Ideogram 4 visual box editor pattern for Z-Image-Turbo regional prompting.

## Node

`Z-Image-Turbo Region Builder KJ`

Outputs:

- `positive`: the positive Z-Image conditioning. Connect this to the sampler positive input.
- `negative`: the negative Z-Image conditioning. Connect this to the sampler negative input.
- `latent_with_noise_mask`: latent output for the sampler. For text-to-image it is an empty latent. For image-to-image, if `image` and `vae` are connected, it is the encoded source image latent with `combined_mask` attached as `noise_mask`.
- `combined_mask`: one mask made from all drawn boxes. White/bright areas are editable, black areas should stay preserved. Usually only needed if your workflow has a separate mask/inpaint input.
- `region_masks`: separate masks for every drawn box, shape `N,H,W`. Mostly for debugging, previewing, or advanced workflows that process each region separately.
- `source_image`: the input image passed through. If no image is connected, this is a blank image. Optional; use it only if another node needs the original image.
- `preview`: visual preview image with boxes and mask tint. Optional; useful with `Preview Image`.
- `regions_json`: debug text showing parsed regions and the final composed positive prompt. Optional; useful for checking what the node actually sent to CLIP.
- `bboxes`: bounding boxes in pixel coordinates. Optional; only useful for nodes that accept ComfyUI `BBOX` data.
- `width` / `height`: passthrough image dimensions. Optional; useful if another node needs the same size.

## Installation

1. Put this folder in `ComfyUI/custom_nodes/ZIT-Ideogram`.
2. Restart ComfyUI.
3. Add node: `ZIT-Ideogram/Z-Image > Z-Image-Turbo Region Builder KJ`.

No extra Python packages are required.

## Usage

Use ComfyUI's built-in Z-Image-Turbo workflow as the base graph, then replace the normal text encoders with this node:

1. Connect Z-Image/Qwen `CLIP` to `clip`.
2. Connect `positive` and `negative` to the sampler.
3. For text-to-image, connect `latent_with_noise_mask` to the sampler latent input, or connect `width`, `height`, and `batch_size` to your own latent/image size nodes.
4. For image-to-image regional editing, connect the source image to `image`, connect the same VAE used by the workflow to `vae`, then connect `latent_with_noise_mask` to the sampler latent input.
5. Draw boxes in the editor and set each region prompt, optional region negative prompt, strength, and feather.

The node does not call any Ideogram API and does not emit Ideogram caption JSON. It produces native ComfyUI conditioning and masks.

## Basic Workflows

### Text-to-image

Minimum wiring:

1. `clip` input <- your Z-Image/Qwen CLIP.
2. `positive` output -> sampler positive.
3. `negative` output -> sampler negative.
4. `latent_with_noise_mask` output -> sampler latent input.

You can ignore `region_masks`, `combined_mask`, `source_image`, `regions_json`, `bboxes`, `width`, and `height` for a simple text-to-image workflow.

### Image-to-image regional edit

Recommended wiring:

1. Load or provide an image.
2. Connect that image to this node's `image` input.
3. Connect the workflow VAE to this node's `vae` input.
4. Connect `positive` -> sampler positive.
5. Connect `negative` -> sampler negative.
6. Connect `latent_with_noise_mask` -> sampler latent input.
7. Set sampler denoise around `0.6` to `0.8` as a starting point.

With this wiring, the node encodes the source image and attaches the drawn boxes as the latent noise mask. The sampler should mainly change the masked regions. You normally do not need to connect `combined_mask` separately in this setup.

Use `combined_mask` separately only if your graph has a dedicated mask/inpaint input, for example an inpaint conditioning node, mask preview node, or a workflow that expects an external mask in addition to the latent.

## Z-Image-Turbo Notes

Z-Image-Turbo does not natively consume Ideogram-style bounding-box caption JSON. The editor boxes are converted into ComfyUI masks and prompt text.

`conditioning_mode`:

- `single_prompt_fast`: recommended default. Region prompts are folded into one Z-Image prompt and masks are output separately. This keeps sampling speed close to a normal Z-Image workflow.
- `regional_conditioning_slow`: experimental for Z-Image-Turbo. It emits one masked conditioning per region, can multiply sampler work by the number of regions, and often does not improve adherence because ZIT is not designed like Ideogram's API regional editor.

For text-to-image, region text is treated as additional positive prompt text with a rough area hint. Z-Image-Turbo may still ignore the rectangle or move the concept because it does not natively support hard regional prompt boxes.

For image-to-image edits, connect `image` and `vae`, then use `latent_with_noise_mask` as the sampler latent. The node's `batch_size` repeats a single source latent/mask when you want multiple variations. In testing, KSampler denoise around `0.6` to `0.8` is usually the practical range for visible regional changes while preserving the rest of the image. This is the closest native ComfyUI path for "only change the selected area". Preservation still depends on Z-Image-Turbo, denoise, mask feather, and the workflow; it is not equivalent to Ideogram 4's API-level regional editor.

`default_feather` controls mask edge softness in pixels. `0` is a hard rectangle edge, `8-24` is a normal soft edge, and `32+` creates a very broad transition.

`default_region_strength` controls mask opacity/weight for generated region masks and `latent_with_noise_mask`. In `single_prompt_fast` it does not make the text prompt stronger. For img2img edits, keep it near `1.0` unless you intentionally want a weaker/noisier mask edge effect; use sampler denoise for edit intensity.

