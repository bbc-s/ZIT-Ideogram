"""Z-Image-Turbo regional prompt builder.

This node is based on KJNodes' Ideogram 4 visual region editor, but emits native
ComfyUI/Z-Image conditioning and masks instead of Ideogram caption JSON.
"""

import json
import os

import node_helpers
import numpy as np
import torch
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

from comfy_api.latest import io


_FONT_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "fonts", "FreeMono.ttf")


def _font(size):
    try:
        return ImageFont.truetype(_FONT_PATH, size)
    except Exception:
        try:
            return ImageFont.load_default(size)
        except Exception:
            return ImageFont.load_default()


def _parse_json_list(s):
    if s:
        try:
            v = json.loads(s)
            if isinstance(v, list):
                return v
        except json.JSONDecodeError:
            pass
    return []


def _dumps(v):
    return json.dumps(v, ensure_ascii=False, indent=2)


def _norm_box(box):
    x = float(box.get("x", 0.0))
    y = float(box.get("y", 0.0))
    w = float(box.get("w", 0.0))
    h = float(box.get("h", 0.0))
    if w < 0:
        x += w
        w = -w
    if h < 0:
        y += h
        h = -h
    x = max(0.0, min(1.0, x))
    y = max(0.0, min(1.0, y))
    w = max(0.0, min(1.0 - x, w))
    h = max(0.0, min(1.0 - y, h))
    return x, y, w, h


def _encode_zimage(clip, prompt):
    tokens = clip.tokenize(prompt or "")
    return clip.encode_from_tokens_scheduled(tokens)


def _compose_region_prompt(global_prompt, boxes):
    parts = [(global_prompt or "").strip()]
    region_parts = []
    for i, box in enumerate(boxes, start=1):
        prompt = (box.get("prompt") or box.get("desc") or "").strip()
        if prompt:
            region_parts.append(f"region {i}: {prompt}")
    if region_parts:
        parts.append("; ".join(region_parts))
    return "\n".join(p for p in parts if p)


def _set_mask(conditioning, mask, strength, set_area_to_bounds=True):
    return node_helpers.conditioning_set_values(
        conditioning,
        {
            "mask": mask,
            "set_area_to_bounds": bool(set_area_to_bounds),
            "mask_strength": float(strength),
        },
    )


def _box_mask(width, height, box, default_feather, default_strength):
    x, y, w, h = _norm_box(box)
    x1 = max(0, min(width, round(x * width)))
    y1 = max(0, min(height, round(y * height)))
    x2 = max(0, min(width, round((x + w) * width)))
    y2 = max(0, min(height, round((y + h) * height)))

    mask = Image.new("L", (width, height), 0)
    if x2 > x1 and y2 > y1:
        ImageDraw.Draw(mask).rectangle([x1, y1, x2, y2], fill=255)

    feather = float(box.get("feather", default_feather) or 0.0)
    if feather > 0:
        mask = mask.filter(ImageFilter.GaussianBlur(radius=feather))

    strength = float(box.get("strength", default_strength) or 0.0)
    arr = np.asarray(mask, dtype=np.float32) / 255.0
    arr *= max(0.0, min(10.0, strength))
    return torch.from_numpy(arr).clamp(0.0, 1.0), {
        "x": x1,
        "y": y1,
        "width": max(0, x2 - x1),
        "height": max(0, y2 - y1),
    }


def _wrap(draw, text, font, max_w):
    lines = []
    for para in (text or "").split("\n"):
        line = ""
        for word in para.split():
            test = word if not line else line + " " + word
            if line and draw.textlength(test, font=font) > max_w:
                lines.append(line)
                line = word
            else:
                line = test
        if line:
            lines.append(line)
    return lines


