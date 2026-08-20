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

import os
import uuid
import torch
import torch.nn.functional as F
import numpy as np
from PIL import Image

try:
    import folder_paths
except ImportError:
    class DummyFolderPaths:
        models_dir = os.path.join(os.path.expanduser("~"), "ComfyUI", "models")
        folder_names_and_extensions = {}

        @classmethod
        def get_filename_list(cls, name):
            return []

        @classmethod
        def get_full_path(cls, name, filename):
            return filename

        @classmethod
        def get_temp_directory(cls):
            temp_dir = os.path.join(os.path.expanduser("~"), "ComfyUI", "temp")
            os.makedirs(temp_dir, exist_ok=True)
            return temp_dir

    folder_paths = DummyFolderPaths()

try:
    from .film_lut import load_cube_lut
except ImportError:
    from film_lut import load_cube_lut


def tensor_rgb_to_hsv(rgb):
    """
    Converts RGB tensor (B, H, W, 3) in range [0, 1] to HSV tensor (B, H, W, 3) where:
    H in [0, 1] (representing 0 to 360 deg), S in [0, 1], V in [0, 1]
    """
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    maxc, _ = torch.max(rgb, dim=-1)
    minc, _ = torch.min(rgb, dim=-1)
    v = maxc
    deltac = maxc - minc

    s = torch.where(maxc > 1e-6, deltac / (maxc + 1e-6), torch.zeros_like(maxc))

    rc = (maxc - r) / (deltac + 1e-6)
    gc = (maxc - g) / (deltac + 1e-6)
    bc = (maxc - b) / (deltac + 1e-6)

    h = torch.where(
        r == maxc,
        bc - gc,
        torch.where(
            g == maxc,
            2.0 + rc - bc,
            4.0 + gc - rc
        )
    )
    h = (h / 6.0) % 1.0
    h = torch.where(deltac < 1e-6, torch.zeros_like(h), h)

    return torch.stack([h, s, v], dim=-1)


def tensor_hsv_to_rgb(hsv):
    """
    Converts HSV tensor (B, H, W, 3) where H, S, V are in [0, 1] to RGB tensor (B, H, W, 3) in [0, 1].
    """
    h, s, v = hsv[..., 0], hsv[..., 1], hsv[..., 2]

    h6 = (h % 1.0) * 6.0
    i = torch.floor(h6)
    f = h6 - i

    p = v * (1.0 - s)
    q = v * (1.0 - s * f)
    t = v * (1.0 - s * (1.0 - f))

    i_mod = i.to(torch.int64) % 6

    r = torch.where(i_mod == 0, v, torch.where(i_mod == 1, q, torch.where(i_mod == 2, p, torch.where(i_mod == 3, p, torch.where(i_mod == 4, t, v)))))
    g = torch.where(i_mod == 0, t, torch.where(i_mod == 1, v, torch.where(i_mod == 2, v, torch.where(i_mod == 3, q, torch.where(i_mod == 4, p, p)))))
    b = torch.where(i_mod == 0, p, torch.where(i_mod == 1, p, torch.where(i_mod == 2, t, torch.where(i_mod == 3, v, torch.where(i_mod == 4, v, q)))))

    return torch.stack([r, g, b], dim=-1)


