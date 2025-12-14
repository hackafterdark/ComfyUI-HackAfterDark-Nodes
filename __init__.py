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

from .film_ar_size_selector import NODE_CLASS_MAPPINGS as film_ar_mappings, NODE_DISPLAY_NAME_MAPPINGS as film_ar_display_mappings
from .gemini_image_prompt_builder import NODE_CLASS_MAPPINGS as gemini_mappings, NODE_DISPLAY_NAME_MAPPINGS as gemini_display_mappings

NODE_CLASS_MAPPINGS = {**film_ar_mappings, **gemini_mappings}
NODE_DISPLAY_NAME_MAPPINGS = {**film_ar_display_mappings, **gemini_display_mappings}

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
    with open(SETTINGS_FILE, 'w') as f:
        json.dump(settings, f, indent=4)

__all__ = ['NODE_CLASS_MAPPINGS', 'NODE_DISPLAY_NAME_MAPPINGS', 'WEB_DIRECTORY']

@server.PromptServer.instance.routes.get("/hackafterdark/settings")
async def get_settings(request):
    return web.json_response(load_settings())

@server.PromptServer.instance.routes.post("/hackafterdark/settings")
async def post_settings(request):
    try:
        data = await request.json()
        save_settings(data)
        return web.Response(status=200)
    except Exception as e:
        return web.Response(status=500, text=str(e))