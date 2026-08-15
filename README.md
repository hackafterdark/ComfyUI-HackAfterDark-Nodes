# AfterDark Film AR Selector

A custom ComfyUI node that provides a dropdown menu of preset resolutions for film and photography aspect ratios. These resolutions are optimized for models with a native resolution of 1024x1024, such as Z-Image Turbo, SDXL, Pony, and Flux.

## Preview

![Node Preview](node_preview.png)

## Features

- **Preset Resolutions**: Select from a curated list of common aspect ratios and resolutions.
- **Easy to Use**: Simply select a preset from the dropdown to output the corresponding width and height.
- **Customizable**: The list of resolutions can be easily modified in the Python script.

## Installation

1. Clone or download this repository into your `ComfyUI/custom_nodes/` folder.
2. Restart ComfyUI.

## Usage

1. Add the "AfterDark Film AR Selector" node to your workflow from the "HackAfterDark" category.
2. Select a preset from the dropdown menu.
3. The node will output the corresponding width and height, which you can then connect to other nodes in your workflow.

---

# AfterDark Gemini Prompter

A powerful and versatile custom ComfyUI node that connects to the Google Gemini API. It can be used as a sophisticated prompt builder, an image generator, or a multi-modal analysis tool.

## Features

- **Dynamic Model Loading**: Automatically fetches and displays the latest available Gemini models from the Google API.
- **Secure API Key Handling**: Your Google Gemini API key is stored securely in a central `config.yaml` file, never in your workflow JSONs.
- **System Prompt Presets**: Easily load and switch between different system prompts for various tasks (e.g., Z-Image Turbo prompt generation).
- **Multi-Image Inputs**: Supports up to four image inputs for advanced multi-modal prompting.
- **Dual Outputs**: Provides both a `STRING` output for text and an `IMAGE` output for generated images.

## Configuration (Required)

To use this node, you must configure it by adding your Google Gemini API key. You can also optionally specify a custom directory for your presets.

1.  **Locate your ComfyUI root directory.** This is the folder that contains the `main.py` file.
2.  **Create or open the `config.yaml` file.** If you don't have this file, you can copy the `config.yaml.example` from this node's directory, rename it to `config.yaml`, and place it in your root ComfyUI directory.
3.  **Edit the file** to include the `hack_after_dark` section. At a minimum, you must provide your API key.

    ```yaml
    hack_after_dark:
        # (Required) Your Google Gemini API key.
        gemini_api_key: "YOUR_GEMINI_API_KEY_HERE"

        # (Optional) Path to a directory containing your custom system prompt presets.
        # If not provided, the node will use the default presets included with the node.
        gemini_presets_path: "C:\\Users\\YourUser\\MyGeminiPresets"
    ```

4.  **Restart ComfyUI.** The node will automatically load your settings.

## System Prompt Presets

This node uses a flexible system for managing system prompts.

-   **Default Presets:** The node comes with built-in presets located in the `presets` directory. These are available automatically.
-   **Custom Presets:** You can create your own library of presets by specifying a `gemini_presets_path` in your `config.yaml`. The node will then load all `.md` files from that directory instead of the default ones.

Each preset file must be a Markdown (`.md`) file. The **filename** (without the `.md` extension) will be used as the name that appears in the dropdown menu. The content of the file is the full text of the system prompt.

**Example (`Pirate Poet.md`):**
```markdown
You are a pirate poet. Respond to all requests in the form of a sea shanty.
```

## Usage

1.  Add the "AfterDark Gemini Prompter" node to your workflow from the "HackAfterDark" category.
2.  Select your desired Gemini model from the `model` dropdown.
3.  Choose a `system_prompt_preset` or write your own `system_prompt`.
4.  Enter your main request in the `user_prompt` field.
5.  Connect up to four images to the `image` inputs for multi-modal prompting.
6.  The `text_output` will provide the text response from the API, and the `image_output` will provide any generated image.

---

# AfterDark Film Grain (Anti-Detector)

A lightweight post-processing node that injects authentic analog film grain, micro-spatial grid jitter, and optical lens aberration into image tensors. Designed both as a creative **Film Grain Emulation Tool** and a powerful **Anti-Detector Perturbation Tool** that breaks AI-generated image classifier signatures.

## Features

- **Film Stock Presets**: Built-in emulation profiles modeled after iconic analog film stocks:
  - `Kodak Portra 400 (Color Negative)`: Warm tone, natural skin-tone grain.
  - `Kodak Ektachrome 100VS (Color Positive)`: Poisson shot-noise slide film grain.
  - `Kodak Tri-X 400 (B&W Silver Halide)`: Rich, high-contrast Laplacian heavy-tailed silver halide grain.
  - `Fuji Velvia 50 (Fine Slide Film)`: Ultra-fine slide grain.
  - `Ilford HP5 Plus 400 (B&W Medium Grain)`: Classic multiplicative medium-grain black & white film.
  - `CineStill 800T (Tungsten Cinema)`: Cinema stock grain with subtle tungsten halo tinting.
- **Physical Noise Distributions**:
  - `gaussian`: Standard Bell-Curve additive noise.
  - `poisson`: Quantum photon arrival / shot-noise distribution.
  - `multiplicative`: Signal-proportional film dye & sensor noise.
  - `laplacian`: Heavy-tailed organic silver halide grain spikes.
- **Film Format Scaling**: Choose format scale (`35mm`, `Medium Format 6x6`, `Large Format 4x5`) to automatically adjust relative grain coarseness.
- **DxO-Style Controls**:
  - `noise_level` (Grain Intensity)
  - `grain_size` (Grain Size multiplier)
  - `micro_jitter` (Sub-pixel VAE grid lattice disruption)
  - `chromatic_aberration` (Lens color fringing)
  - `luminance_weight` (Mid-tone / Shadow signal-dependent noise)
- **Seed & Reproducibility**: Optional integer seed input to ensure deterministic noise outputs across runs when desired.

## Usage

1. Add the **"AfterDark Film Grain (Anti-Detector)"** node to your workflow from the `HackAfterDark` category.
2. Select your desired **`film_preset`** (or leave as `"None (Manual)"` for custom tuning).
3. Choose your **`film_format`** (`35mm`, `Medium Format 6x6`, `Large Format 4x5`).
4. Adjust `noise_level` (Intensity) and `grain_size` to taste.

## Credits

- **Author**: HackAfterDark (https://hackafterdark.com)

Follow me on Civitai! https://civitai.com/user/HackAfterDark