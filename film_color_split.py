# Copyright 2026 HackAfterDark
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import torch
import torch.nn.functional as F

class AfterDarkFilmColorSplit:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image": ("IMAGE",),
                "shadow_tint": (
                    ["Neutral", "Teal / Cyan", "Deep Blue", "Emerald Green", "Warm Sepia"],
                    {"default": "Teal / Cyan"}
                ),
                "shadow_intensity": ("FLOAT", {
                    "default": 0.20,
                    "min": 0.0,
                    "max": 1.0,
                    "step": 0.05,
                }),
                "highlight_tint": (
                    ["Neutral", "Golden Amber", "Warm Yellow", "Peach Rose", "Cool Cyan"],
                    {"default": "Golden Amber"}
                ),
                "highlight_intensity": ("FLOAT", {
                    "default": 0.20,
                    "min": 0.0,
                    "max": 1.0,
                    "step": 0.05,
                }),
                "balance": ("FLOAT", {
                    "default": 0.0,
                    "min": -1.0,
                    "max": 1.0,
                    "step": 0.05,
                }),
                "micro_contrast": ("FLOAT", {
                    "default": 0.15,
                    "min": 0.0,
                    "max": 1.0,
                    "step": 0.05,
                }),
            }
        }

    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("image",)
    FUNCTION = "apply_color_split"
    CATEGORY = "HackAfterDark"

    def apply_color_split(
        self,
        image,
        shadow_tint="Teal / Cyan",
        shadow_intensity=0.20,
        highlight_tint="Golden Amber",
        highlight_intensity=0.20,
        balance=0.0,
        micro_contrast=0.15,
    ):
        if not isinstance(shadow_tint, str) or shadow_tint in [0, "0", None] or shadow_tint not in ["Neutral", "Teal / Cyan", "Deep Blue", "Emerald Green", "Warm Sepia"]:
            shadow_tint = "Neutral"
        if not isinstance(highlight_tint, str) or highlight_tint in [0, "0", None] or highlight_tint not in ["Neutral", "Golden Amber", "Warm Yellow", "Peach Rose", "Cool Cyan"]:
            highlight_tint = "Neutral"

        out_image = image.clone()
        B, H, W, C = out_image.shape
        device = out_image.device
        dtype = out_image.dtype

        if C < 3:
            return (image,)

        # 1. Luminance map
        luminance = (
            0.2126 * out_image[..., 0] +
            0.7152 * out_image[..., 1] +
            0.0722 * out_image[..., 2]
        )  # [B, H, W]

        # Shift midpoint by balance
        midpoint = 0.5 + balance * 0.25

        # Shadow & Highlight weight maps
        shadow_weight = torch.clamp((midpoint - luminance) / midpoint, 0.0, 1.0) ** 1.5
        highlight_weight = torch.clamp((luminance - midpoint) / (1.0 - midpoint), 0.0, 1.0) ** 1.5

        shadow_weight = shadow_weight.unsqueeze(-1)  # [B, H, W, 1]
        highlight_weight = highlight_weight.unsqueeze(-1)  # [B, H, W, 1]

        # Shadow RGB Multipliers
        if shadow_tint == "Teal / Cyan":
            s_color = torch.tensor([0.75, 1.10, 1.15], device=device, dtype=dtype)
        elif shadow_tint == "Deep Blue":
            s_color = torch.tensor([0.70, 0.85, 1.25], device=device, dtype=dtype)
        elif shadow_tint == "Emerald Green":
            s_color = torch.tensor([0.75, 1.20, 0.90], device=device, dtype=dtype)
        elif shadow_tint == "Warm Sepia":
            s_color = torch.tensor([1.15, 0.95, 0.75], device=device, dtype=dtype)
        else:
            s_color = torch.tensor([1.0, 1.0, 1.0], device=device, dtype=dtype)

        # Highlight RGB Multipliers
        if highlight_tint == "Golden Amber":
            h_color = torch.tensor([1.20, 1.08, 0.80], device=device, dtype=dtype)
        elif highlight_tint == "Warm Yellow":
            h_color = torch.tensor([1.15, 1.15, 0.75], device=device, dtype=dtype)
        elif highlight_tint == "Peach Rose":
            h_color = torch.tensor([1.20, 0.90, 0.95], device=device, dtype=dtype)
        elif highlight_tint == "Cool Cyan":
            h_color = torch.tensor([0.80, 1.10, 1.20], device=device, dtype=dtype)
        else:
            h_color = torch.tensor([1.0, 1.0, 1.0], device=device, dtype=dtype)

        # Apply Shadow Toning
        if shadow_tint != "Neutral" and shadow_intensity > 0.0:
            tinted_s = out_image[..., :3] * s_color.view(1, 1, 1, 3)
            out_image[..., :3] = (1.0 - shadow_weight * shadow_intensity) * out_image[..., :3] + (shadow_weight * shadow_intensity) * tinted_s

        # Apply Highlight Toning
        if highlight_tint != "Neutral" and highlight_intensity > 0.0:
            tinted_h = out_image[..., :3] * h_color.view(1, 1, 1, 3)
            out_image[..., :3] = (1.0 - highlight_weight * highlight_intensity) * out_image[..., :3] + (highlight_weight * highlight_intensity) * tinted_h

        # 2. Micro-Contrast / Clarity Filter (High-pass spatial frequency mask)
        if micro_contrast > 0.0:
            img_perm = out_image.permute(0, 3, 1, 2)  # [B, C, H, W]
            low_pass = F.avg_pool2d(img_perm, kernel_size=5, stride=1, padding=2)
            high_pass = img_perm - low_pass
            img_perm = img_perm + high_pass * (micro_contrast * 1.2)
            out_image = img_perm.permute(0, 2, 3, 1)

        return (torch.clamp(out_image, 0.0, 1.0),)

NODE_CLASS_MAPPINGS = {
    "AfterDarkFilmColorSplit": AfterDarkFilmColorSplit
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "AfterDarkFilmColorSplit": "AfterDark Film Color Split & Clarity"
}