class HackAfterDarkLiveGrade:
    @classmethod
    def get_search_directories(cls):
        dirs = []
        # Explicit path requested for user system
        explicit_path = r"F:\ComfyUI\models\luts"
        if os.path.exists(explicit_path) and explicit_path not in dirs:
            dirs.append(explicit_path)

        # Standard ComfyUI models/luts directory
        if hasattr(folder_paths, "models_dir") and folder_paths.models_dir:
            models_luts = os.path.join(folder_paths.models_dir, "luts")
            if not os.path.exists(models_luts):
                try:
                    os.makedirs(models_luts, exist_ok=True)
                except Exception:
                    pass
            if os.path.exists(models_luts) and models_luts not in dirs:
                dirs.append(models_luts)

        # Local custom node luts/ directory
        local_luts = os.path.join(os.path.dirname(__file__), "luts")
        if not os.path.exists(local_luts):
            try:
                os.makedirs(local_luts, exist_ok=True)
            except Exception:
                pass
        if os.path.exists(local_luts) and local_luts not in dirs:
            dirs.append(local_luts)

        return dirs

    @classmethod
    def get_lut_files(cls):
        dirs = cls.get_search_directories()
        lut_map = {}
        for d in dirs:
            for root, _, filenames in os.walk(d):
                for f in filenames:
                    if f.lower().endswith((".cube", ".3dl")):
                        rel = os.path.relpath(os.path.join(root, f), d)
                        rel_str = rel.replace("\\", "/")
                        if rel_str not in lut_map:
                            lut_map[rel_str] = os.path.join(root, f)

        if hasattr(folder_paths, "get_filename_list"):
            try:
                for f in folder_paths.get_filename_list("luts"):
                    f_str = f.replace("\\", "/")
                    if f_str not in lut_map:
                        full = folder_paths.get_full_path("luts", f)
                        if full:
                            lut_map[f_str] = full
            except Exception:
                pass

        if not lut_map:
            return ["No LUTs found"]

        return sorted(list(lut_map.keys()))

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image": ("IMAGE",),
                "lut_file": (cls.get_lut_files(),),
                "strength": ("FLOAT", {
                    "default": 1.0,
                    "min": 0.0,
                    "max": 1.0,
                    "step": 0.01,
                    "display": "slider",
                }),
                "exposure": ("FLOAT", {
                    "default": 0.0,
                    "min": -3.0,
                    "max": 3.0,
                    "step": 0.05,
                    "display": "slider",
                }),
                "contrast": ("FLOAT", {
                    "default": 1.0,
                    "min": 0.5,
                    "max": 1.5,
                    "step": 0.01,
                    "display": "slider",
                }),
                "black_lift": ("FLOAT", {
                    "default": 0.0,
                    "min": -0.5,
                    "max": 0.5,
                    "step": 0.005,
                    "display": "slider",
                }),
                "hue": ("FLOAT", {
                    "default": 0.0,
                    "min": -180.0,
                    "max": 180.0,
                    "step": 1.0,
                    "display": "slider",
                }),
                "saturation": ("FLOAT", {
                    "default": 1.0,
                    "min": 0.0,
                    "max": 2.0,
                    "step": 0.01,
                    "display": "slider",
                }),
                "tint_green_magenta": ("FLOAT", {
                    "default": 0.0,
                    "min": -1.0,
                    "max": 1.0,
                    "step": 0.01,
                    "display": "slider",
                }),
                "tint_amber_blue": ("FLOAT", {
                    "default": 0.0,
                    "min": -1.0,
                    "max": 1.0,
                    "step": 0.01,
                    "display": "slider",
                }),
                "enable_preview": ("BOOLEAN", {"default": True}),
                "clip_output": ("BOOLEAN", {"default": True}),
            }
        }

    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("image",)
    FUNCTION = "apply_live_grade"
    CATEGORY = "HackAfterDark"
    OUTPUT_NODE = True

    def resolve_lut_path(self, lut_file):
        if not lut_file or lut_file in ["None", "No LUTs found"]:
            return None

        if os.path.isabs(lut_file) and os.path.exists(lut_file):
            return lut_file

        dirs = self.get_search_directories()
        for d in dirs:
            possible_path = os.path.join(d, lut_file)
            if os.path.exists(possible_path):
                return possible_path

        if hasattr(folder_paths, "get_full_path"):
            try:
                full = folder_paths.get_full_path("luts", lut_file)
                if full and os.path.exists(full):
                    return full
            except Exception:
                pass

        return None

    def apply_live_grade(
        self,
        image,
        lut_file,
        strength=1.0,
        exposure=0.0,
        contrast=1.0,
        black_lift=0.0,
        hue=0.0,
        saturation=1.0,
        tint_green_magenta=0.0,
        tint_amber_blue=0.0,
        enable_preview=True,
        clip_output=True
    ):
        out_image = image.clone()
        B, H, W, C = out_image.shape

        if C != 3:
            raise ValueError(f"Live Grade requires a 3-channel RGB image, got {C} channels")

        # 1. LUT Application
        lut_path = self.resolve_lut_path(lut_file)
        if lut_path and os.path.exists(lut_path) and strength > 0.0:
            lut_tensor = load_cube_lut(lut_path).to(device=image.device, dtype=image.dtype)
            grid_coords = (out_image * 2.0 - 1.0).unsqueeze(1)  # Shape (B, 1, H, W, 3)
            lut_batch = lut_tensor.repeat(B, 1, 1, 1, 1)
            mapped_ncdhw = F.grid_sample(lut_batch, grid_coords, mode="bilinear", padding_mode="border", align_corners=True)
            mapped_img = mapped_ncdhw.squeeze(2).permute(0, 2, 3, 1)
            out_image = (1.0 - strength) * out_image + strength * mapped_img

        # 2. Tonality Adjustments: Exposure -> Contrast -> Black Lift
        if exposure != 0.0:
            out_image = out_image * (2.0 ** exposure)

        if contrast != 1.0:
            out_image = (out_image - 0.5) * contrast + 0.5

        if black_lift != 0.0:
            if black_lift >= 0.0:
                out_image = out_image * (1.0 - black_lift) + black_lift
            else:
                out_image = out_image * (1.0 + black_lift)

        # 3. HSV Adjustments: Hue Shift & Saturation
        if hue != 0.0 or saturation != 1.0:
            hsv = tensor_rgb_to_hsv(out_image)
            if hue != 0.0:
                hsv[..., 0] = (hsv[..., 0] + (hue / 360.0)) % 1.0
            if saturation != 1.0:
                hsv[..., 1] = torch.clamp(hsv[..., 1] * saturation, 0.0, 1.0)
            out_image = tensor_hsv_to_rgb(hsv)

        # 4. Tint Correction (Green/Magenta & Amber/Blue)
        if tint_green_magenta != 0.0 or tint_amber_blue != 0.0:
            r_offset = 0.25 * tint_green_magenta + 0.50 * tint_amber_blue
            g_offset = -0.50 * tint_green_magenta + 0.25 * tint_amber_blue
            b_offset = 0.25 * tint_green_magenta - 0.50 * tint_amber_blue
            tint_vec = torch.tensor([r_offset, g_offset, b_offset], device=out_image.device, dtype=out_image.dtype)
            out_image = out_image + tint_vec

        # 5. Output Clipping
        if clip_output:
            out_image = torch.clamp(out_image, 0.0, 1.0)

        # 6. Preview Image Generation for Frontend UI
        ui_results = {}
        if enable_preview:
            try:
                temp_dir = folder_paths.get_temp_directory() if hasattr(folder_paths, "get_temp_directory") else os.path.join(os.path.expanduser("~"), "ComfyUI", "temp")
                os.makedirs(temp_dir, exist_ok=True)

                session_id = uuid.uuid4().hex[:8]
                orig_fn = f"livegrade_orig_{session_id}.png"

                # Save original sample thumbnail for client-side live grading
                orig_np = (image[0].cpu().numpy() * 255).astype(np.uint8)
                orig_pil = Image.fromarray(orig_np)
                orig_pil.thumbnail((512, 512))
                orig_pil.save(os.path.join(temp_dir, orig_fn), format="PNG")

                ui_results["livegrade_images"] = [
                    {"filename": orig_fn, "subfolder": "", "type": "temp"},
                ]
            except Exception as e:
                print(f"[HackAfterDarkLiveGrade] Warning: Failed to generate preview thumbnail: {e}")

        return {"ui": ui_results, "result": (out_image,)}


NODE_CLASS_MAPPINGS = {
    "HackAfterDarkLiveGrade": HackAfterDarkLiveGrade
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "HackAfterDarkLiveGrade": "HackAfterDark Live Grade"
}
