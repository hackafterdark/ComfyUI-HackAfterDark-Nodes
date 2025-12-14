import { app } from "/scripts/app.js";
import { api } from "/scripts/api.js";

const GEMINI_API_KEY_ID = "HackAfterDark.GeminiApiKey";
const PRESETS_PATH_ID = "HackAfterDark.PresetsPath";

// Helper function to save settings to the backend
async function saveSettings(settings) {
    try {
        const resp = await api.fetchApi("/hackafterdark/settings", {
            method: "POST",
            body: JSON.stringify(settings),
        });
        if (resp.status !== 200) {
            console.error("Failed to save HackAfterDark settings.");
        }
    } catch (e) {
        console.error("Error saving HackAfterDark settings:", e);
    }
}

app.registerExtension({
    name: "HackAfterDark.Settings",
    async setup(app) {
        // API Key Setting
        const apiKeySetting = app.ui.settings.addSetting({
            id: GEMINI_API_KEY_ID,
            name: "Gemini API Key",
            type: "text",
            defaultValue: "",
            onChange: async (value) => {
                await saveSettings({ gemini_api_key: value, presets_path: presetsPathSetting.value });
            },
        });

        // Presets Path Setting
        const presetsPathSetting = app.ui.settings.addSetting({
            id: PRESETS_PATH_ID,
            name: "Prompt Template Directory",
            type: "text",
            defaultValue: "",
            onChange: async (value) => {
                await saveSettings({ gemini_api_key: apiKeySetting.value, presets_path: value });
            },
        });
        
        // Load the initial values from the backend
        try {
            const resp = await api.fetchApi("/hackafterdark/settings");
            if (resp.status === 200) {
                const settings = await resp.json();
                if (settings.gemini_api_key) {
                    apiKeySetting.value = settings.gemini_api_key;
                }
                if (settings.presets_path) {
                    presetsPathSetting.value = settings.presets_path;
                }
            }
        } catch (e) {
            console.error("Failed to load HackAfterDark settings:", e);
        }
    },
});