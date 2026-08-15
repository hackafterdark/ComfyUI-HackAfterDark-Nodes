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

FILM_PRESETS = {
    "None (Manual)": {},
    "Kodak Portra 400 (Color Negative)": {
        "noise_type": "gaussian",
        "base_grain_size": 1.4,
        "base_jitter": 0.0015,
        "base_aberration": 0.0010,
        "tone_warmth": 0.015,  # subtle Portra warm tint
    },
    "Kodak Ektachrome 100VS (Color Positive)": {
        "noise_type": "poisson",
        "base_grain_size": 1.2,
        "base_jitter": 0.0015,
        "base_aberration": 0.0012,
        "tone_warmth": 0.0,
    },
    "Kodak Tri-X 400 (B&W Silver Halide)": {
        "noise_type": "laplacian",
        "base_grain_size": 1.6,
        "base_jitter": 0.0020,
        "base_aberration": 0.0,
        "tone_warmth": 0.0,
    },
    "Fuji Velvia 50 (Fine Slide Film)": {
        "noise_type": "gaussian",
        "base_grain_size": 1.1,
        "base_jitter": 0.0015,
        "base_aberration": 0.0008,
        "tone_warmth": -0.01,
    },
    "Ilford HP5 Plus 400 (B&W Medium Grain)": {
        "noise_type": "multiplicative",
        "base_grain_size": 1.5,
        "base_jitter": 0.0018,
        "base_aberration": 0.0,
        "tone_warmth": 0.0,
    },
    "CineStill 800T (Tungsten Cinema)": {
        "noise_type": "poisson",
        "base_grain_size": 1.5,
        "base_jitter": 0.0020,
        "base_aberration": 0.0018,
        "tone_warmth": -0.015,  # subtle tungsten cool tint
    },
}

FORMAT_SCALERS = {
    "35mm (24x36 - Standard Grain)": 1.0,
    "Medium Format (6x6 - Fine Grain)": 0.70,
    "Large Format (4x5 - Ultra Fine)": 0.45,
}

