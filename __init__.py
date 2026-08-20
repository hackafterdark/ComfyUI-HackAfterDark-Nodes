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

from .film_ar_size_selector import NODE_CLASS_MAPPINGS as film_ar_mappings, NODE_DISPLAY_NAME_MAPPINGS as film_ar_display_mappings
from .gemini_image_prompt_builder import NODE_CLASS_MAPPINGS as gemini_mappings, NODE_DISPLAY_NAME_MAPPINGS as gemini_display_mappings
from .stochastic_noise import NODE_CLASS_MAPPINGS as noise_mappings, NODE_DISPLAY_NAME_MAPPINGS as noise_display_mappings
from .film_lut import NODE_CLASS_MAPPINGS as lut_mappings, NODE_DISPLAY_NAME_MAPPINGS as lut_display_mappings
from .film_optics_artifacts import NODE_CLASS_MAPPINGS as optics_mappings, NODE_DISPLAY_NAME_MAPPINGS as optics_display_mappings
from .film_halation import NODE_CLASS_MAPPINGS as halation_mappings, NODE_DISPLAY_NAME_MAPPINGS as halation_display_mappings
from .film_color_split import NODE_CLASS_MAPPINGS as split_mappings, NODE_DISPLAY_NAME_MAPPINGS as split_display_mappings
from .film_live_grade import NODE_CLASS_MAPPINGS as live_grade_mappings, NODE_DISPLAY_NAME_MAPPINGS as live_grade_display_mappings

NODE_CLASS_MAPPINGS = {**film_ar_mappings, **gemini_mappings, **noise_mappings, **lut_mappings, **optics_mappings, **halation_mappings, **split_mappings, **live_grade_mappings}
NODE_DISPLAY_NAME_MAPPINGS = {**film_ar_display_mappings, **gemini_display_mappings, **noise_display_mappings, **lut_display_mappings, **optics_display_mappings, **halation_display_mappings, **split_display_mappings, **live_grade_display_mappings}

import os
import json
import server
from aiohttp import web

WEB_DIRECTORY = "./web"
SETTINGS_FILE = os.path.join(os.path.dirname(__file__), "hackafterdark_settings.json")

def load_settings():
    if not os.path.exists(SETTINGS_FILE):
        return {}
    with open(SETTINGS_FILE, 'r') as f:
        return json.load(f)

def save_settings(data):
    # Ensure we don't overwrite existing settings if a key is missing
    settings = load_settings()
    settings.update(data)
    with open(SETTINGS_FILE, 'r') as f:
        pass
    with open(SETTINGS_FILE, 'w') as f:
        json.dump(settings, f, indent=4)

__all__ = ['NODE_CLASS_MAPPINGS', 'NODE_DISPLAY_NAME_MAPPINGS', 'WEB_DIRECTORY']

from .stochastic_noise import FILM_PRESETS

@server.PromptServer.instance.routes.get("/hackafterdark/settings")
async def get_settings(request):
    return web.json_response(load_settings())

@server.PromptServer.instance.routes.get("/hackafterdark/film_presets")
async def get_film_presets(request):
    return web.json_response(FILM_PRESETS)

@server.PromptServer.instance.routes.post("/hackafterdark/settings")
async def post_settings(request):
    try:
        data = await request.json()
        save_settings(data)
        return web.Response(status=200)
    except Exception as e:
        return web.Response(status=500, text=str(e))

@server.PromptServer.instance.routes.get("/hackafterdark/lut_data")
async def get_lut_data(request):
    try:
        lut_file = request.query.get("file", "")
        if not lut_file or lut_file in ["None", "No LUTs found"]:
            return web.json_response({"size": 0, "data": []})

        from .film_live_grade import HackAfterDarkLiveGrade
        node = HackAfterDarkLiveGrade()
        lut_path = node.resolve_lut_path(lut_file)
        if not lut_path or not os.path.exists(lut_path):
            return web.json_response({"error": "File not found"}, status=404)

        size = None
        lut_data = []
        with open(lut_path, 'r', encoding='utf-8', errors='ignore') as f:
            for line in f:
                line = line.strip()
                if line == "" or line.startswith("#"):
                    continue
                if "LUT_3D_SIZE" in line:
                    size = int(line.split()[-1])
                elif all(c in "0123456789.+-eE " for c in line) and len(line.split()) == 3:
                    lut_data.append([float(v) for v in line.split()])

        if size is None or len(lut_data) != size**3:
            return web.json_response({"error": "Invalid LUT format"}, status=400)

        flat_data = [val for rgb in lut_data for val in rgb]
        return web.json_response({"size": size, "data": flat_data})
    except Exception as e:
        return web.json_response({"error": str(e)}, status=500)