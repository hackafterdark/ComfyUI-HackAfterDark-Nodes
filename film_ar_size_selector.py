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
        "960x1120 (MF 6x7 Portrait)",
        "864x1152 (MF 645 Portrait)",
        "832x1248 (35mm Portrait)",
        "768x1344 (9:16 Portrait)",
        "--- Landscape ---",
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
        "1920x512 (Super Ultrawide)"
    ]

    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "preset": (s.resolutions,),
            }
        }

    RETURN_TYPES = ("INT", "INT")
    RETURN_NAMES = ("width", "height")
    FUNCTION = "get_size"
    CATEGORY = "HackAfterDark"

    def get_size(self, preset):
        if preset.startswith("---"):
            # Find the next valid resolution
            current_index = self.resolutions.index(preset)
            next_index = current_index + 1
            while self.resolutions[next_index].startswith("---"):
                next_index += 1
            preset = self.resolutions[next_index]

        # The preset comes in as a list, so we take the first element
        resolution_str = preset
        width_str, _ = resolution_str.split(' ', 1)
        width, height = [int(x) for x in width_str.split('x')]
        return (width, height)

NODE_CLASS_MAPPINGS = {
    "FilmARSizeSelector": FilmARSizeSelector
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "FilmARSizeSelector": "AfterDark Film AR Selector"
}