class AfterDarkStochasticNoise:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image": ("IMAGE",),
                "film_preset": (list(FILM_PRESETS.keys()), {"default": "None (Manual)"}),
                "film_format": (list(FORMAT_SCALERS.keys()), {"default": "35mm (24x36 - Standard Grain)"}),
                "noise_level": ("FLOAT", {
                    "default": 0.025,
                    "min": 0.0,
                    "max": 0.20,
                    "step": 0.001,
                    "display": "slider"
                }),
                "grain_size": ("FLOAT", {
                    "default": 1.5,
                    "min": 0.5,
                    "max": 5.0,
                    "step": 0.1,
                    "display": "slider"
                }),
                "noise_type": (["gaussian", "poisson", "multiplicative", "laplacian"], {"default": "gaussian"}),
                "channel_mode": (["monochromatic", "color"], {"default": "monochromatic"}),
                "micro_jitter": ("FLOAT", {
                    "default": 0.0015,
                    "min": 0.0,
                    "max": 0.010,
                    "step": 0.0005,
                    "display": "slider"
                }),
                "chromatic_aberration": ("FLOAT", {
                    "default": 0.0010,
                    "min": 0.0,
                    "max": 0.005,
                    "step": 0.0005,
                    "display": "slider"
                }),
                "luminance_weight": ("BOOLEAN", {"default": True}),
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
    FUNCTION = "apply_noise"
    CATEGORY = "HackAfterDark"

    def apply_noise(
        self,
        image,
        film_preset,
        film_format,
        noise_level,
        grain_size=1.5,
        noise_type="gaussian",
        channel_mode="monochromatic",
        micro_jitter=0.0015,
        chromatic_aberration=0.0010,
        luminance_weight=True,
        seed=0
    ):
        out_image = image.clone()
        B, H, W, C = out_image.shape

        format_scale = FORMAT_SCALERS.get(film_format, 1.0)
        preset_cfg = FILM_PRESETS.get(film_preset, {})

        if film_preset != "None (Manual)" and preset_cfg:
            eff_grain_size = grain_size * preset_cfg.get("base_grain_size", 1.0) * format_scale
            eff_micro_jitter = max(micro_jitter, preset_cfg.get("base_jitter", 0.0015))
            eff_chromatic_aberration = max(chromatic_aberration, preset_cfg.get("base_aberration", 0.0010))
            tone_warmth = preset_cfg.get("tone_warmth", 0.0)
        else:
            eff_grain_size = grain_size * format_scale
            eff_micro_jitter = micro_jitter
            eff_chromatic_aberration = chromatic_aberration
            tone_warmth = 0.0

        if (
            noise_level <= 0.0
            and eff_micro_jitter <= 0.0
            and eff_chromatic_aberration <= 0.0
            and tone_warmth == 0.0
        ):
            return (image,)

        generator = None
        if seed != 0:
            device_type = out_image.device.type if hasattr(out_image.device, 'type') else str(out_image.device)
            generator = torch.Generator(device=device_type)
            generator.manual_seed(seed)

        # 1. Subtle Film Tone Tint
        if tone_warmth != 0.0 and C >= 3:
            out_image[..., 0] = out_image[..., 0] + tone_warmth
            out_image[..., 2] = out_image[..., 2] - tone_warmth

        # 2. Spatial Micro-Jitter (sub-pixel grid warping to break VAE lattice signatures)
        if eff_micro_jitter > 0.0:
            tensor_nchw = out_image.permute(0, 3, 1, 2)
            
            grid_y, grid_x = torch.meshgrid(
                torch.linspace(-1, 1, H, device=out_image.device),
                torch.linspace(-1, 1, W, device=out_image.device),
                indexing="ij"
            )
            grid = torch.stack((grid_x, grid_y), dim=-1).unsqueeze(0).repeat(B, 1, 1, 1)

            jitter_raw = (torch.rand((B, max(1, H // 8), max(1, W // 8), 2), device=out_image.device, generator=generator) * 2.0 - 1.0) * eff_micro_jitter
            jitter_raw = jitter_raw.permute(0, 3, 1, 2)
            jitter_smooth = F.interpolate(jitter_raw, size=(H, W), mode="bilinear", align_corners=False).permute(0, 2, 3, 1)

            warped_grid = grid + jitter_smooth
            tensor_nchw = F.grid_sample(tensor_nchw, warped_grid, mode="bilinear", padding_mode="border", align_corners=False)
            out_image = tensor_nchw.permute(0, 2, 3, 1)

        # 3. Subtle Chromatic Aberration (sub-pixel channel offset)
        if eff_chromatic_aberration > 0.0 and C >= 3:
            shift_pixels = max(1, int(eff_chromatic_aberration * min(H, W)))
            r_ch = torch.roll(out_image[..., 0], shifts=(shift_pixels, shift_pixels), dims=(1, 2))
            b_ch = torch.roll(out_image[..., 2], shifts=(-shift_pixels, -shift_pixels), dims=(1, 2))
            out_image[..., 0] = r_ch
            out_image[..., 2] = b_ch

        # 4. Film Grain / Stochastic Noise Generation
        if noise_level > 0.0:
            if eff_grain_size > 1.0:
                g_h = max(1, int(H / eff_grain_size))
                g_w = max(1, int(W / eff_grain_size))
            else:
                g_h, g_w = H, W

            noise_channels = 1 if channel_mode == "monochromatic" else C
            noise_shape = (B, g_h, g_w, noise_channels)

            if noise_type == "gaussian":
                raw_noise = torch.randn(noise_shape, dtype=out_image.dtype, device=out_image.device, generator=generator) * noise_level
            elif noise_type == "multiplicative":
                raw_noise = torch.randn(noise_shape, dtype=out_image.dtype, device=out_image.device, generator=generator) * noise_level
            elif noise_type == "poisson":
                # Shot noise / Poisson arrival approximation
                poisson_scale = 100.0 / max(noise_level, 0.001)
                scaled_tensor = torch.clamp(out_image[..., :noise_channels] * poisson_scale, min=0.1)
                if eff_grain_size > 1.0:
                    scaled_tensor = F.interpolate(scaled_tensor.permute(0, 3, 1, 2), size=(g_h, g_w), mode="bilinear", align_corners=False).permute(0, 2, 3, 1)
                poisson_samples = torch.poisson(scaled_tensor, generator=generator)
                raw_noise = (poisson_samples - scaled_tensor) / poisson_scale
            elif noise_type == "laplacian":
                # Heavy-tailed Laplacian distribution (natural film grain spikes)
                u = torch.rand(noise_shape, dtype=out_image.dtype, device=out_image.device, generator=generator) - 0.5
                raw_noise = -torch.sign(u) * torch.log(1.0 - 2.0 * torch.abs(u) + 1e-7) * (noise_level * 0.707)

            if eff_grain_size > 1.0:
                noise_nchw = raw_noise.permute(0, 3, 1, 2)
                noise_upscaled = F.interpolate(noise_nchw, size=(H, W), mode="bilinear", align_corners=False)
                noise = noise_upscaled.permute(0, 2, 3, 1)
            else:
                noise = raw_noise

            if channel_mode == "monochromatic" and noise.shape[-1] == 1:
                noise = noise.expand(-1, -1, -1, C)

            if luminance_weight:
                if C >= 3:
                    lum = 0.299 * out_image[..., 0:1] + 0.587 * out_image[..., 1:2] + 0.114 * out_image[..., 2:3]
                else:
                    lum = out_image[..., 0:1]
                weight = 1.0 - torch.square(2.0 * (lum - 0.5))
                noise = noise * weight

            if noise_type == "multiplicative":
                out_image = out_image + (out_image * noise)
            else:
                out_image = out_image + noise

        out_image = torch.clamp(out_image, 0.0, 1.0)
        return (out_image,)

NODE_CLASS_MAPPINGS = {
    "AfterDarkStochasticNoise": AfterDarkStochasticNoise
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "AfterDarkStochasticNoise": "AfterDark Film Grain"
}
