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
import torch
import torch.nn.functional as F

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
    folder_paths = DummyFolderPaths()

def load_cube_lut(lut_path):
    """
    Parses an Adobe .cube 3D LUT file and returns a PyTorch Tensor of shape (1, 3, size, size, size).
    """
    size = None
    lut_data = []

    with open(lut_path, 'r', encoding='utf-8', errors='ignore') as f:
        for line in f:
            line = line.strip()
            if line == "" or line.startswith("#"):
                continue
            if '#' in line:
                line = line.split('#')[0].strip()
            if "LUT_3D_SIZE" in line:
                try:
                    size = int(line.split()[-1])
                except ValueError:
                    pass
            else:
                parts = line.split()
                if len(parts) >= 3:
                    try:
                        lut_data.append([float(parts[0]), float(parts[1]), float(parts[2])])
                    except ValueError:
                        pass

    if size is None:
        raise ValueError(f"No valid LUT_3D_SIZE found in LUT file: {lut_path}")
    if len(lut_data) != size**3:
        raise ValueError(f"Expected {size**3} entries, found {len(lut_data)} in {lut_path}")

    # Shape in cube format: R varies fastest, then G, then B
    lut_tensor = torch.tensor(lut_data, dtype=torch.float32)
    # Reshape to (B_size, G_size, R_size, 3)
    lut_tensor = lut_tensor.view(size, size, size, 3)
    # Permute to PyTorch NCDHW convention: (1, 3, B_size, G_size, R_size)
    lut_tensor = lut_tensor.permute(3, 0, 1, 2).unsqueeze(0)
    return lut_tensor

class AfterDarkFilmLUT:
    @classmethod
    def get_search_directories(cls):
        dirs = []
        # 1. ComfyUI models/luts
        if hasattr(folder_paths, "models_dir") and folder_paths.models_dir:
            models_luts = os.path.join(folder_paths.models_dir, "luts")
            if not os.path.exists(models_luts):
                try:
                    os.makedirs(models_luts, exist_ok=True)
                except Exception:
                    pass
            if os.path.exists(models_luts):
                dirs.append(models_luts)
        
        # 2. Local custom node luts/
        local_luts = os.path.join(os.path.dirname(__file__), "luts")
        if not os.path.exists(local_luts):
            try:
                os.makedirs(local_luts, exist_ok=True)
            except Exception:
                pass
        if os.path.exists(local_luts):
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

        # Also check folder_paths if luts was registered there
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
                }),
                "contrast": ("FLOAT", {
                    "default": 1.0,
                    "min": 0.5,
                    "max": 1.5,
                    "step": 0.01,
                }),
                "black_lift": ("FLOAT", {
                    "default": 0.0,
                    "min": 0.0,
                    "max": 0.10,
                    "step": 0.005,
                }),
                "color_space": (["sRGB (Standard)", "Linear -> sRGB", "sRGB -> Linear"], {"default": "sRGB (Standard)"}),
                "clip_output": ("BOOLEAN", {"default": True}),
            }
        }

    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("image",)
    FUNCTION = "apply_lut"
    CATEGORY = "HackAfterDark"

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

    def apply_lut(
        self,
        image,
        lut_file,
        strength=1.0,
        contrast=1.0,
        black_lift=0.0,
        color_space="sRGB (Standard)",
        clip_output=True
    ):
        if (lut_file in ["None", "No LUTs found"] or strength <= 0.0) and contrast == 1.0 and black_lift == 0.0:
            return (image,)

        out_image = image.clone()
        B, H, W, C = out_image.shape

        if C != 3:
            raise ValueError(f"LUT application requires a 3-channel RGB image, got {C} channels")

        lut_path = self.resolve_lut_path(lut_file)
        if lut_file not in ["None", "No LUTs found"] and strength > 0.0:
            if not lut_path or not os.path.exists(lut_path):
                raise FileNotFoundError(f"LUT file not found: {lut_file}")

            lut_tensor = load_cube_lut(lut_path).to(device=image.device, dtype=image.dtype)

            # Color Space Conversion (if needed)
            if color_space == "Linear -> sRGB":
                out_image = torch.where(
                    out_image <= 0.0031308,
                    out_image * 12.92,
                    1.055 * torch.pow(torch.clamp(out_image, 1e-6, 1.0), 1.0 / 2.4) - 0.055
                )
            elif color_space == "sRGB -> Linear":
                out_image = torch.where(
                    out_image <= 0.04045,
                    out_image / 12.92,
                    torch.pow(torch.clamp((out_image + 0.055) / 1.055, 0.0, 1.0), 2.4)
                )

            # Map pixel RGB values [0, 1] to PyTorch grid_sample normalized coordinates [-1, 1]
            grid_coords = (out_image * 2.0 - 1.0).unsqueeze(1)  # Shape (B, 1, H, W, 3)

            # Hardware-accelerated 3D trilinear interpolation on GPU
            lut_batch = lut_tensor.repeat(B, 1, 1, 1, 1)
            mapped_ncdhw = F.grid_sample(lut_batch, grid_coords, mode="bilinear", padding_mode="border", align_corners=True)
            mapped_img = mapped_ncdhw.squeeze(2).permute(0, 2, 3, 1)

            # Post-LUT color space reversal if applicable
            if color_space == "sRGB -> Linear":
                mapped_img = torch.where(
                    mapped_img <= 0.0031308,
                    mapped_img * 12.92,
                    1.055 * torch.pow(torch.clamp(mapped_img, 1e-6, 1.0), 1.0 / 2.4) - 0.055
                )
            elif color_space == "Linear -> sRGB":
                mapped_img = torch.where(
                    mapped_img <= 0.04045,
                    mapped_img / 12.92,
                    torch.pow(torch.clamp((mapped_img + 0.055) / 1.055, 0.0, 1.0), 2.4)
                )

            # Alpha blend between original and LUT result based on strength
            out_image = (1.0 - strength) * image + strength * mapped_img

        # Apply Contrast Adjustment
        if contrast != 1.0:
            out_image = (out_image - 0.5) * contrast + 0.5

        # Apply Black Lift (Film Toe Density)
        if black_lift > 0.0:
            out_image = out_image * (1.0 - black_lift) + black_lift

        if clip_output:
            out_image = torch.clamp(out_image, 0.0, 1.0)

        return (out_image,)

NODE_CLASS_MAPPINGS = {
    "AfterDarkFilmLUT": AfterDarkFilmLUT
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "AfterDarkFilmLUT": "AfterDark Film LUT"
}
