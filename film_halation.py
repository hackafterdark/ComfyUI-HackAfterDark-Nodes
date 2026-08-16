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

class AfterDarkFilmHalation:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image": ("IMAGE",),
                "halation_intensity": ("FLOAT", {
                    "default": 0.35,
                    "min": 0.0,
                    "max": 1.0,
                    "step": 0.05,
                }),
                "threshold": ("FLOAT", {
                    "default": 0.85,
                    "min": 0.50,
                    "max": 0.99,
                    "step": 0.01,
                }),
                "bloom_radius": ("FLOAT", {
                    "default": 8.0,
                    "min": 1.0,
                    "max": 30.0,
                    "step": 0.5,
                }),
                "halation_tint": (
                    ["Red / Orange (CineStill 800T)", "Golden Amber", "Warm Yellow", "Soft White"],
                    {"default": "Red / Orange (CineStill 800T)"}
                ),
            }
        }

    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("image",)
    FUNCTION = "apply_halation"
    CATEGORY = "HackAfterDark"

    def apply_halation(
        self,
        image,
        halation_intensity=0.35,
        threshold=0.85,
        bloom_radius=8.0,
        halation_tint="Red / Orange (CineStill 800T)"
    ):
        if halation_intensity <= 0.0:
            return (image,)

        out_image = image.clone()
        B, H, W, C = out_image.shape
        device = out_image.device
        dtype = out_image.dtype

        if C < 3:
            return (image,)

        # 1. Calculate luminance map
        luminance = (
            0.2126 * out_image[..., 0] +
            0.7152 * out_image[..., 1] +
            0.0722 * out_image[..., 2]
        )  # [B, H, W]

        # 2. Extract specular highlights above threshold
        specular = torch.clamp((luminance - threshold) / (1.0 - threshold + 1e-6), 0.0, 1.0)
        specular = specular.unsqueeze(1)  # [B, 1, H, W]

        # 3. Determine Halation Tint Color
        if halation_tint == "Red / Orange (CineStill 800T)":
            tint = torch.tensor([1.0, 0.20, 0.04], device=device, dtype=dtype)
        elif halation_tint == "Golden Amber":
            tint = torch.tensor([1.0, 0.55, 0.10], device=device, dtype=dtype)
        elif halation_tint == "Warm Yellow":
            tint = torch.tensor([1.0, 0.80, 0.20], device=device, dtype=dtype)
        elif halation_tint == "Soft White":
            tint = torch.tensor([1.0, 1.0, 1.0], device=device, dtype=dtype)
        else:
            tint = torch.tensor([1.0, 0.20, 0.04], device=device, dtype=dtype)

        # 4. Multi-scale Gaussian Bloom Blur via PyTorch downsampling pyramid
        scale = max(1.0, bloom_radius / 4.0)
        low_h = max(4, int(H / scale))
        low_w = max(4, int(W / scale))

        down = F.interpolate(specular, size=(low_h, low_w), mode="bilinear", align_corners=False)
        blur = F.interpolate(down, size=(H, W), mode="bilinear", align_corners=False)
        blur = blur.squeeze(1).unsqueeze(-1)  # [B, H, W, 1]

        # 5. Apply tinted bloom with soft additive blending
        bloom_effect = blur * tint.view(1, 1, 1, 3) * halation_intensity
        out_image[..., :3] = torch.clamp(out_image[..., :3] + bloom_effect, 0.0, 1.0)

        return (out_image,)

NODE_CLASS_MAPPINGS = {
    "AfterDarkFilmHalation": AfterDarkFilmHalation
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "AfterDarkFilmHalation": "AfterDark Film Halation & Bloom"
}
