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

class AfterDarkFilmOpticsArtifacts:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image": ("IMAGE",),
                "light_leak_style": (
                    [
                        "None",
                        "C-41 Fiery Core Flare",
                        "Tungsten Blue Burn",
                        "Vintage Magenta Leak",
                        "Sunburst Golden Flare",
                        "Rainbow Prism Flare",
                        "Dual-Tone Cyan & Amber",
                        "Random Organic Multi-Layer"
                    ],
                    {"default": "C-41 Fiery Core Flare"}
                ),
                "leak_location": (
                    [
                        "Random / Scattered",
                        "Dual-Border Holga Leak",
                        "Wide Gate Leak (Asymmetric Bar)",
                        "Vertical Curtain Gap",
                        "Bottom Frame Burn",
                        "Dual-Edge Cross Burn",
                        "Top Left Corner",
                        "Top Right Corner",
                        "Bottom Left Corner",
                        "Bottom Right Corner",
                        "Left Edge Strip",
                        "Right Edge Strip",
                        "Center Specular Flare",
                        "Diagonal Streak",
                        "Sprocket Hole Leaks"
                    ],
                    {"default": "Random / Scattered"}
                ),
                "leak_intensity": ("FLOAT", {
                    "default": 0.35,
                    "min": 0.0,
                    "max": 1.0,
                    "step": 0.05,
                }),
                "vignette_amount": ("FLOAT", {
                    "default": 0.25,
                    "min": 0.0,
                    "max": 1.0,
                    "step": 0.05,
                }),
                "vignette_falloff": ("FLOAT", {
                    "default": 1.5,
                    "min": 0.5,
                    "max": 3.0,
                    "step": 0.1,
                }),
                "gate_border": ("FLOAT", {
                    "default": 0.0,
                    "min": 0.0,
                    "max": 0.15,
                    "step": 0.01,
                }),
            },
            "optional": {
                "seed": ("INT", {
                    "default": 0,
                    "min": 0,
                    "max": 0xffffffffffffffff,
                }),
            }
        }

    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("image",)
    FUNCTION = "apply_artifacts"
    CATEGORY = "HackAfterDark"

    def apply_artifacts(
        self,
        image,
        light_leak_style="C-41 Fiery Core Flare",
        leak_location="Random / Scattered",
        leak_intensity=0.35,
        vignette_amount=0.25,
        vignette_falloff=1.5,
        gate_border=0.0,
        seed=0,
    ):
        out_image = image.clone()
        B, H, W, C = out_image.shape
        device = out_image.device
        dtype = out_image.dtype

        # 1. Procedural Organic Light Leak Engine
        if light_leak_style != "None" and leak_intensity > 0.0 and C >= 3:
            generator = None
            if seed != 0:
                device_type = device.type if hasattr(device, 'type') else str(device)
                generator = torch.Generator(device=device_type)
                generator.manual_seed(seed)

            # Spatial coordinate meshgrid [0, 1]
            y_coords = torch.linspace(0, 1, H, device=device, dtype=dtype)
            x_coords = torch.linspace(0, 1, W, device=device, dtype=dtype)
            grid_y, grid_x = torch.meshgrid(y_coords, x_coords, indexing="ij")

            # Seed-driven spatial perturbations (center jitter & ellipse scaling)
            if generator is not None:
                jitter_x = (torch.rand((1,), device=device, dtype=dtype, generator=generator).item() - 0.5) * 0.30
                jitter_y = (torch.rand((1,), device=device, dtype=dtype, generator=generator).item() - 0.5) * 0.30
                scale_x = 0.7 + torch.rand((1,), device=device, dtype=dtype, generator=generator).item() * 0.7
                scale_y = 0.7 + torch.rand((1,), device=device, dtype=dtype, generator=generator).item() * 0.7
            else:
                jitter_x, jitter_y = 0.0, 0.0
                scale_x, scale_y = 1.0, 1.0

            # Base colors for flare layers
            hot_core_tint = torch.tensor([1.0, 0.95, 0.45], device=device, dtype=dtype)  # White-hot yellow core

            if light_leak_style in ("C-41 Fiery Core Flare", "None"):
                outer_tint = torch.tensor([1.0, 0.25, 0.05], device=device, dtype=dtype)  # Deep C-41 Red-Orange
            elif light_leak_style == "Tungsten Blue Burn":
                outer_tint = torch.tensor([0.15, 0.50, 1.0], device=device, dtype=dtype)
            elif light_leak_style == "Vintage Magenta Leak":
                outer_tint = torch.tensor([0.95, 0.15, 0.60], device=device, dtype=dtype)
            elif light_leak_style == "Sunburst Golden Flare":
                outer_tint = torch.tensor([1.0, 0.70, 0.15], device=device, dtype=dtype)
            elif light_leak_style == "Dual-Tone Cyan & Amber":
                outer_tint = torch.tensor([0.10, 0.85, 0.95], device=device, dtype=dtype)
            elif light_leak_style in ("Random Organic Multi-Layer", "Rainbow Prism Flare"):
                if generator is not None:
                    rand_color = torch.rand((3,), device=device, dtype=dtype, generator=generator)
                else:
                    rand_color = torch.rand((3,), device=device, dtype=dtype)
                outer_tint = torch.clamp(rand_color + 0.15, 0.0, 1.0)
            else:
                outer_tint = torch.tensor([1.0, 0.25, 0.05], device=device, dtype=dtype)

            # Ultra-smooth organic cloud modulation map (bicubic spline)
            low_noise = torch.rand((1, 1, 8, 8), device=device, dtype=dtype, generator=generator)
            noise_cloud = F.interpolate(low_noise, size=(H, W), mode="bicubic", align_corners=False).squeeze()

            # Primary Leak Distance & Mask Geometry Calculation
            if leak_location == "Dual-Border Holga Leak":
                # Inspired directly by the Buddha statue reference photo:
                # 1. Intense bottom-left golden flare blob
                # 2. Right-side vertical golden light column
                # 3. Soft top-sky magenta fogging
                dist_left = torch.sqrt(((grid_x - (0.05 + jitter_x * 0.3)) / (0.25 * scale_x))**2 + ((grid_y - (0.85 + jitter_y * 0.3)) / (0.35 * scale_y))**2)
                mask_left = torch.exp(-(dist_left**2) / 0.35)

                dist_right = torch.abs(grid_x - (0.90 + jitter_x * 0.2)) / (0.12 * scale_x)
                mask_right = torch.exp(-(dist_right**2) / 0.35) * (0.6 + 0.4 * torch.sin(grid_y * 3.14159 * 2.0))

                mask_top = torch.clamp((0.25 - grid_y) / 0.25, 0.0, 1.0) * 0.35

                outer_mask = torch.clamp(mask_left + mask_right + mask_top, 0.0, 1.0) * (0.80 + 0.20 * noise_cloud)
                core_mask = torch.clamp(mask_left * 1.5 + mask_right * 0.8 - 0.4, 0.0, 1.0)
                dist = torch.sqrt(torch.clamp(1.0 - outer_mask, 1e-4, 1.0))

            elif leak_location in ("Wide Gate Leak (Asymmetric Bar)", "Vertical Curtain Gap"):
                # Inspired directly by user reference images (Image 1 & 2):
                # 1. Asymmetric sharp right gate edge (shadow of metal gate) + soft left bleed
                # 2. Vertical intensity modulation & gap break in upper-middle
                # 3. Secondary subtle strip on opposite edge
                bar_center = 0.60 + jitter_x * 0.4 if leak_location == "Wide Gate Leak (Asymmetric Bar)" else 0.75 + jitter_x * 0.4
                bar_width = 0.22 * scale_x if leak_location == "Wide Gate Leak (Asymmetric Bar)" else 0.08 * scale_x

                dx = (grid_x - bar_center) / max(bar_width, 0.01)
                
                # Asymmetric sharp drop-off on right edge vs smooth bleed on left edge
                left_edge = torch.clamp((dx + 1.0) * 3.0, 0.0, 1.0)
                right_edge = torch.clamp(1.0 - (dx - 0.2) * 14.0, 0.0, 1.0)
                asymmetric_profile = left_edge * right_edge

                # Vertical intensity modulation & gap break (inspired by Image 1 break in upper middle)
                vert_modulation = 0.55 + 0.45 * torch.sin(grid_y * 3.14159 * 2.5 + jitter_y * 10.0)
                gap_break = torch.clamp(1.0 - torch.exp(-((grid_y - (0.35 + jitter_y * 0.2))**2) / 0.015) * 0.85, 0.15, 1.0)

                bar_mask = asymmetric_profile * vert_modulation * gap_break

                # Secondary thin strip on opposite side (like Image 1 near bus!)
                sec_x = 0.15 - jitter_x * 0.3
                sec_dist = torch.abs(grid_x - sec_x) / 0.06
                sec_mask = torch.exp(-(sec_dist**2) / 0.35) * 0.35 * vert_modulation

                outer_mask = torch.clamp(bar_mask + sec_mask, 0.0, 1.0) * (0.75 + 0.25 * noise_cloud)
                core_mask = torch.clamp(bar_mask - 0.35, 0.0, 1.0) * (1.0 - grid_y) * 1.5  # Hot bottom core
                dist = torch.sqrt(torch.clamp(1.0 - outer_mask, 1e-4, 1.0))

            elif leak_location == "Bottom Frame Burn":
                # Inspired by Ref Image 1 & 3: Upward fiery flare from bottom edge with uneven height
                dist_y = torch.clamp(1.0 - grid_y - jitter_y, 0.0, 1.0) / scale_y
                dist_x = torch.abs(grid_x - (0.4 + jitter_x)) / scale_x
                dist = torch.sqrt(dist_x**2 + dist_y**2)
                outer_mask = torch.exp(-(dist ** 2) / 0.35) * (0.80 + 0.20 * noise_cloud)
                core_mask = torch.exp(-(dist ** 2) / 0.06) * outer_mask

            elif leak_location == "Dual-Edge Cross Burn":
                # Inspired by Ref Image 2: Two opposing leaks (bottom flare + top corner leak)
                dist1 = torch.sqrt(((grid_x - (0.1 + jitter_x)) / scale_x)**2 + ((grid_y - (0.9 + jitter_y)) / scale_y)**2)
                dist2 = torch.sqrt(((grid_x - (0.9 - jitter_x)) / scale_x)**2 + ((grid_y - (0.1 - jitter_y)) / scale_y)**2)
                dist = torch.min(dist1, dist2)
                outer_mask = torch.exp(-(dist ** 2) / 0.35) * (0.80 + 0.20 * noise_cloud)
                core_mask = torch.exp(-(dist ** 2) / 0.06) * outer_mask

            elif leak_location == "Random / Scattered":
                # Multi-pocket random scatter: Generates 1 to 2 organic flare pockets
                cx1, cy1 = 0.5 + jitter_x, 0.5 + jitter_y
                cx2, cy2 = 0.1 + jitter_y, 0.85 - jitter_x
                dist1 = torch.sqrt(((grid_x - cx1) / scale_x)**2 + ((grid_y - cy1) / scale_y)**2)
                dist2 = torch.sqrt(((grid_x - cx2) / scale_y)**2 + ((grid_y - cy2) / scale_x)**2)
                dist = torch.min(dist1, dist2)
                outer_mask = torch.exp(-(dist ** 2) / 0.35) * (0.80 + 0.20 * noise_cloud)
                core_mask = torch.exp(-(dist ** 2) / 0.06) * outer_mask

            elif leak_location == "Top Left Corner":
                dist = torch.sqrt(((grid_x - (0.0 + jitter_x)) / scale_x)**2 + ((grid_y - (0.0 + jitter_y)) / scale_y)**2)
                outer_mask = torch.exp(-(dist ** 2) / 0.35) * (0.80 + 0.20 * noise_cloud)
                core_mask = torch.exp(-(dist ** 2) / 0.06) * outer_mask

            elif leak_location == "Top Right Corner":
                dist = torch.sqrt(((grid_x - (1.0 + jitter_x)) / scale_x)**2 + ((grid_y - (0.0 + jitter_y)) / scale_y)**2)
                outer_mask = torch.exp(-(dist ** 2) / 0.35) * (0.80 + 0.20 * noise_cloud)
                core_mask = torch.exp(-(dist ** 2) / 0.06) * outer_mask

            elif leak_location == "Bottom Left Corner":
                dist = torch.sqrt(((grid_x - (0.0 + jitter_x)) / scale_x)**2 + ((grid_y - (1.0 + jitter_y)) / scale_y)**2)
                outer_mask = torch.exp(-(dist ** 2) / 0.35) * (0.80 + 0.20 * noise_cloud)
                core_mask = torch.exp(-(dist ** 2) / 0.06) * outer_mask

            elif leak_location == "Bottom Right Corner":
                dist = torch.sqrt(((grid_x - (1.0 + jitter_x)) / scale_x)**2 + ((grid_y - (1.0 + jitter_y)) / scale_y)**2)
                outer_mask = torch.exp(-(dist ** 2) / 0.35) * (0.80 + 0.20 * noise_cloud)
                core_mask = torch.exp(-(dist ** 2) / 0.06) * outer_mask

            elif leak_location == "Left Edge Strip":
                dist = torch.abs(grid_x - (0.0 + jitter_x)) / scale_x
                outer_mask = torch.exp(-(dist ** 2) / 0.35) * (0.80 + 0.20 * noise_cloud)
                core_mask = torch.exp(-(dist ** 2) / 0.06) * outer_mask

            elif leak_location == "Right Edge Strip":
                dist = torch.abs(grid_x - (1.0 + jitter_x)) / scale_x
                outer_mask = torch.exp(-(dist ** 2) / 0.35) * (0.80 + 0.20 * noise_cloud)
                core_mask = torch.exp(-(dist ** 2) / 0.06) * outer_mask

            elif leak_location == "Center Specular Flare":
                dist = torch.sqrt(((grid_x - 0.5) / scale_x)**2 + ((grid_y - 0.5) / scale_y)**2)
                outer_mask = torch.exp(-(dist ** 2) / 0.35) * (0.80 + 0.20 * noise_cloud)
                core_mask = torch.exp(-(dist ** 2) / 0.06) * outer_mask

            elif leak_location == "Diagonal Streak":
                dist = torch.abs((grid_x + grid_y) / 1.414 - (0.7 + jitter_x)) / scale_x
                outer_mask = torch.exp(-(dist ** 2) / 0.35) * (0.80 + 0.20 * noise_cloud)
                core_mask = torch.exp(-(dist ** 2) / 0.06) * outer_mask

            elif leak_location == "Sprocket Hole Leaks":
                sprocket_freq = torch.sin(grid_y * 3.14159 * 12.0) ** 4
                dist = torch.clamp((torch.min(grid_x, 1.0 - grid_x) * 4.0) + (1.0 - sprocket_freq) * 0.5, 0.0, 2.0)
                outer_mask = torch.exp(-(dist ** 2) / 0.35) * (0.80 + 0.20 * noise_cloud)
                core_mask = torch.exp(-(dist ** 2) / 0.06) * outer_mask

            else:
                dist = torch.sqrt((1.0 - grid_x)**2 + grid_y**2)
                outer_mask = torch.exp(-(dist ** 2) / 0.35) * (0.80 + 0.20 * noise_cloud)
                core_mask = torch.exp(-(dist ** 2) / 0.06) * outer_mask

            # Spectral color gradient blending (Outer Fringe -> White Hot Core)
            if light_leak_style == "Rainbow Prism Flare":
                rainbow_tint = torch.stack([
                    0.5 + 0.5 * torch.sin(dist * 6.28 + 0.0),
                    0.5 + 0.5 * torch.sin(dist * 6.28 + 2.09),
                    0.5 + 0.5 * torch.sin(dist * 6.28 + 4.18),
                ], dim=-1)  # [H, W, 3]
                leak_color = rainbow_tint
            else:
                leak_color = (1.0 - core_mask.unsqueeze(-1)) * outer_tint.view(1, 1, 3) + core_mask.unsqueeze(-1) * hot_core_tint.view(1, 1, 3)

            leak_tensor = outer_mask.unsqueeze(-1).unsqueeze(0) * leak_color.unsqueeze(0) * leak_intensity

            # Screen blend mode: Out = 1 - (1 - Image) * (1 - Leak * Intensity)
            out_image[..., :3] = 1.0 - (1.0 - out_image[..., :3]) * (1.0 - leak_tensor)

        # 2. Physical Lens Vignetting (Cos^4 theta optical law)
        if vignette_amount > 0.0:
            y_coords = torch.linspace(-1, 1, H, device=device, dtype=dtype)
            x_coords = torch.linspace(-1, 1, W, device=device, dtype=dtype)
            grid_y, grid_x = torch.meshgrid(y_coords, x_coords, indexing="ij")

            radius_sq = (grid_x**2 + grid_y**2) / 2.0  # Normalized radius [0, 1]
            vignette_map = 1.0 - vignette_amount * torch.clamp(radius_sq ** (vignette_falloff / 2.0), 0.0, 1.0)
            vignette_map = vignette_map.unsqueeze(-1).unsqueeze(0)  # [1, H, W, 1]

            out_image = out_image * vignette_map

        # 3. Soft Film Gate Border Shading
        if gate_border > 0.0:
            border_h = max(1, int(H * gate_border))
            border_w = max(1, int(W * gate_border))

            gate_mask = torch.ones((H, W), device=device, dtype=dtype)
            for i in range(border_h):
                alpha = i / float(border_h)
                gate_mask[i, :] *= alpha
                gate_mask[H - 1 - i, :] *= alpha
            for j in range(border_w):
                alpha = j / float(border_w)
                gate_mask[:, j] *= alpha
                gate_mask[:, W - 1 - j] *= alpha

            gate_mask = gate_mask.unsqueeze(-1).unsqueeze(0)  # [1, H, W, 1]
            out_image = out_image * gate_mask

        return (torch.clamp(out_image, 0.0, 1.0),)

NODE_CLASS_MAPPINGS = {
    "AfterDarkFilmOpticsArtifacts": AfterDarkFilmOpticsArtifacts
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "AfterDarkFilmOpticsArtifacts": "AfterDark Film Optics & Artifacts"
}