def _render_preview(boxes, width, height, masks, bg=None, brightness=50):
    if bg is not None:
        iw, ih = bg.size
        long_edge = max(iw, ih)
        scale = min(1.0, 1024 / long_edge) if long_edge > 0 else 1.0
        rw, rh = max(1, round(iw * scale)), max(1, round(ih * scale))
        base = bg.convert("RGB").resize((rw, rh), Image.LANCZOS)
        base = ImageEnhance.Brightness(base).enhance(max(0.0, min(1.0, brightness / 100.0)))
        img = base.convert("RGBA")
    else:
        long_edge = max(width, height)
        scale = min(1.0, 1024 / long_edge) if long_edge > 0 else 1.0
        rw, rh = max(1, round(width * scale)), max(1, round(height * scale))
        g = round(max(0, min(100, brightness)) / 100 * 128)
        img = Image.new("RGBA", (rw, rh), (g, g, g, 255))

    overlay = Image.new("RGBA", (rw, rh), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    font = _font(max(10, round(rh / 64)))
    tag_font = _font(max(9, round(rh / 72)))
    colors = [(70, 180, 230), (240, 170, 60), (120, 205, 120), (220, 100, 120), (180, 140, 255)]

    for i, box in enumerate(boxes):
        x, y, w, h = _norm_box(box)
        x1, y1 = round(x * rw), round(y * rh)
        x2, y2 = round((x + w) * rw), round((y + h) * rh)
        color = colors[i % len(colors)]
        draw.rectangle([x1, y1, x2, y2], outline=color + (255,), width=2)
        draw.rectangle([x1, y1, x1 + 26, y1 + 16], fill=color + (230,))
        draw.text((x1 + 4, y1 + 2), str(i + 1).zfill(2), fill=(0, 0, 0, 255), font=tag_font)
        text = box.get("prompt") or box.get("desc") or ""
        ty = y1 + 21
        for line in _wrap(draw, text, font, max(12, x2 - x1 - 8)):
            if ty > y2:
                break
            draw.text((x1 + 4, ty), line, fill=color + (255,), font=font)
            ty += font.size + 2 if hasattr(font, "size") else 13

    if masks:
        combined = torch.stack(masks).max(dim=0).values
        m = Image.fromarray((combined.detach().cpu().numpy() * 120).clip(0, 120).astype(np.uint8), "L")
        m = m.resize((rw, rh), Image.BILINEAR)
        tint = Image.new("RGBA", (rw, rh), (70, 180, 230, 0))
        tint.putalpha(m)
        overlay = Image.alpha_composite(tint, overlay)

    img = Image.alpha_composite(img, overlay).convert("RGB")
    arr = np.asarray(img, dtype=np.float32) / 255.0
    return torch.from_numpy(arr).unsqueeze(0)


class ZImageTurboRegionBuilderKJ(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="ZImageTurboRegionBuilderKJ",
            display_name="Z-Image-Turbo Region Builder KJ",
            category="ZIT-Ideogram/Z-Image",
            search_aliases=["z-image", "zimage", "turbo", "regional prompt", "mask", "inpaint"],
            is_experimental=True,
            description="""
Visual region prompt builder for Z-Image-Turbo.

Draw boxes on the canvas, set a prompt, optional negative prompt, strength, and
feather per region. The node outputs Z-Image text conditionings with ComfyUI
masks, a batch of independent masks, a combined mask for img2img/inpainting, and
serialized region data for workflow save/load.
""",
            inputs=[
                io.Clip.Input("clip"),
                io.Int.Input("width", default=1024, min=64, max=16384, step=16),
                io.Int.Input("height", default=1024, min=64, max=16384, step=16),
                io.String.Input("global_prompt", multiline=True, default="", dynamic_prompts=True),
                io.String.Input("global_negative_prompt", multiline=True, default="", dynamic_prompts=True),
                io.Combo.Input("mode", options=["text_to_image", "image_to_image_region_edit"], default="text_to_image"),
                io.Float.Input("default_region_strength", default=1.0, min=0.0, max=10.0, step=0.01),
                io.Float.Input("default_feather", default=16.0, min=0.0, max=512.0, step=1.0),
                io.Combo.Input("conditioning_mode", options=["single_prompt_fast", "regional_conditioning_slow"],
                               default="single_prompt_fast",
                               tooltip="single_prompt_fast is recommended for Z-Image-Turbo. regional_conditioning_slow adds one masked conditioning per region and can multiply sampling time."),
                io.Image.Input("image", optional=True, tooltip="Optional source/reference image shown in the editor and passed through."),
                io.Vae.Input("vae", optional=True, tooltip="Optional VAE. When provided with an image, the node also outputs an encoded latent with combined_mask as noise_mask for img2img regional edits."),
                io.String.Input("regions_data", default="", socketless=True, advanced=True),
                io.Int.Input("bg_brightness", default=35, min=0, max=100, socketless=True, advanced=True),
            ],
            outputs=[
                io.Conditioning.Output(display_name="positive"),
                io.Conditioning.Output(display_name="negative"),
                io.Mask.Output(display_name="region_masks"),
                io.Mask.Output(display_name="combined_mask"),
                io.Image.Output(display_name="source_image"),
                io.Image.Output(display_name="preview"),
                io.String.Output(display_name="regions_json"),
                io.BoundingBox.Output(display_name="bboxes"),
                io.Int.Output(display_name="width"),
                io.Int.Output(display_name="height"),
                io.Latent.Output(display_name="latent_with_noise_mask"),
            ],
        )

    @classmethod
    def execute(
        cls,
        clip,
        width,
        height,
        global_prompt,
        global_negative_prompt,
        mode,
        default_region_strength,
        default_feather,
        conditioning_mode="single_prompt_fast",
        regions_data="",
        image=None,
        vae=None,
        bg_brightness=35,
    ) -> io.NodeOutput:
        boxes = [b for b in _parse_json_list(regions_data) if isinstance(b, dict)]
        masks = []
        bbox_dicts = []
        region_records = []

        positive = _encode_zimage(clip, _compose_region_prompt(global_prompt, boxes))
        negative = _encode_zimage(clip, global_negative_prompt)

        for box in boxes:
            mask, bbox = _box_mask(width, height, box, default_feather, default_region_strength)
            if bbox["width"] <= 0 or bbox["height"] <= 0:
                continue
            masks.append(mask)
            bbox_dicts.append(bbox)
            strength = float(box.get("strength", default_region_strength) or default_region_strength)
            prompt = (box.get("prompt") or box.get("desc") or "").strip()
            neg_prompt = (box.get("negative_prompt") or "").strip()
            if conditioning_mode == "regional_conditioning_slow" and prompt:
                positive += _set_mask(_encode_zimage(clip, prompt), mask.unsqueeze(0), strength)
            if conditioning_mode == "regional_conditioning_slow" and neg_prompt:
                negative += _set_mask(_encode_zimage(clip, neg_prompt), mask.unsqueeze(0), strength)
            region_records.append(
                {
                    "bbox": bbox,
                    "prompt": prompt,
                    "negative_prompt": neg_prompt,
                    "strength": strength,
                    "feather": float(box.get("feather", default_feather) or 0.0),
                }
            )

        if masks:
            region_masks = torch.stack(masks, dim=0)
            combined_mask = region_masks.max(dim=0).values.unsqueeze(0)
        else:
            region_masks = torch.zeros((1, height, width), dtype=torch.float32)
            combined_mask = torch.zeros((1, height, width), dtype=torch.float32)

        source_image = image
        if source_image is None:
            source_image = torch.zeros((1, height, width, 3), dtype=torch.float32)

        latent = {"samples": torch.zeros((1, 16, max(1, height // 8), max(1, width // 8)), dtype=torch.float32)}
        if image is not None and vae is not None:
            latent = {"samples": vae.encode(image[:, :, :, :3]), "noise_mask": combined_mask}

        bg = None
        if image is not None:
            try:
                bg = Image.fromarray((image[0].detach().cpu().numpy() * 255).clip(0, 255).astype(np.uint8))
            except Exception:
                bg = None
        preview = _render_preview(boxes, width, height, masks, bg, bg_brightness)
        bboxes_out = [bbox_dicts] if bbox_dicts else []

        region_json = {
            "mode": mode,
            "conditioning_mode": conditioning_mode,
            "global_prompt": global_prompt,
            "global_negative_prompt": global_negative_prompt,
            "regions": region_records,
        }

        return io.NodeOutput(
            positive,
            negative,
            region_masks,
            combined_mask,
            source_image,
            preview,
            _dumps(region_json),
            bboxes_out,
            width,
            height,
            latent,
            ui={"dims": [width, height]},
        )
