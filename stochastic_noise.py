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
        "channel_mode": "color",
        "base_grain_size": 1.4,
        "base_jitter": 0.0015,
        "base_aberration": 0.0010,
        "tone_warmth": 0.015,
        "noise_level": 0.025,
        "gamma_shift": 0.98,
        "edge_softening": 0.10,
        "spatial_resample": 0.015,
        "luminance_response": "Film (Midtone & Shadow)",
    },
    "Kodak Ektachrome 100VS (Color Positive)": {
        "noise_type": "poisson",
        "channel_mode": "color",
        "base_grain_size": 1.2,
        "base_jitter": 0.0015,
        "base_aberration": 0.0012,
        "tone_warmth": 0.0,
        "noise_level": 0.018,
        "gamma_shift": 0.94,
        "edge_softening": 0.08,
        "spatial_resample": 0.012,
        "luminance_response": "Film (Midtone & Shadow)",
    },
    "Kodak Tri-X 400 (B&W Silver Halide)": {
        "noise_type": "laplacian",
        "channel_mode": "monochromatic",
        "base_grain_size": 1.6,
        "base_jitter": 0.0020,
        "base_aberration": 0.0,
        "tone_warmth": 0.0,
        "noise_level": 0.030,
        "gamma_shift": 0.96,
        "edge_softening": 0.10,
        "spatial_resample": 0.015,
        "luminance_response": "Film (Midtone & Shadow)",
    },
    "Fuji Velvia 50 (Fine Slide Film)": {
        "noise_type": "gaussian",
        "channel_mode": "color",
        "base_grain_size": 1.1,
        "base_jitter": 0.0015,
        "base_aberration": 0.0008,
        "tone_warmth": -0.01,
        "noise_level": 0.012,
        "gamma_shift": 0.92,
        "edge_softening": 0.05,
        "spatial_resample": 0.010,
        "luminance_response": "Film (Midtone & Shadow)",
    },
    "Ilford HP5 Plus 400 (B&W Medium Grain)": {
        "noise_type": "multiplicative",
        "channel_mode": "monochromatic",
        "base_grain_size": 1.5,
        "base_jitter": 0.0018,
        "base_aberration": 0.0,
        "tone_warmth": 0.0,
        "noise_level": 0.028,
        "gamma_shift": 0.97,
        "edge_softening": 0.10,
        "spatial_resample": 0.015,
        "luminance_response": "Film (Midtone & Shadow)",
    },
    "CineStill 800T (Tungsten Cinema)": {
        "noise_type": "poisson",
        "channel_mode": "color",
        "base_grain_size": 1.5,
        "base_jitter": 0.0020,
        "base_aberration": 0.0018,
        "tone_warmth": -0.015,
        "noise_level": 0.040,
        "gamma_shift": 0.96,
        "edge_softening": 0.15,
        "spatial_resample": 0.018,
        "luminance_response": "Film (Midtone & Shadow)",
    },
    "Kodak Kodachrome 64 (Vintage Color Reversal)": {
        "noise_type": "poisson",
        "channel_mode": "color",
        "base_grain_size": 1.05,
        "base_jitter": 0.0012,
        "base_aberration": 0.0008,
        "tone_warmth": 0.010,
        "noise_level": 0.015,
        "gamma_shift": 0.95,
        "edge_softening": 0.12,
        "spatial_resample": 0.012,
        "luminance_response": "Film (Midtone & Shadow)",
    },
    "Kodak Gold 200 (Consumer Color Negative)": {
        "noise_type": "gaussian",
        "channel_mode": "color",
        "base_grain_size": 1.45,
        "base_jitter": 0.0016,
        "base_aberration": 0.0012,
        "tone_warmth": 0.025,
        "noise_level": 0.025,
        "gamma_shift": 0.98,
        "edge_softening": 0.10,
        "spatial_resample": 0.015,
        "luminance_response": "Film (Midtone & Shadow)",
    },
    "Fuji Pro 400H (Cool Pastel Portrait)": {
        "noise_type": "gaussian",
        "channel_mode": "color",
        "base_grain_size": 1.35,
        "base_jitter": 0.0014,
        "base_aberration": 0.0010,
        "tone_warmth": -0.010,
        "noise_level": 0.022,
        "gamma_shift": 0.99,
        "edge_softening": 0.08,
        "spatial_resample": 0.012,
        "luminance_response": "Film (Midtone & Shadow)",
    },
    "Kodak Vision3 250D (Daylight Cinema)": {
        "noise_type": "poisson",
        "channel_mode": "color",
        "base_grain_size": 1.25,
        "base_jitter": 0.0016,
        "base_aberration": 0.0012,
        "tone_warmth": 0.0,
        "noise_level": 0.024,
        "gamma_shift": 0.97,
        "edge_softening": 0.10,
        "spatial_resample": 0.015,
        "luminance_response": "Film (Midtone & Shadow)",
    },
    "Kodak T-Max 3200 (High-Speed B&W)": {
        "noise_type": "laplacian",
        "channel_mode": "monochromatic",
        "base_grain_size": 2.20,
        "base_jitter": 0.0030,
        "base_aberration": 0.0,
        "tone_warmth": 0.0,
        "noise_level": 0.055,
        "gamma_shift": 0.95,
        "edge_softening": 0.12,
        "spatial_resample": 0.020,
        "luminance_response": "Film (Midtone & Shadow)",
    },
    "Ilford Delta 100 (Fine-Grain B&W)": {
        "noise_type": "multiplicative",
        "channel_mode": "monochromatic",
        "base_grain_size": 0.95,
        "base_jitter": 0.0010,
        "base_aberration": 0.0,
        "tone_warmth": 0.0,
        "noise_level": 0.014,
        "gamma_shift": 0.98,
        "edge_softening": 0.05,
        "spatial_resample": 0.010,
        "luminance_response": "Film (Midtone & Shadow)",
    },
    "Agfa Vista 200 (Vibrant Pop Color)": {
        "noise_type": "gaussian",
        "channel_mode": "color",
        "base_grain_size": 1.30,
        "base_jitter": 0.0015,
        "base_aberration": 0.0011,
        "tone_warmth": 0.015,
        "noise_level": 0.024,
        "gamma_shift": 0.96,
        "edge_softening": 0.10,
        "spatial_resample": 0.015,
        "luminance_response": "Film (Midtone & Shadow)",
    },
    "Polaroid 600 (Instant Analog Emulsion)": {
        "noise_type": "multiplicative",
        "channel_mode": "color",
        "base_grain_size": 1.80,
        "base_jitter": 0.0022,
        "base_aberration": 0.0022,
        "tone_warmth": 0.008,
        "noise_level": 0.035,
        "gamma_shift": 1.02,
        "edge_softening": 0.20,
        "spatial_resample": 0.022,
        "luminance_response": "Film (Midtone & Shadow)",
    },
    "Harman Phoenix 200 (Experimental Color)": {
        "noise_type": "gaussian",
        "channel_mode": "color",
        "base_grain_size": 1.70,
        "base_jitter": 0.0022,
        "base_aberration": 0.0020,
        "tone_warmth": 0.028,
        "noise_level": 0.032,
        "gamma_shift": 0.94,
        "edge_softening": 0.15,
        "spatial_resample": 0.018,
        "luminance_response": "Film (Midtone & Shadow)",
    },
    "Lomography Lady Grey 400 (B&W 120 Medium Format)": {
        "noise_type": "laplacian",
        "channel_mode": "monochromatic",
        "base_grain_size": 1.30,
        "base_jitter": 0.0018,
        "base_aberration": 0.0,
        "tone_warmth": 0.0,
        "noise_level": 0.026,
        "gamma_shift": 0.96,
        "edge_softening": 0.08,
        "spatial_resample": 0.014,
        "luminance_response": "Film (Midtone & Shadow)",
    },
    "Fuji Neopan Acros 100 II (Ultra-Fine B&W)": {
        "noise_type": "laplacian",
        "channel_mode": "monochromatic",
        "base_grain_size": 0.90,
        "base_jitter": 0.0010,
        "base_aberration": 0.0,
        "tone_warmth": 0.0,
        "noise_level": 0.012,
        "gamma_shift": 0.97,
        "edge_softening": 0.03,
        "spatial_resample": 0.008,
        "luminance_response": "Film (Midtone & Shadow)",
    },
    "Ilford Delta 3200 (High-Speed Gritty B&W)": {
        "noise_type": "laplacian",
        "channel_mode": "monochromatic",
        "base_grain_size": 2.40,
        "base_jitter": 0.0035,
        "base_aberration": 0.0,
        "tone_warmth": 0.0,
        "noise_level": 0.058,
        "gamma_shift": 0.95,
        "edge_softening": 0.14,
        "spatial_resample": 0.022,
        "luminance_response": "Film (Midtone & Shadow)",
    },
    "Kodak Ektar 100 (Ultra-Vivid Fine Color)": {
        "noise_type": "gaussian",
        "channel_mode": "color",
        "base_grain_size": 0.95,
        "base_jitter": 0.0010,
        "base_aberration": 0.0006,
        "tone_warmth": 0.005,
        "noise_level": 0.013,
        "gamma_shift": 0.95,
        "edge_softening": 0.05,
        "spatial_resample": 0.010,
        "luminance_response": "Film (Midtone & Shadow)",
    },
    "Kodak ColorPlus 200 (Vintage Consumer Warmth)": {
        "noise_type": "gaussian",
        "channel_mode": "color",
        "base_grain_size": 1.40,
        "base_jitter": 0.0016,
        "base_aberration": 0.0012,
        "tone_warmth": 0.022,
        "noise_level": 0.025,
        "gamma_shift": 0.98,
        "edge_softening": 0.12,
        "spatial_resample": 0.016,
        "luminance_response": "Film (Midtone & Shadow)",
    },
    "LomoChrome Metropolis (Desaturated Experimental)": {
        "noise_type": "multiplicative",
        "channel_mode": "color",
        "base_grain_size": 1.65,
        "base_jitter": 0.0020,
        "base_aberration": 0.0015,
        "tone_warmth": -0.012,
        "noise_level": 0.030,
        "gamma_shift": 0.93,
        "edge_softening": 0.12,
        "spatial_resample": 0.018,
        "luminance_response": "Film (Midtone & Shadow)",
    },
    "Ilford Pan F Plus 50 (Ultra-Fine Low-ISO B&W)": {
        "noise_type": "multiplicative",
        "channel_mode": "monochromatic",
        "base_grain_size": 0.85,
        "base_jitter": 0.0008,
        "base_aberration": 0.0,
        "tone_warmth": 0.0,
        "noise_level": 0.010,
        "gamma_shift": 0.96,
        "edge_softening": 0.02,
        "spatial_resample": 0.006,
        "luminance_response": "Film (Midtone & Shadow)",
    },
    "Lomography Earl Grey 100 (Fine B&W)": {
        "noise_type": "laplacian",
        "channel_mode": "monochromatic",
        "base_grain_size": 1.05,
        "base_jitter": 0.0012,
        "base_aberration": 0.0,
        "tone_warmth": 0.0,
        "noise_level": 0.015,
        "gamma_shift": 0.97,
        "edge_softening": 0.06,
        "spatial_resample": 0.010,
        "luminance_response": "Film (Midtone & Shadow)",
    },
    "Agfa Scala 200x (B&W Reversal Slide)": {
        "noise_type": "poisson",
        "channel_mode": "monochromatic",
        "base_grain_size": 1.20,
        "base_jitter": 0.0015,
        "base_aberration": 0.0,
        "tone_warmth": 0.0,
        "noise_level": 0.020,
        "gamma_shift": 0.93,
        "edge_softening": 0.08,
        "spatial_resample": 0.012,
        "luminance_response": "Film (Midtone & Shadow)",
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
                }),
                "grain_size": ("FLOAT", {
                    "default": 1.5,
                    "min": 0.5,
                    "max": 5.0,
                    "step": 0.1,
                }),
                "noise_type": (["gaussian", "poisson", "multiplicative", "laplacian"], {"default": "gaussian"}),
                "channel_mode": (["monochromatic", "color"], {"default": "monochromatic"}),
                "micro_jitter": ("FLOAT", {
                    "default": 0.0015,
                    "min": 0.0,
                    "max": 0.010,
                    "step": 0.0005,
                }),
                "chromatic_aberration": ("FLOAT", {
                    "default": 0.0010,
                    "min": 0.0,
                    "max": 0.005,
                    "step": 0.0005,
                }),
                "spatial_resample": ("FLOAT", {
                    "default": 0.015,
                    "min": 0.0,
                    "max": 0.05,
                    "step": 0.005,
                }),
                "gamma_shift": ("FLOAT", {
                    "default": 0.98,
                    "min": 0.90,
                    "max": 1.10,
                    "step": 0.005,
                }),
                "edge_softening": ("FLOAT", {
                    "default": 0.10,
                    "min": 0.0,
                    "max": 1.0,
                    "step": 0.05,
                }),
                "luminance_response": (["Film (Midtone & Shadow)", "Digital (Shadow Heavy)", "Uniform (Flat)"], {"default": "Film (Midtone & Shadow)"}),
                "tone_warmth": ("FLOAT", {
                    "default": 0.0,
                    "min": -0.10,
                    "max": 0.10,
                    "step": 0.001,
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
        spatial_resample=0.015,
        gamma_shift=0.98,
        edge_softening=0.10,
        luminance_response="Film (Midtone & Shadow)",
        tone_warmth=0.0,
        seed=0,
        luminance_weight=None
    ):
        # Backward compatibility if luminance_weight boolean parameter is provided
        if luminance_weight is not None:
            if isinstance(luminance_weight, bool):
                luminance_response = "Film (Midtone & Shadow)" if luminance_weight else "Uniform (Flat)"
            elif isinstance(luminance_weight, str):
                luminance_response = luminance_weight
        out_image = image.clone()
        B, H, W, C = out_image.shape

        format_scale = FORMAT_SCALERS.get(film_format, 1.0)
        preset_cfg = FILM_PRESETS.get(film_preset, {})

        if film_preset != "None (Manual)" and preset_cfg:
            eff_grain_size = grain_size * preset_cfg.get("base_grain_size", 1.0) * format_scale
            eff_micro_jitter = micro_jitter if micro_jitter != 0.0015 else preset_cfg.get("base_jitter", 0.0015)
            eff_chromatic_aberration = chromatic_aberration if chromatic_aberration != 0.0010 else preset_cfg.get("base_aberration", 0.0010)
            eff_tone_warmth = tone_warmth if tone_warmth != 0.0 else preset_cfg.get("tone_warmth", 0.0)
        else:
            eff_grain_size = grain_size * format_scale
            eff_micro_jitter = micro_jitter
            eff_chromatic_aberration = chromatic_aberration
            eff_tone_warmth = tone_warmth

        if (
            noise_level <= 0.0
            and eff_micro_jitter <= 0.0
            and eff_chromatic_aberration <= 0.0
            and eff_tone_warmth == 0.0
            and spatial_resample <= 0.0
            and gamma_shift == 1.0
            and edge_softening <= 0.0
        ):
            return (image,)

        generator = None
        if seed != 0:
            device_type = out_image.device.type if hasattr(out_image.device, 'type') else str(out_image.device)
            generator = torch.Generator(device=device_type)
            generator.manual_seed(seed)

        # 1. Spatial Resampling Jitter (rescales down slightly & upscales back using bicubic to strip VAE high-freq harmonics)
        if spatial_resample > 0.0:
            scale_fac = 1.0 - spatial_resample
            low_h = max(1, int(H * scale_fac))
            low_w = max(1, int(W * scale_fac))
            tensor_nchw = out_image.permute(0, 3, 1, 2)
            resampled = F.interpolate(tensor_nchw, size=(low_h, low_w), mode="bilinear", align_corners=False)
            resampled = F.interpolate(resampled, size=(H, W), mode="bicubic", align_corners=False)
            out_image = resampled.permute(0, 2, 3, 1)

        # 2. Non-Linear Gamma Curve Shift (disrupts VAE Swish/SiLU color manifold activation signatures)
        if gamma_shift != 1.0:
            out_image = torch.pow(torch.clamp(out_image, 1e-6, 1.0), gamma_shift)

        # 3. Micro Edge Softening (softens hyper-crisp synthetic machine edges)
        if edge_softening > 0.0:
            tensor_nchw = out_image.permute(0, 3, 1, 2)
            kernel = torch.tensor([[1., 2., 1.], [2., 4., 2.], [1., 2., 1.]], device=out_image.device, dtype=out_image.dtype) / 16.0
            kernel = kernel.expand(C, 1, 3, 3)
            blurred_nchw = F.conv2d(tensor_nchw, kernel, padding=1, groups=C)
            blurred_img = blurred_nchw.permute(0, 2, 3, 1)
            out_image = torch.lerp(out_image, blurred_img, edge_softening * 0.3)

        # 4. Subtle Film Tone Tint
        if eff_tone_warmth != 0.0 and C >= 3:
            out_image[..., 0] = out_image[..., 0] + eff_tone_warmth
            out_image[..., 2] = out_image[..., 2] - eff_tone_warmth

        # 5. Spatial Micro-Jitter (sub-pixel grid warping to break VAE lattice signatures)
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

        # 6. Subtle Chromatic Aberration (sub-pixel channel offset)
        if eff_chromatic_aberration > 0.0 and C >= 3:
            shift_pixels = max(1, int(eff_chromatic_aberration * min(H, W)))
            r_ch = torch.roll(out_image[..., 0], shifts=(shift_pixels, shift_pixels), dims=(1, 2))
            b_ch = torch.roll(out_image[..., 2], shifts=(-shift_pixels, -shift_pixels), dims=(1, 2))
            out_image[..., 0] = r_ch
            out_image[..., 2] = b_ch

        # 7. Film Grain / Stochastic Noise Generation
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
                poisson_scale = 100.0 / max(noise_level, 0.001)
                scaled_tensor = torch.clamp(out_image[..., :noise_channels] * poisson_scale, min=0.1)
                if eff_grain_size > 1.0:
                    scaled_tensor = F.interpolate(scaled_tensor.permute(0, 3, 1, 2), size=(g_h, g_w), mode="bilinear", align_corners=False).permute(0, 2, 3, 1)
                poisson_samples = torch.poisson(scaled_tensor, generator=generator)
                raw_noise = (poisson_samples - scaled_tensor) / poisson_scale
            elif noise_type == "laplacian":
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

            if luminance_response != "Uniform (Flat)":
                if C >= 3:
                    lum = 0.299 * out_image[..., 0:1] + 0.587 * out_image[..., 1:2] + 0.114 * out_image[..., 2:3]
                else:
                    lum = out_image[..., 0:1]

                if luminance_response == "Digital (Shadow Heavy)":
                    # Digital Sensor low-SNR noise (heaviest in deep darks, rolls off linearly)
                    weight = torch.clamp(1.0 - 0.75 * lum, min=0.10, max=1.0)
                else:
                    # Film (Midtone & Shadow): Peak density in shadows/midtones, soft roll-off in highlights
                    weight = torch.clamp(1.0 - torch.pow(torch.clamp(lum - 0.2, min=0.0), 1.5) * 1.5, min=0.15, max=1.0)

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
