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
                    ["None", "C-41 Orange Flare", "Tungsten Blue Burn", "Vintage Magenta Leak", "Random Light Leak"],
                    {"default": "C-41 Orange Flare"}
                ),
                "leak_location": (
                    ["Top Left Corner", "Top Right Corner", "Bottom Left Corner", "Bottom Right Corner", "Left Edge Strip", "Right Edge Strip"],
                    {"default": "Top Right Corner"}
                ),
                "leak_intensity": ("FLOAT", {
                    "default": 0.30,
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
        light_leak_style="C-41 Orange Flare",
        leak_location="Top Right Corner",
        leak_intensity=0.30,
        vignette_amount=0.25,
        vignette_falloff=1.5,
        gate_border=0.0,
        seed=0,
    ):
        out_image = image.clone()
        B, H, W, C = out_image.shape
        device = out_image.device
        dtype = out_image.dtype

        # 1. Procedural Light Leak Injection
        if light_leak_style != "None" and leak_intensity > 0.0 and C >= 3:
            generator = None
            if seed != 0:
                device_type = device.type if hasattr(device, 'type') else str(device)
                generator = torch.Generator(device=device_type)
                generator.manual_seed(seed)

            # Determine color tint for light leak
            if light_leak_style == "C-41 Orange Flare":
                color_tint = torch.tensor([1.0, 0.45, 0.10], device=device, dtype=dtype)
            elif light_leak_style == "Tungsten Blue Burn":
                color_tint = torch.tensor([0.20, 0.55, 1.0], device=device, dtype=dtype)
            elif light_leak_style == "Vintage Magenta Leak":
                color_tint = torch.tensor([0.95, 0.20, 0.65], device=device, dtype=dtype)
            elif light_leak_style == "Random Light Leak":
                if generator is not None:
                    rand_color = torch.rand((3,), device=device, dtype=dtype, generator=generator)
                else:
                    rand_color = torch.rand((3,), device=device, dtype=dtype)
                color_tint = torch.clamp(rand_color + 0.2, 0.0, 1.0)
            else:
                color_tint = torch.tensor([1.0, 0.45, 0.10], device=device, dtype=dtype)

            # Generate spatial coordinate grid
            y_coords = torch.linspace(0, 1, H, device=device, dtype=dtype)
            x_coords = torch.linspace(0, 1, W, device=device, dtype=dtype)
            grid_y, grid_x = torch.meshgrid(y_coords, x_coords, indexing="ij")

            # Determine distance mask based on leak location
            if leak_location == "Top Left Corner":
                dist = torch.sqrt(grid_x**2 + grid_y**2)
            elif leak_location == "Top Right Corner":
                dist = torch.sqrt((1.0 - grid_x)**2 + grid_y**2)
            elif leak_location == "Bottom Left Corner":
                dist = torch.sqrt(grid_x**2 + (1.0 - grid_y)**2)
            elif leak_location == "Bottom Right Corner":
                dist = torch.sqrt((1.0 - grid_x)**2 + (1.0 - grid_y)**2)
            elif leak_location == "Left Edge Strip":
                dist = grid_x
            elif leak_location == "Right Edge Strip":
                dist = 1.0 - grid_x
            else:
                dist = torch.sqrt((1.0 - grid_x)**2 + grid_y**2)

            leak_mask = torch.clamp(1.0 - dist / 0.75, 0.0, 1.0) ** 1.8
            leak_mask = leak_mask.unsqueeze(-1).unsqueeze(0)  # [1, H, W, 1]

            # Screen blending mode: Out = 1 - (1 - Image) * (1 - Leak * Intensity)
            leak_tensor = leak_mask * color_tint.view(1, 1, 1, 3) * leak_intensity
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
            # Create soft border falloff
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
