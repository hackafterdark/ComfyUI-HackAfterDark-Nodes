import { app } from "/scripts/app.js";
import { api } from "/scripts/api.js";

let filmPresets = null;

async function fetchPresets() {
    if (filmPresets) return filmPresets;
    try {
        const resp = await api.fetchApi("/hackafterdark/film_presets");
        if (resp.status === 200) {
            filmPresets = await resp.json();
        }
    } catch (e) {
        console.error("Failed to fetch HackAfterDark film presets:", e);
    }
    return filmPresets || {};
}

app.registerExtension({
    name: "HackAfterDark.FilmGrainPresets",
    async nodeCreated(node) {
        if (node.comfyClass !== "AfterDarkStochasticNoise") return;

        const presets = await fetchPresets();

        const findWidget = (name) => node.widgets?.find((w) => w.name === name);

        const presetWidget = findWidget("film_preset");
        const grainSizeWidget = findWidget("grain_size");
        const noiseTypeWidget = findWidget("noise_type");
        const microJitterWidget = findWidget("micro_jitter");
        const aberrationWidget = findWidget("chromatic_aberration");
        const warmthWidget = findWidget("tone_warmth");

        if (!presetWidget) return;

        let isUpdatingFromPreset = false;

        // Callback when preset dropdown changes
        const origPresetCallback = presetWidget.callback;
        presetWidget.callback = function (value) {
            if (origPresetCallback) origPresetCallback.apply(this, arguments);

            if (value && value !== "None (Manual)" && presets[value]) {
                const cfg = presets[value];
                isUpdatingFromPreset = true;

                if (grainSizeWidget && cfg.base_grain_size !== undefined) {
                    grainSizeWidget.value = cfg.base_grain_size;
                }
                if (noiseTypeWidget && cfg.noise_type !== undefined) {
                    noiseTypeWidget.value = cfg.noise_type;
                }
                if (microJitterWidget && cfg.base_jitter !== undefined) {
                    microJitterWidget.value = cfg.base_jitter;
                }
                if (aberrationWidget && cfg.base_aberration !== undefined) {
                    aberrationWidget.value = cfg.base_aberration;
                }
                if (warmthWidget && cfg.tone_warmth !== undefined) {
                    warmthWidget.value = cfg.tone_warmth;
                }

                isUpdatingFromPreset = false;
                app.graph.setDirtyCanvas(true, true);
            }
        };

        // Attach listeners to manual inputs so tweaking any parameter switches preset to "None (Manual)"
        const manualWidgets = [
            grainSizeWidget,
            noiseTypeWidget,
            microJitterWidget,
            aberrationWidget,
            warmthWidget,
            findWidget("noise_level"),
            findWidget("channel_mode"),
            findWidget("spatial_resample"),
            findWidget("gamma_shift"),
            findWidget("edge_softening"),
            findWidget("luminance_response"),
            findWidget("film_format")
        ].filter(Boolean);

        manualWidgets.forEach((w) => {
            const origCb = w.callback;
            w.callback = function (v) {
                if (origCb) origCb.apply(this, arguments);
                if (!isUpdatingFromPreset && presetWidget.value !== "None (Manual)") {
                    presetWidget.value = "None (Manual)";
                    app.graph.setDirtyCanvas(true, true);
                }
            };
        });
    }
});
