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

"""
@author: HackAfterDark
@title: Gemini Image Prompt Builder
@nickname: Gemini Prompter
@description: A node to generate image prompts or images using the Google Gemini API, with support for multiple images and presets.
"""

import os
import yaml
import requests
import traceback
import torch
import numpy as np
from PIL import Image
import google.generativeai as genai
from io import BytesIO

class GeminiImagePromptBuilder:
    _api_key = None
    _presets_path = None
    _models = []
    _presets = {}

    def __init__(self):
        # We don't need to load everything on startup anymore
        pass

    @classmethod
    def load_api_key(cls):
        if cls._api_key is None:
            try:
                import json
                settings_file = os.path.join(os.path.dirname(__file__), "hackafterdark_settings.json")
                if os.path.exists(settings_file):
                    with open(settings_file, 'r') as f:
                        settings = json.load(f)
                        api_key = settings.get("gemini_api_key")
                        if api_key:
                            cls._api_key = api_key
                            print("HackAfterDark: Gemini API key loaded from settings file.")
                        presets_path = settings.get("presets_path")
                        if presets_path and os.path.isdir(presets_path):
                            cls._presets_path = presets_path
                            print(f"HackAfterDark: Custom presets path loaded from settings: {presets_path}")
            except Exception as e:
                print(f"HackAfterDark: Error loading settings from file: {e}")

    @classmethod
    def load_models(cls):
        # Always try to load models if the list is empty and we have an API key.
        # This allows the list to populate after the user enters the key in settings.
        if not cls._models and cls._api_key:
            try:
                genai.configure(api_key=cls._api_key)
                cls._models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
                print(f"HackAfterDark: Loaded {len(cls._models)} Gemini models.")
            except Exception as e:
                print(f"HackAfterDark: Failed to load Gemini models: {e}")
                cls._models = [] # Ensure it's an empty list on failure

    @classmethod
    def load_presets(cls):
        if not cls._presets:
            presets_dir = cls._presets_path if cls._presets_path else os.path.join(os.path.dirname(os.path.abspath(__file__)), "presets")
            if os.path.isdir(presets_dir):
                for filename in os.listdir(presets_dir):
                    if filename.endswith(".md"):
                        file_path = os.path.join(presets_dir, filename)
                        try:
                            with open(file_path, 'r', encoding='utf-8') as f:
                                # Use the filename without extension as the key
                                preset_name = os.path.splitext(filename)[0]
                                cls._presets[preset_name] = f.read()
                        except Exception as e:
                            print(f"HackAfterDark: Error loading preset {filename}: {e}")
                print(f"HackAfterDark: Loaded {len(cls._presets)} presets from {presets_dir}.")

    @classmethod
    def INPUT_TYPES(cls):
        # We need to load fresh settings every time the node UI is drawn
        cls.load_api_key()
        cls.load_models()
        cls.load_presets()
        
        preset_names = ["None"] + list(cls._presets.keys())
        models = cls._models if cls._models else ["ERROR: No models found"]

        required_inputs = {
            "model": (models,),
            "system_prompt_preset": (preset_names,),
            "system_prompt": ("STRING", {"multiline": True, "default": ""}),
            "user_prompt": ("STRING", {"multiline": True, "default": ""}),
            "temperature": ("FLOAT", {"default": 0.9, "min": 0.0, "max": 1.0, "step": 0.01}),
        }

        if not cls._api_key:
            required_inputs["error"] = ("STRING", {"default": "API key not found. Please set it in the ComfyUI settings.", "multiline": True})

        return {
            "required": required_inputs,
            "optional": {
                "image1": ("IMAGE",), "image2": ("IMAGE",), "image3": ("IMAGE",), "image4": ("IMAGE",)
            }
        }

    RETURN_TYPES = ("STRING", "IMAGE")
    RETURN_NAMES = ("text_output", "image_output")
    FUNCTION = "execute"
    CATEGORY = "HackAfterDark"

    def _create_placeholder_image(self):
        """Create a 1x1 black placeholder image tensor for when no image is generated."""
        return torch.zeros((1, 1, 1, 3), dtype=torch.float32)

    def execute(self, model, system_prompt_preset, system_prompt, user_prompt, temperature, image1=None, image2=None, image3=None, image4=None):
        # Always reload the key on execute to get the latest version
        self.load_api_key()
        if not self._api_key:
            return ("ERROR: API key not found. Please set it in ComfyUI settings and restart.", self._create_placeholder_image())

        genai.configure(api_key=self._api_key)
        
        final_system_prompt = system_prompt
        
        # Handle preset selection - support both string and legacy list/tuple formats
        preset_key = system_prompt_preset
        if isinstance(system_prompt_preset, (list, tuple)):
            # Legacy format: ('Z-Image Turbo Prompter', '.md') - join to get filename, then strip extension
            preset_key = "".join(system_prompt_preset)
            if preset_key.endswith(".md"):
                preset_key = preset_key[:-3]
        
        # Use preset content if a preset is selected
        if preset_key != "None" and preset_key in self._presets:
            final_system_prompt = self._presets[preset_key]

        contents = [final_system_prompt, user_prompt]
        images = [img for img in [image1, image2, image3, image4] if img is not None]
        for tensor_image in images:
            # Correctly convert tensor to PIL Image
            # Squeeze to remove batch dimension, permute to HWC, and convert
            np_image = tensor_image.squeeze(0).cpu().numpy() * 255.0
            pil_image = Image.fromarray(np_image.astype(np.uint8), 'RGB')
            contents.append(pil_image)

        print(f"HackAfterDark: Calling Gemini model '{model}'...")
        print(f"HackAfterDark: System prompt length: {len(final_system_prompt)}, User prompt: '{user_prompt[:100] if user_prompt else ''}'")
        print(f"HackAfterDark: Number of images: {len(images)}")
        
        # Call the API
        try:
            gemini_model = genai.GenerativeModel(model)
            response = gemini_model.generate_content(contents, generation_config={"temperature": temperature})
        except Exception as api_err:
            print(f"HackAfterDark: API call failed: {api_err}")
            return (f"ERROR: API call failed - {api_err}", self._create_placeholder_image())
        
        # Check for blocked content first
        if hasattr(response, 'prompt_feedback'):
            feedback = response.prompt_feedback
            if hasattr(feedback, 'block_reason') and feedback.block_reason:
                block_msg = f"ERROR: Content blocked by Gemini. Reason: {feedback.block_reason}"
                print(f"HackAfterDark: {block_msg}")
                return (block_msg, self._create_placeholder_image())
        
        # Check if we have any candidates
        if not hasattr(response, 'candidates') or not response.candidates:
            return ("ERROR: No response generated. The prompt may have been blocked.", self._create_placeholder_image())
        
        print(f"HackAfterDark: Response received. Candidates: {len(response.candidates)}")
        
        # Extract text output
        text_output = ""
        try:
            text_output = response.text
            print(f"HackAfterDark: Text output length: {len(text_output)}")
        except Exception as text_err:
            print(f"HackAfterDark: Error getting text via .text: {text_err}")
            # Try to get text from candidates directly
            try:
                for candidate in response.candidates:
                    if hasattr(candidate, 'content') and hasattr(candidate.content, 'parts'):
                        for part in candidate.content.parts:
                            if hasattr(part, 'text') and part.text:
                                text_output += part.text
                print(f"HackAfterDark: Text from candidates: {len(text_output)}")
            except Exception as e2:
                print(f"HackAfterDark: Could not extract text from candidates: {e2}")
        
        # Extract image output (optional - errors won't affect text output)
        image_output = self._create_placeholder_image()
        try:
            for candidate in response.candidates:
                if hasattr(candidate, 'content') and hasattr(candidate.content, 'parts'):
                    for part in candidate.content.parts:
                        if hasattr(part, 'inline_data') and part.inline_data:
                            try:
                                image_data = part.inline_data.data
                                pil_image = Image.open(BytesIO(image_data))
                                np_image = np.array(pil_image).astype(np.float32) / 255.0
                                image_output = torch.from_numpy(np_image).unsqueeze(0)
                                print(f"HackAfterDark: Image generated: {pil_image.size}")
                            except Exception as img_parse_err:
                                print(f"HackAfterDark: Could not parse image data: {img_parse_err}")
                            break
        except Exception as img_err:
            print(f"HackAfterDark: Error extracting image: {img_err}")
            # Image extraction failed, but we still have text - continue
        
        if not text_output:
            text_output = "ERROR: No text response received from Gemini."
        else:
            # Strip markdown code fences and whitespace
            cleaned_text = text_output.strip()
            if cleaned_text.startswith("```") and cleaned_text.endswith("```"):
                # Find the first newline to handle ```json etc.
                start_index = cleaned_text.find('\n') + 1 if '\n' in cleaned_text[:5] else 3
                text_output = cleaned_text[start_index:-3].strip()
        
        print(f"HackAfterDark: Final text output length: {len(text_output)}")
        
        return (text_output, image_output)

NODE_CLASS_MAPPINGS = {"GeminiImagePromptBuilder": GeminiImagePromptBuilder}
NODE_DISPLAY_NAME_MAPPINGS = {"GeminiImagePromptBuilder": "AfterDark Gemini Prompter"}