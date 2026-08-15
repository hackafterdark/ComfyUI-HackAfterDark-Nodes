# Author: HackAfterDark
# Version: 1.0
# Title: Film Aspect Ratio & Size Selector
# Description: A custom node for ComfyUI that provides a dropdown menu of preset resolutions for film and photography aspect ratios.
# Copyright 2025 HackAfterDark
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

class FilmARSizeSelector:
    resolutions = [
        "--- Portrait ---",
        "1024x1024 (Square / MF 6x6)",
        "864x1152 (3:4 Classic Portrait)",
        "960x1120 (MF 6x7 Portrait)",
        "864x1152 (MF 645 Portrait)",
        "832x1248 (35mm Portrait)",
        "768x1344 (9:16 Portrait)",
        "--- Landscape ---",
        "1152x864 (4:3 Classic Landscape)",
        "1120x960 (MF 6x7 Landscape)",
        "1152x864 (MF 645 Landscape)",
        "1248x832 (35mm Landscape)",
        "--- Cinematic ---",
        "1152x832 (Academy Ratio)",
        "1024x704 (IMAX 70mm)",
        "1344x768 (16:9 Widescreen)",
        "1408x768 (1.85:1 Cinema Film)",
        "1472x768 (DCI 4K)",
        "1536x704 (Standard 70mm Film)",
        "1568x672 (21:9 Ultrawide)",
        "1504x640 (2.35:1 Cinemascope)",
        "1536x640 (2.40:1 Cinematic Ultrawide)",
        "1728x640 (XPan Panoramic)",
        "1792x640 (MGM 65 / Ultra Panavision)",
        "1920x512 (Super Ultrawide)",
        "--- Print ---",
        "896x1120 (4:5 Print / 8x10 Portrait)",
        "1120x896 (5:4 Print / 10x8 Landscape)",
        "800x1120 (5:7 Print Portrait)",
        "1120x800 (7:5 Print Landscape)",
        "--- Custom ---",
        "Custom (Manual Override)"
    ]

    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "resolution_preset": (s.resolutions,),
            },
            "optional": {
                "custom_width": ("INT", {"default": 0, "min": 0, "max": 8192, "step": 8}),
                "custom_height": ("INT", {"default": 0, "min": 0, "max": 8192, "step": 8}),
            }
        }

    RETURN_TYPES = ("INT", "INT")
    RETURN_NAMES = ("width", "height")
    FUNCTION = "get_size"
    CATEGORY = "HackAfterDark"

    def get_size(self, resolution_preset, custom_width=0, custom_height=0):
        if resolution_preset.startswith("---"):
            # Find the next valid resolution
            current_index = self.resolutions.index(resolution_preset)
            next_index = (current_index + 1) % len(self.resolutions)
            while self.resolutions[next_index].startswith("---"):
                next_index = (next_index + 1) % len(self.resolutions)
            resolution_preset = self.resolutions[next_index]

        if resolution_preset == "Custom (Manual Override)":
            preset_w, preset_h = 1024, 1024
        else:
            resolution_str = resolution_preset
            width_str, _ = resolution_str.split(' ', 1)
            preset_w, preset_h = [int(x) for x in width_str.split('x')]

        width = custom_width if custom_width > 0 else preset_w
        height = custom_height if custom_height > 0 else preset_h

        return (width, height)

NODE_CLASS_MAPPINGS = {
    "FilmARSizeSelector": FilmARSizeSelector
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "FilmARSizeSelector": "AfterDark Film AR Selector"
}