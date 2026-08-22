import { app } from "/scripts/app.js";
import { api } from "/scripts/api.js";

// Exact Parameter Min/Max Bounds Map matching film_live_grade.py
const PARAM_BOUNDS = {
    lut_strength: { min: 0.0, max: 1.0 },
    strength: { min: 0.0, max: 1.0 },
    exposure: { min: -3.0, max: 3.0 },
    contrast: { min: 0.5, max: 1.5 },
    black_lift: { min: -0.5, max: 0.5 },
    hue: { min: -180.0, max: 180.0 },
    saturation: { min: 0.0, max: 2.0 },
    tint_green_magenta: { min: -1.0, max: 1.0 },
    tint_amber_blue: { min: -1.0, max: 1.0 },
    shadow_intensity: { min: 0.0, max: 1.0 },
    highlight_intensity: { min: 0.0, max: 1.0 },
    balance: { min: -1.0, max: 1.0 },
    micro_contrast: { min: 0.0, max: 1.0 },
    clarity: { min: 0.0, max: 1.0 }
};

function getWidgetBounds(widget) {
    const name = widget.name;
    if (PARAM_BOUNDS[name]) {
        const b = PARAM_BOUNDS[name];
        const min = widget.options?.min !== undefined ? widget.options.min : b.min;
        const max = widget.options?.max !== undefined ? widget.options.max : b.max;
        return { min, max };
    }
    const min = widget.options?.min !== undefined ? widget.options.min : 0.0;
    const max = widget.options?.max !== undefined ? widget.options.max : 1.0;
    return { min, max };
}

// Cache for fetched 3D LUT data
const lutCache = new Map();
let currentLightbox = null;

async function fetchLutData(lutFile) {
    if (!lutFile || lutFile === "None" || lutFile === "No LUTs found") {
        return null;
    }
    if (lutCache.has(lutFile)) {
        return lutCache.get(lutFile);
    }
    try {
        const resp = await api.fetchApi("/hackafterdark/lut_data?file=" + encodeURIComponent(lutFile));
        if (resp.status === 200) {
            const lutJson = await resp.json();
            if (lutJson.size && lutJson.data) {
                lutCache.set(lutFile, lutJson);
                return lutJson;
            }
        }
    } catch (e) {
        console.error("[HackAfterDarkLiveGrade] Failed to fetch LUT data:", e);
    }
    return null;
}

function sampleLut(r, g, b, lut) {
    const N = lut.size;
    if (!N || N < 2) return [r, g, b];
    const data = lut.data;

    const x = Math.max(0, Math.min(1, r)) * (N - 1);
    const y = Math.max(0, Math.min(1, g)) * (N - 1);
    const z = Math.max(0, Math.min(1, b)) * (N - 1);

    const x0 = Math.floor(x);
    const x1 = Math.min(x0 + 1, N - 1);
    const dx = x - x0;

    const y0 = Math.floor(y);
    const y1 = Math.min(y0 + 1, N - 1);
    const dy = y - y0;

    const z0 = Math.floor(z);
    const z1 = Math.min(z0 + 1, N - 1);
    const dz = z - z0;

    const getVal = (rx, gy, bz) => {
        const idx = (bz * N * N + gy * N + rx) * 3;
        return [data[idx], data[idx + 1], data[idx + 2]];
    };

    const c000 = getVal(x0, y0, z0);
    const c100 = getVal(x1, y0, z0);
    const c010 = getVal(x0, y1, z0);
    const c110 = getVal(x1, y1, z0);
    const c001 = getVal(x0, y0, z1);
    const c101 = getVal(x1, y0, z1);
    const c011 = getVal(x0, y1, z1);
    const c111 = getVal(x1, y1, z1);

    const c00 = [
        c000[0] + dx * (c100[0] - c000[0]),
        c000[1] + dx * (c100[1] - c000[1]),
        c000[2] + dx * (c100[2] - c000[2])
    ];
    const c10 = [
        c010[0] + dx * (c110[0] - c010[0]),
        c010[1] + dx * (c110[1] - c010[1]),
        c010[2] + dx * (c110[2] - c010[2])
    ];
    const c01 = [
        c001[0] + dx * (c101[0] - c001[0]),
        c001[1] + dx * (c101[1] - c001[1]),
        c001[2] + dx * (c101[2] - c001[2])
    ];
    const c11 = [
        c011[0] + dx * (c111[0] - c011[0]),
        c011[1] + dx * (c111[1] - c011[1]),
        c011[2] + dx * (c111[2] - c011[2])
    ];

    const c0 = [
        c00[0] + dy * (c10[0] - c00[0]),
        c00[1] + dy * (c10[1] - c00[1]),
        c00[2] + dy * (c10[2] - c00[2])
    ];
    const c1 = [
        c01[0] + dy * (c11[0] - c01[0]),
        c01[1] + dy * (c11[1] - c01[1]),
        c01[2] + dy * (c11[2] - c01[2])
    ];

    return [
        c0[0] + dz * (c1[0] - c0[0]),
        c0[1] + dz * (c1[0] - c0[0]),
        c0[2] + dz * (c1[2] - c0[2])
    ];
}

function rgbToHsv(r, g, b) {
    const max = Math.max(r, g, b);
    const min = Math.min(r, g, b);
    const d = max - min;
    const v = max;
    const s = max === 0 ? 0 : d / max;
    let h = 0;

    if (max !== min) {
        if (max === r) h = (g - b) / d + (g < b ? 6 : 0);
        else if (max === g) h = (b - r) / d + 2;
        else if (max === b) h = (r - g) / d + 4;
        h /= 6;
    }
    return [h, s, v];
}

function hsvToRgb(h, s, v) {
    let r, g, b;
    const i = Math.floor(h * 6);
    const f = h * 6 - i;
    const p = v * (1 - s);
    const q = v * (1 - f * s);
    const t = v * (1 - (1 - f) * s);

    switch (i % 6) {
        case 0: r = v; g = t; b = p; break;
        case 1: r = q; g = v; b = p; break;
        case 2: r = p; g = v; b = t; break;
        case 3: r = p; g = q; b = v; break;
        case 4: r = t; g = p; b = v; break;
        case 5: r = v; g = p; b = q; break;
    }
    return [r, g, b];
}

// Lightbox Overlay Asset Viewer Modal
function openLightbox(initialMode, node) {
    if (currentLightbox) {
        currentLightbox.close();
    }

    const state = node.liveGradeState;
    if (!state || !state.hasImage) return;

    let activeMode = initialMode; // 'before' or 'after'

    const overlay = document.createElement("div");
    overlay.id = "hackafterdark-lightbox-overlay";
    overlay.style.cssText = `
        position: fixed;
        top: 0;
        left: 0;
        width: 100vw;
        height: 100vh;
        background: rgba(10, 12, 16, 0.88);
        backdrop-filter: blur(10px);
        -webkit-backdrop-filter: blur(10px);
        z-index: 99999;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        font-family: Inter, system-ui, -apple-system, sans-serif;
        user-select: none;
    `;

    // Top Controls Bar
    const header = document.createElement("div");
    header.style.cssText = `
        position: absolute;
        top: 24px;
        display: flex;
        align-items: center;
        gap: 12px;
        background: rgba(24, 27, 35, 0.92);
        padding: 8px 18px;
        border-radius: 30px;
        border: 1px solid rgba(255, 255, 255, 0.15);
        box-shadow: 0 12px 32px rgba(0, 0, 0, 0.6);
        z-index: 100000;
    `;

    const btnBefore = document.createElement("button");
    btnBefore.innerHTML = "BEFORE (Original)";
    btnBefore.style.cssText = `
        border: none;
        padding: 8px 18px;
        border-radius: 20px;
        font-weight: 600;
        font-size: 13px;
        cursor: pointer;
        transition: all 0.15s ease;
    `;

    const btnAfter = document.createElement("button");
    btnAfter.innerHTML = "AFTER (Color Graded)";
    btnAfter.style.cssText = `
        border: none;
        padding: 8px 18px;
        border-radius: 20px;
        font-weight: 600;
        font-size: 13px;
        cursor: pointer;
        transition: all 0.15s ease;
    `;

    const hintText = document.createElement("span");
    hintText.innerText = "Use ← → Arrow keys to switch";
    hintText.style.cssText = "color: #9CA3AF; font-size: 12px; margin: 0 8px;";

    const btnClose = document.createElement("button");
    btnClose.innerText = "✕";
    btnClose.style.cssText = `
        background: rgba(255, 255, 255, 0.12);
        color: #F3F4F6;
        border: none;
        width: 30px;
        height: 30px;
        border-radius: 50%;
        font-size: 14px;
        cursor: pointer;
        display: flex;
        align-items: center;
        justify-content: center;
        margin-left: 8px;
    `;

    header.appendChild(btnBefore);
    header.appendChild(btnAfter);
    header.appendChild(hintText);
    header.appendChild(btnClose);

    // Main Viewport Container
    const imgContainer = document.createElement("div");
    imgContainer.style.cssText = `
        max-width: 92vw;
        max-height: 84vh;
        display: flex;
        align-items: center;
        justify-content: center;
        position: relative;
    `;

    const imgElem = document.createElement("img");
    imgElem.style.cssText = `
        max-width: 92vw;
        max-height: 82vh;
        object-fit: contain;
        border-radius: 10px;
        box-shadow: 0 24px 60px rgba(0, 0, 0, 0.85);
        border: 1px solid rgba(255, 255, 255, 0.18);
        transition: opacity 0.1s ease;
    `;

    imgContainer.appendChild(imgElem);

    overlay.appendChild(header);
    overlay.appendChild(imgContainer);

    const updateView = () => {
        if (activeMode === "before") {
            imgElem.src = state.origCanvas ? state.origCanvas.toDataURL() : (state.origImg ? state.origImg.src : "");
            btnBefore.style.background = "#374151";
            btnBefore.style.color = "#FFFFFF";
            btnAfter.style.background = "transparent";
            btnAfter.style.color = "#9CA3AF";
        } else {
            imgElem.src = state.gradedCanvas ? state.gradedCanvas.toDataURL() : (state.origImg ? state.origImg.src : "");
            btnAfter.style.background = "#10B981";
            btnAfter.style.color = "#FFFFFF";
            btnBefore.style.background = "transparent";
            btnBefore.style.color = "#9CA3AF";
        }
    };

    btnBefore.onclick = (e) => {
        e.stopPropagation();
        activeMode = "before";
        updateView();
    };

    btnAfter.onclick = (e) => {
        e.stopPropagation();
        activeMode = "after";
        updateView();
    };

    const closeSelf = () => {
        window.removeEventListener("keydown", handleKeyDown);
        if (overlay.parentNode) {
            overlay.parentNode.removeChild(overlay);
        }
        if (currentLightbox && currentLightbox.overlay === overlay) {
            currentLightbox = null;
        }
    };

    btnClose.onclick = (e) => {
        e.stopPropagation();
        closeSelf();
    };

    overlay.onclick = (e) => {
        if (e.target === overlay || e.target === imgContainer) {
            closeSelf();
        }
    };

    const handleKeyDown = (e) => {
        if (e.key === "ArrowLeft" || e.key === "ArrowUp") {
            e.preventDefault();
            activeMode = "before";
            updateView();
        } else if (e.key === "ArrowRight" || e.key === "ArrowDown" || e.key === " ") {
            e.preventDefault();
            activeMode = "after";
            updateView();
        } else if (e.key === "Escape") {
            e.preventDefault();
            closeSelf();
        }
    };

    window.addEventListener("keydown", handleKeyDown);
    document.body.appendChild(overlay);

    currentLightbox = {
        overlay,
        close: closeSelf,
        update: updateView,
        node
    };

    updateView();
}

// Upstream Graph Inspector to find source image without workflow execution
function findUpstreamImageUrl(node, visited = new Set()) {
    if (!node || visited.has(node.id)) return null;
    visited.add(node.id);

    const input = node.inputs?.find(i => i.name === "image" || i.type === "IMAGE");
    if (!input || input.link == null) return null;

    if (!app.graph || !app.graph.links) return null;
    const link = app.graph.links[input.link];
    if (!link) return null;

    const originNode = app.graph.getNodeById(link.origin_id);
    if (!originNode) return null;

    // A. Check LoadImage node
    if (originNode.comfyClass === "LoadImage") {
        const imgWidget = originNode.widgets?.find(w => w.name === "image");
        if (imgWidget && imgWidget.value) {
            return api.apiURL("/view?filename=" + encodeURIComponent(imgWidget.value) + "&type=input");
        }
    }

    // B. Check rendered preview images on originNode
    if (originNode.imgs && originNode.imgs.length > 0 && originNode.imgs[0].src) {
        return originNode.imgs[0].src;
    }
    if (originNode.previewImages && originNode.previewImages.length > 0 && originNode.previewImages[0].src) {
        return originNode.previewImages[0].src;
    }

    // C. Check image widget on originNode
    if (originNode.widgets) {
        for (const w of originNode.widgets) {
            if (w.type === "image" && w.value && typeof w.value === "object" && w.value.filename) {
                return api.apiURL("/view?" + new URLSearchParams(w.value).toString());
            }
        }
    }

    // D. Recurse upstream
    return findUpstreamImageUrl(originNode, visited);
}

// Helper to compute Left Control Stack Column width dynamically
function getLeftColWidth(node) {
    const w = node.size ? node.size[0] : 860;
    return Math.max(260, Math.min(360, Math.floor(w * 0.42)));
}

// Bulletproof Widget Setup Function: Re-binds all custom handlers on every frame / configuration load
function setupCustomWidgets(node) {
    // 1. Patch LiteGraph canvas processNodeWidgets & processMouseMove globally
    if (app.canvas && !app.canvas._hackafterdark_patched) {
        app.canvas._hackafterdark_patched = true;

        const origProcessNodeWidgets = app.canvas.processNodeWidgets;
        app.canvas.processNodeWidgets = function (nodeRef, pos, event, active_widget) {
            if (nodeRef && nodeRef.comfyClass === "HackAfterDarkLiveGrade") {
                const lW = getLeftColWidth(nodeRef);
                if (pos && pos[0] > lW + 5 && pos[1] >= 30) {
                    // Click is in Right Column Preview Area below title bar! Block LiteGraph widget processing!
                    return true;
                }
                const res = origProcessNodeWidgets ? origProcessNodeWidgets.apply(this, arguments) : false;
                // Permanently clear LiteGraph's default node_widget_drag so LiteGraph built-in slider drag NEVER runs!
                this.node_widget_drag = null;
                return res;
            }
            if (origProcessNodeWidgets) {
                return origProcessNodeWidgets.apply(this, arguments);
            }
            return false;
        };

        const origProcessMouseMove = app.canvas.processMouseMove;
        app.canvas.processMouseMove = function (e) {
            // Intercept mouse move to neutralize any stray LiteGraph widget drag state for LiveGrade
            if (this.node_widget_drag && this.node_widget_drag[0] && this.node_widget_drag[0].comfyClass === "HackAfterDarkLiveGrade") {
                this.node_widget_drag = null;
            }
            if (origProcessMouseMove) return origProcessMouseMove.apply(this, arguments);
        };
    }

    if (!node.widgets || node.widgets.length === 0) return;
    const leftColW = getLeftColWidth(node);

    node.widgets.forEach(widget => {
        if (!widget.origType) {
            widget.origType = widget.type;
        }

        // Restrict HTML DOM elements overlay width to left control column if created by ComfyUI
        if (widget.element) {
            widget.element.style.width = (leftColW - 24) + "px";
            widget.element.style.maxWidth = (leftColW - 24) + "px";
        }
        if (widget.inputEl) {
            widget.inputEl.style.width = (leftColW - 24) + "px";
            widget.inputEl.style.maxWidth = (leftColW - 24) + "px";
        }

        widget.width = leftColW - 24;

        // Override widget.type to custom so LiteGraph NEVER draws a 100%-wide built-in background box
        if (["tint_green_magenta", "tint_amber_blue", "hue"].includes(widget.name)) {
            widget.type = "custom_spectrum_slider";
        } else {
            widget.type = "custom_livegrade_widget";
        }

        widget.computeSize = function (width) {
            const lW = getLeftColWidth(node);
            const isSpectrum = ["hue", "tint_green_magenta", "tint_amber_blue"].includes(this.name);
            return [lW, isSpectrum ? 38 : 22];
        };

        // Shared Helper to start global 1:1 window pointer dragging
        const startSliderDrag = (targetWidget, targetNode, initialPos, event) => {
            const margin = 12;
            const lW = getLeftColWidth(targetNode);
            const wW = lW - margin * 2;
            const relX = Math.max(0, Math.min(wW, initialPos[0] - margin));
            const pct = relX / wW;

            const { min, max } = getWidgetBounds(targetWidget);
            let rawVal = Math.max(min, Math.min(max, min + pct * (max - min)));

            targetWidget.value = rawVal;
            if (targetWidget.callback) targetWidget.callback(targetWidget.value, targetNode);
            targetNode.updateClientLivePreview();
            targetNode.setDirtyCanvas(true, true);

            targetNode.activeDraggingWidget = targetWidget;
            targetNode.mouseDownPos = [event.clientX, event.clientY];
            targetNode.isClickOnly = true;

            if (app.canvas) app.canvas.node_widget_drag = null;

            const handleWindowPointerMove = (e) => {
                if (!targetNode.activeDraggingWidget) return;

                if (targetNode.mouseDownPos) {
                    const dist = Math.hypot(e.clientX - targetNode.mouseDownPos[0], e.clientY - targetNode.mouseDownPos[1]);
                    if (dist > 3) {
                        targetNode.isClickOnly = false;
                    }
                }

                const canvasElem = app.canvas ? app.canvas.canvas : null;
                if (!canvasElem || !app.canvas.ds) return;

                const rect = canvasElem.getBoundingClientRect();
                const scale = app.canvas.ds.scale || 1.0;
                const offset = app.canvas.ds.offset || [0, 0];

                const canvasX = (e.clientX - rect.left) / scale - offset[0];
                const nodeX = canvasX - targetNode.pos[0];

                const currentLW = getLeftColWidth(targetNode);
                const trackW = currentLW - margin * 2;

                const rX = Math.max(0, Math.min(trackW, nodeX - margin));
                const p = rX / trackW;

                const w = targetNode.activeDraggingWidget;
                const { min, max } = getWidgetBounds(w);
                let val = Math.max(min, Math.min(max, min + p * (max - min)));

                w.value = val;
                if (w.callback) w.callback(w.value, targetNode);
                targetNode.updateClientLivePreview();
                targetNode.setDirtyCanvas(true, true);

                if (app.canvas) app.canvas.node_widget_drag = null;
            };

            const handleWindowPointerUp = (e) => {
                window.removeEventListener("pointermove", handleWindowPointerMove);
                window.removeEventListener("pointerup", handleWindowPointerUp);

                if (!targetNode.activeDraggingWidget) return;

                const w = targetNode.activeDraggingWidget;
                const isClick = targetNode.isClickOnly;

                targetNode.activeDraggingWidget = null;
                targetNode.mouseDownPos = null;
                targetNode.isClickOnly = false;

                if (app.canvas) app.canvas.node_widget_drag = null;

                // Single Click Prompt Dialog to type exact value
                if (isClick && w && (w.origType === "number" || w.origType === "slider" || typeof w.value === "number")) {
                    const canvasObj = app.canvas;
                    if (canvasObj && canvasObj.prompt) {
                        canvasObj.prompt("Value", w.value, (val) => {
                            const num = parseFloat(val);
                            if (!isNaN(num)) {
                                const { min, max } = getWidgetBounds(w);
                                let clamped = Math.max(min, Math.min(max, num));
                                w.value = clamped;
                                if (w.callback) w.callback(w.value, targetNode);
                                targetNode.updateClientLivePreview();
                                targetNode.setDirtyCanvas(true, true);
                            }
                        }, e);
                    }
                }

                targetNode.setDirtyCanvas(true, true);
            };

            window.addEventListener("pointermove", handleWindowPointerMove);
            window.addEventListener("pointerup", handleWindowPointerUp);
        };

        if (["tint_green_magenta", "tint_amber_blue", "hue"].includes(widget.name)) {
            widget.draw = function (ctx, nodeRef, widget_width, y, widget_height) {
                const lW = getLeftColWidth(nodeRef || node);
                const margin = 12;
                const trackX = margin;
                const trackY = y + 18;
                const trackW = lW - margin * 2;
                const trackH = 14;

                ctx.save();

                // 1. Left Label Header
                ctx.font = "bold 11px Inter, sans-serif";
                ctx.fillStyle = "#CCCCCC";
                ctx.textAlign = "left";
                const displayName = this.name.toUpperCase().replace(/_/g, " ");
                ctx.fillText(displayName, trackX, y + 12);

                // 2. Right Side: Value Display
                const val = this.value !== undefined ? this.value : 0;
                let valStr = "";
                if (this.name === "hue") {
                    valStr = Math.round(val) + "°";
                } else {
                    valStr = Number(val).toFixed(2);
                }

                ctx.font = "bold 11px Inter, sans-serif";
                ctx.textAlign = "right";
                ctx.fillStyle = "#10B981";
                ctx.fillText(valStr, trackX + trackW, y + 12);

                // 3. Thick Spectrum Color Track
                const grad = ctx.createLinearGradient(trackX, 0, trackX + trackW, 0);
                if (this.name === "tint_green_magenta") {
                    grad.addColorStop(0.00, "#10B981");
                    grad.addColorStop(0.50, "#374151");
                    grad.addColorStop(1.00, "#EC4899");
                } else if (this.name === "tint_amber_blue") {
                    grad.addColorStop(0.00, "#F59E0B");
                    grad.addColorStop(0.50, "#374151");
                    grad.addColorStop(1.00, "#3B82F6");
                } else if (this.name === "hue") {
                    grad.addColorStop(0.00, "#FF0000");
                    grad.addColorStop(0.17, "#FFFF00");
                    grad.addColorStop(0.33, "#00FF00");
                    grad.addColorStop(0.50, "#00FFFF");
                    grad.addColorStop(0.67, "#0000FF");
                    grad.addColorStop(0.83, "#FF00FF");
                    grad.addColorStop(1.00, "#FF0000");
                }

                ctx.fillStyle = grad;
                ctx.beginPath();
                ctx.roundRect(trackX, trackY, trackW, trackH, 6);
                ctx.fill();

                // Center Zero Tick Mark
                const centerX = trackX + trackW / 2;
                ctx.fillStyle = "rgba(255, 255, 255, 0.5)";
                ctx.fillRect(centerX - 1, trackY, 2, trackH);

                ctx.strokeStyle = "rgba(255, 255, 255, 0.25)";
                ctx.lineWidth = 1;
                ctx.stroke();

                // 4. Indicator Thumb
                const { min, max } = getWidgetBounds(this);
                const pct = Math.max(0, Math.min(1, (val - min) / (max - min)));

                const markerX = trackX + pct * trackW;
                const markerY = trackY - 2;
                const markerW = 6;
                const markerH = trackH + 4;

                ctx.fillStyle = "#FFFFFF";
                ctx.shadowColor = "rgba(0, 0, 0, 0.8)";
                ctx.shadowBlur = 4;
                ctx.beginPath();
                ctx.roundRect(markerX - markerW / 2, markerY, markerW, markerH, 3);
                ctx.fill();

                ctx.strokeStyle = "#111827";
                ctx.lineWidth = 1;
                ctx.stroke();

                ctx.restore();
            };

            widget.mouse = function (event, pos, nodeRef) {
                const targetNode = nodeRef || node;
                const lW = getLeftColWidth(targetNode);

                // Hard Lock: Return true for Right Column clicks so LiteGraph fallback never runs!
                if (pos[0] > lW + 5) {
                    if (app.canvas) app.canvas.node_widget_drag = null;
                    return true;
                }

                if (event.type === "pointerdown" || event.type === "mousedown") {
                    startSliderDrag(this, targetNode, pos, event);
                    return true;
                }
                return false;
            };
        } else {
            widget.draw = function (ctx, nodeRef, widget_width, y, widget_height) {
                const lW = getLeftColWidth(nodeRef || node);
                const margin = 12;
                const wX = margin;
                const wW = lW - margin * 2;
                const h = widget_height || 22;

                ctx.save();

                // Modern Pill Container Box (Rendered strictly inside leftColW)
                ctx.fillStyle = "rgba(24, 27, 35, 0.88)";
                ctx.strokeStyle = "rgba(255, 255, 255, 0.12)";
                ctx.lineWidth = 1;
                ctx.beginPath();
                ctx.roundRect(wX, y + 1, wW, h - 2, 4);
                ctx.fill();
                ctx.stroke();

                const displayName = this.name.toUpperCase().replace(/_/g, " ");
                const wType = this.origType || this.type;

                // A. Combo / Dropdown Widget
                if (wType === "combo" || this.options?.values) {
                    ctx.font = "bold 11px Inter, sans-serif";
                    ctx.fillStyle = "#CCCCCC";
                    ctx.textAlign = "left";
                    ctx.fillText(displayName, wX + 8, y + h / 2 + 4);

                    ctx.font = "600 11px Inter, sans-serif";
                    ctx.fillStyle = "#10B981";
                    ctx.textAlign = "right";
                    const strVal = String(this.value ?? "");
                    const maxChars = Math.floor(wW / 14);
                    const truncVal = strVal.length > maxChars ? strVal.substring(0, maxChars - 2) + "…" : strVal;
                    ctx.fillText(truncVal + "  ▼", wX + wW - 8, y + h / 2 + 4);
                }
                // B. Toggle (Boolean) Widget
                else if (wType === "toggle" || typeof this.value === "boolean") {
                    ctx.font = "bold 11px Inter, sans-serif";
                    ctx.fillStyle = "#CCCCCC";
                    ctx.textAlign = "left";
                    ctx.fillText(displayName, wX + 8, y + h / 2 + 4);

                    const isTrue = Boolean(this.value);
                    const tW = 32;
                    const tH = 15;
                    const tX = wX + wW - tW - 6;
                    const tY = y + (h - tH) / 2;

                    ctx.fillStyle = isTrue ? "#10B981" : "#374151";
                    ctx.beginPath();
                    ctx.roundRect(tX, tY, tW, tH, 8);
                    ctx.fill();

                    const kR = 5;
                    const kX = isTrue ? tX + tW - kR - 3 : tX + kR + 3;
                    ctx.fillStyle = "#FFFFFF";
                    ctx.beginPath();
                    ctx.arc(kX, tY + tH / 2, kR, 0, Math.PI * 2);
                    ctx.fill();
                }
                // C. Button Widget
                else if (wType === "button") {
                    ctx.font = "bold 11px Inter, sans-serif";
                    ctx.fillStyle = "#F3F4F6";
                    ctx.textAlign = "center";
                    ctx.fillText(this.label || displayName, wX + wW / 2, y + h / 2 + 4);
                }
                // D. Number / Slider Widget
                else {
                    const { min, max } = getWidgetBounds(this);
                    const val = Number(this.value ?? min);
                    const pct = Math.max(0, Math.min(1, (val - min) / (max - min)));

                    // Filled progress bar inside track
                    ctx.fillStyle = "rgba(16, 185, 129, 0.25)";
                    ctx.beginPath();
                    ctx.roundRect(wX + 1, y + 2, (wW - 2) * pct, h - 4, 3);
                    ctx.fill();

                    // White Indicator Thumb Knob (Same 1:1 cursor alignment as Color Spectrum Sliders!)
                    const markerX = wX + pct * wW;
                    const markerW = 4;
                    const markerH = h - 2;

                    ctx.fillStyle = "#FFFFFF";
                    ctx.shadowColor = "rgba(0, 0, 0, 0.6)";
                    ctx.shadowBlur = 4;
                    ctx.beginPath();
                    ctx.roundRect(markerX - markerW / 2, y + 1, markerW, markerH, 2);
                    ctx.fill();

                    ctx.font = "bold 11px Inter, sans-serif";
                    ctx.fillStyle = "#CCCCCC";
                    ctx.textAlign = "left";
                    ctx.fillText(displayName, wX + 8, y + h / 2 + 4);

                    ctx.font = "bold 11px Inter, sans-serif";
                    ctx.fillStyle = "#10B981";
                    ctx.textAlign = "right";
                    const valStr = typeof val === "number" ? val.toFixed(2) : String(val);
                    ctx.fillText(valStr, wX + wW - 8, y + h / 2 + 4);
                }

                ctx.restore();
            };

            widget.mouse = function (event, pos, nodeRef) {
                const targetNode = nodeRef || node;
                const lW = getLeftColWidth(targetNode);
                const wType = this.origType || this.type;

                // Hard Lock: Return true for Right Column clicks so LiteGraph fallback never runs!
                if (pos[0] > lW + 5) {
                    if (app.canvas) app.canvas.node_widget_drag = null;
                    return true;
                }

                if (event.type === "pointerdown" || event.type === "mousedown") {
                    // Button Click
                    if (wType === "button") {
                        if (this.callback) this.callback(this, targetNode, pos, event);
                        if (app.canvas) app.canvas.node_widget_drag = null;
                        return true;
                    }
                    // Toggle Click
                    if (wType === "toggle" || typeof this.value === "boolean") {
                        this.value = !this.value;
                        if (this.callback) this.callback(this.value, targetNode);
                        targetNode.updateClientLivePreview();
                        targetNode.setDirtyCanvas(true, true);
                        if (app.canvas) app.canvas.node_widget_drag = null;
                        return true;
                    }
                    // Combo Dropdown Click
                    if (wType === "combo" || this.options?.values) {
                        const values = this.options?.values;
                        if (Array.isArray(values) && values.length > 0) {
                            const canvas = app.canvas;
                            if (canvas && canvas.showWidgetOptions) {
                                canvas.showWidgetOptions(this, event);
                            } else {
                                const current = this.value;
                                const idx = values.indexOf(current);
                                const next = values[(idx + 1) % values.length];
                                this.value = next;
                                if (this.callback) this.callback(this.value, targetNode);
                                targetNode.updateClientLivePreview();
                                targetNode.setDirtyCanvas(true, true);
                            }
                        }
                        if (app.canvas) app.canvas.node_widget_drag = null;
                        return true;
                    }

                    // Smooth 1:1 Direct Window Pointer Dragging for All Float Sliders
                    startSliderDrag(this, targetNode, pos, event);
                    return true;
                }

                return false;
            };
        }
    });
}

app.registerExtension({
    name: "HackAfterDark.LiveGrade",
    async nodeCreated(node) {
        if (node.comfyClass !== "HackAfterDarkLiveGrade") return;

        // Disable standard ComfyUI default image rendering overlay
        node.imgs = null;

        // Interactive Preview Mode & Layout State
        node.previewMode = "graded_only"; // 'graded_only', 'dual_view', 'split_wipe'
        node.splitWipeRatio = 0.5;        // 0.0 (Original) to 1.0 (Graded)
        node.isDraggingWipe = false;
        node.activeDraggingWidget = null;
        node.mouseDownPos = null;
        node.isClickOnly = false;

        // Default side-by-side node dimensions (~860px wide x 680px tall)
        const defaultW = 860;
        const defaultH = 680;
        if (!node.size || node.size[0] < defaultW || node.size[1] < defaultH) {
            node.setSize([Math.max(node.size ? node.size[0] : 0, defaultW), Math.max(node.size ? node.size[1] : 0, defaultH)]);
        }

        // Initialize state for client-side offscreen rendering
        node.liveGradeState = {
            origImg: null,
            origCanvas: null,
            origCtx: null,
            gradedCanvas: null,
            gradedCtx: null,
            width: 0,
            height: 0,
            hasImage: false,
            isUpdating: false,
            currentUrl: null
        };

        const getWidgetVal = (name, def) => {
            const w = node.widgets?.find(w => w.name === name);
            return w ? w.value : def;
        };

        // Add Global Reset Button at top of node
        node.addWidget("button", "↺ Reset All Grade Settings", "reset", () => {
            const defaults = {
                lut_file: "None",
                lut_strength: 1.0,
                strength: 1.0,
                exposure: 0.0,
                contrast: 1.0,
                black_lift: 0.0,
                hue: 0.0,
                saturation: 1.0,
                tint_green_magenta: 0.0,
                tint_amber_blue: 0.0,
                shadow_tint: "Neutral",
                shadow_intensity: 0.0,
                highlight_tint: "Neutral",
                highlight_intensity: 0.0,
                balance: 0.0,
                micro_contrast: 0.0,
                clarity: 0.0,
                clip_output: true,
                output_original: true
            };
            (node.widgets || []).forEach(w => {
                if (defaults[w.name] !== undefined) {
                    w.value = defaults[w.name];
                }
            });
            node.updateClientLivePreview();
        });

        // Function to insert dedicated reset button directly beneath its corresponding color control
        const addResetButtonBeneath = (targetName, label, resetCallback) => {
            const btn = node.addWidget("button", label, "btn_reset_" + targetName, resetCallback);
            const targetIdx = node.widgets.findIndex(w => w.name === targetName);
            const btnIdx = node.widgets.indexOf(btn);
            if (targetIdx !== -1 && btnIdx !== -1 && btnIdx !== targetIdx + 1) {
                node.widgets.splice(btnIdx, 1);
                node.widgets.splice(targetIdx + 1, 0, btn);
            }
        };

        // Position individual reset buttons directly below each respective spectrum slider
        addResetButtonBeneath("hue", "↺ Reset Hue to 0°", () => {
            const w = node.widgets?.find(w => w.name === "hue");
            if (w) w.value = 0.0;
            node.updateClientLivePreview();
        });

        addResetButtonBeneath("tint_green_magenta", "↺ Reset Tint (Green/Magenta) to 0", () => {
            const w = node.widgets?.find(w => w.name === "tint_green_magenta");
            if (w) w.value = 0.0;
            node.updateClientLivePreview();
        });

        addResetButtonBeneath("tint_amber_blue", "↺ Reset Tint (Amber/Blue) to 0", () => {
            const w = node.widgets?.find(w => w.name === "tint_amber_blue");
            if (w) w.value = 0.0;
            node.updateClientLivePreview();
        });

        // Bind custom widget logic immediately
        setupCustomWidgets(node);

        // Bind custom widget logic when LiteGraph restores workflow configuration
        const origOnConfigure = node.onConfigure;
        node.onConfigure = function (info) {
            if (origOnConfigure) origOnConfigure.apply(this, arguments);
            setupCustomWidgets(this);
        };

        // Intercept LiteGraph widget hit-testing so Right Column clicks never trigger widgets
        node.findWidget = function (pos) {
            const leftColW = getLeftColWidth(this);

            // If click is in Right Column (Preview Area), return null so LiteGraph DOES NOT trigger any widget
            if (pos[0] > leftColW + 5) {
                return null;
            }

            if (!this.widgets) return null;
            for (let i = 0; i < this.widgets.length; i++) {
                const w = this.widgets[i];
                if (w.last_y === undefined) continue;
                const wH = w.computeSize ? w.computeSize(leftColW)[1] : 22;
                if (pos[1] >= w.last_y && pos[1] <= w.last_y + wH) {
                    return w;
                }
            }
            return null;
        };

        // Client-Side Real-Time Color Grading Engine
        node.updateClientLivePreview = async function () {
            const state = this.liveGradeState;
            if (!state.hasImage || !state.origCtx || !state.gradedCtx || state.isUpdating) return;

            state.isUpdating = true;
            try {
                const lutFile = getWidgetVal("lut_file", "None");
                const lutStrength = Number(getWidgetVal("lut_strength", getWidgetVal("strength", 1.0)));
                const exposure = Number(getWidgetVal("exposure", 0.0));
                const contrast = Number(getWidgetVal("contrast", 1.0));
                const blackLift = Number(getWidgetVal("black_lift", 0.0));
                const hue = Number(getWidgetVal("hue", 0.0));
                const saturation = Number(getWidgetVal("saturation", 1.0));
                const tintGM = Number(getWidgetVal("tint_green_magenta", 0.0));
                const tintAB = Number(getWidgetVal("tint_amber_blue", 0.0));

                const shadowTint = getWidgetVal("shadow_tint", "Neutral");
                const shadowIntensity = Number(getWidgetVal("shadow_intensity", 0.0));
                const highlightTint = getWidgetVal("highlight_tint", "Neutral");
                const highlightIntensity = Number(getWidgetVal("highlight_intensity", 0.0));
                const balance = Number(getWidgetVal("balance", 0.0));
                const microContrast = Number(getWidgetVal("micro_contrast", 0.0));
                const clarity = Number(getWidgetVal("clarity", 0.0));

                const clipOutput = Boolean(getWidgetVal("clip_output", true));

                let lutData = null;
                if (lutFile && lutFile !== "None" && lutFile !== "No LUTs found" && lutStrength > 0) {
                    lutData = await fetchLutData(lutFile);
                }

                const W = state.width;
                const H = state.height;
                const srcData = state.origCtx.getImageData(0, 0, W, H);
                const dstData = state.gradedCtx.createImageData(W, H);

                const src = srcData.data;
                const dst = dstData.data;
                const numPixels = W * H;

                // Split Toning Color Tint Offsets [R, G, B]
                let sOffset = [0.0, 0.0, 0.0];
                if (shadowTint === "Teal / Cyan") sOffset = [-0.20, 0.10, 0.20];
                else if (shadowTint === "Deep Blue") sOffset = [-0.15, -0.05, 0.25];
                else if (shadowTint === "Emerald Green") sOffset = [-0.15, 0.25, -0.10];
                else if (shadowTint === "Warm Sepia") sOffset = [0.25, 0.10, -0.15];

                let hOffset = [0.0, 0.0, 0.0];
                if (highlightTint === "Golden Amber") hOffset = [0.25, 0.15, -0.20];
                else if (highlightTint === "Warm Yellow") hOffset = [0.20, 0.20, -0.20];
                else if (highlightTint === "Peach Rose") hOffset = [0.25, -0.05, 0.10];
                else if (highlightTint === "Cool Cyan") hOffset = [-0.15, 0.15, 0.25];

                const midpoint = 0.5 + balance * 0.35;
                const midSafeS = Math.max(0.01, midpoint);
                const midSafeH = Math.max(0.01, 1.0 - midpoint);

                for (let i = 0; i < numPixels; i++) {
                    const px = i * 4;
                    let r = src[px] / 255.0;
                    let g = src[px + 1] / 255.0;
                    let b = src[px + 2] / 255.0;
                    const a = src[px + 3];

                    // 1. 3D LUT Application
                    if (lutData && lutStrength > 0) {
                        const [lr, lg, lb] = sampleLut(r, g, b, lutData);
                        r = (1.0 - lutStrength) * r + lutStrength * lr;
                        g = (1.0 - lutStrength) * g + lutStrength * lg;
                        b = (1.0 - lutStrength) * b + lutStrength * lb;
                    }

                    // 2. Tonality: Exposure -> Contrast -> Black Lift
                    if (exposure !== 0.0) {
                        const mult = Math.pow(2.0, exposure);
                        r *= mult;
                        g *= mult;
                        b *= mult;
                    }

                    if (contrast !== 1.0) {
                        r = (r - 0.5) * contrast + 0.5;
                        g = (g - 0.5) * contrast + 0.5;
                        b = (b - 0.5) * contrast + 0.5;
                    }

                    if (blackLift !== 0.0) {
                        if (blackLift >= 0.0) {
                            r = r * (1.0 - blackLift) + blackLift;
                            g = g * (1.0 - blackLift) + blackLift;
                            b = b * (1.0 - blackLift) + blackLift;
                        } else {
                            r = r * (1.0 + blackLift);
                            g = g * (1.0 + blackLift);
                            b = b * (1.0 + blackLift);
                        }
                    }

                    // 3. HSV Color Shift
                    if (hue !== 0.0 || saturation !== 1.0) {
                        let [h, s, v] = rgbToHsv(
                            Math.max(0, Math.min(1, r)),
                            Math.max(0, Math.min(1, g)),
                            Math.max(0, Math.min(1, b))
                        );
                        if (hue !== 0.0) {
                            h = (h + (hue / 360.0)) % 1.0;
                            if (h < 0) h += 1.0;
                        }
                        if (saturation !== 1.0) {
                            s = Math.max(0, Math.min(1, s * saturation));
                        }
                        [r, g, b] = hsvToRgb(h, s, v);
                    }

                    // 4. Tint Correction
                    if (tintGM !== 0.0 || tintAB !== 0.0) {
                        r += 0.25 * tintGM + 0.50 * tintAB;
                        g += -0.50 * tintGM + 0.25 * tintAB;
                        b += 0.25 * tintGM - 0.50 * tintAB;
                    }

                    // 5. Split Toning
                    if ((shadowTint !== "Neutral" && shadowIntensity > 0) || (highlightTint !== "Neutral" && highlightIntensity > 0)) {
                        const lum = 0.2126 * r + 0.7152 * g + 0.0722 * b;
                        const sw = Math.max(0, Math.min(1, (midpoint - lum) / midSafeS));
                        const hw = Math.max(0, Math.min(1, (lum - midpoint) / midSafeH));

                        if (sw > 0 && shadowTint !== "Neutral" && shadowIntensity > 0) {
                            r += sw * shadowIntensity * sOffset[0];
                            g += sw * shadowIntensity * sOffset[1];
                            b += sw * shadowIntensity * sOffset[2];
                        }
                        if (hw > 0 && highlightTint !== "Neutral" && highlightIntensity > 0) {
                            r += hw * highlightIntensity * hOffset[0];
                            g += hw * highlightIntensity * hOffset[1];
                            b += hw * highlightIntensity * hOffset[2];
                        }
                    }

                    // 6. Output Clipping
                    if (clipOutput) {
                        r = Math.max(0, Math.min(1, r));
                        g = Math.max(0, Math.min(1, g));
                        b = Math.max(0, Math.min(1, b));
                    }

                    dst[px] = Math.round(r * 255);
                    dst[px + 1] = Math.round(g * 255);
                    dst[px + 2] = Math.round(b * 255);
                    dst[px + 3] = a;
                }

                // 7. Micro-Contrast / Clarity (High-Pass Convolution Filter)
                const mcAmount = Math.max(microContrast, clarity);
                if (mcAmount > 0.0) {
                    const cMult = mcAmount * 1.2;
                    const copyData = new Uint8ClampedArray(dst);

                    for (let y = 1; y < H - 1; y++) {
                        for (let x = 1; x < W - 1; x++) {
                            const p = (y * W + x) * 4;

                            // 3x3 Average low pass
                            let sumR = 0, sumG = 0, sumB = 0;
                            for (let dy = -1; dy <= 1; dy++) {
                                for (let dx = -1; dx <= 1; dx++) {
                                    const np = ((y + dy) * W + (x + dx)) * 4;
                                    sumR += copyData[np];
                                    sumG += copyData[np + 1];
                                    sumB += copyData[np + 2];
                                }
                            }
                            const avgR = sumR / 9.0;
                            const avgG = sumG / 9.0;
                            const avgB = sumB / 9.0;

                            const hpR = copyData[p] - avgR;
                            const hpG = copyData[p + 1] - avgG;
                            const hpB = copyData[p + 2] - avgB;

                            let nr = copyData[p] + hpR * cMult;
                            let ng = copyData[p + 1] + hpG * cMult;
                            let nb = copyData[p + 2] + hpB * cMult;

                            if (clipOutput) {
                                nr = Math.max(0, Math.min(255, nr));
                                ng = Math.max(0, Math.min(255, ng));
                                nb = Math.max(0, Math.min(255, nb));
                            }

                            dst[p] = Math.round(nr);
                            dst[p + 1] = Math.round(ng);
                            dst[p + 2] = Math.round(nb);
                        }
                    }
                }

                state.gradedCtx.putImageData(dstData, 0, 0);
                this.setDirtyCanvas(true, true);

                // Update active Lightbox view if currently open for this node
                if (currentLightbox && currentLightbox.node === this) {
                    currentLightbox.update();
                }
            } catch (err) {
                console.error("[HackAfterDarkLiveGrade] Error in client live update:", err);
            } finally {
                state.isUpdating = false;
            }
        };

        // Automatically fetch image from upstream node (LoadImage, PreviewImage, etc.) without execution!
        node.checkUpstreamImage = function () {
            const url = findUpstreamImageUrl(this);
            if (!url) return;

            if (this.liveGradeState.currentUrl === url && this.liveGradeState.hasImage) {
                this.updateClientLivePreview();
                return;
            }

            const img = new Image();
            img.crossOrigin = "anonymous";
            img.onload = () => {
                const state = this.liveGradeState;
                const maxDim = 1024;
                let w = img.width;
                let h = img.height;
                if (w > maxDim || h > maxDim) {
                    if (w > h) {
                        h = Math.round((h * maxDim) / w);
                        w = maxDim;
                    } else {
                        w = Math.round((w * maxDim) / h);
                        h = maxDim;
                    }
                }

                state.width = w;
                state.height = h;

                state.origCanvas = document.createElement("canvas");
                state.origCanvas.width = w;
                state.origCanvas.height = h;
                state.origCtx = state.origCanvas.getContext("2d", { willReadFrequently: true });
                if (state.origCtx) state.origCtx.imageSmoothingQuality = "high";
                state.origCtx.drawImage(img, 0, 0, w, h);

                state.gradedCanvas = document.createElement("canvas");
                state.gradedCanvas.width = w;
                state.gradedCanvas.height = h;
                state.gradedCtx = state.gradedCanvas.getContext("2d", { willReadFrequently: true });
                if (state.gradedCtx) state.gradedCtx.imageSmoothingQuality = "high";

                state.origImg = img;
                state.currentUrl = url;
                state.hasImage = true;

                this.updateClientLivePreview();
            };
            img.src = url;
        };

        // Hook link changes to automatically pull upstream image
        const origOnConnectionsChange = node.onConnectionsChange;
        node.onConnectionsChange = function (type, index, connected, link_info) {
            if (origOnConnectionsChange) origOnConnectionsChange.apply(this, arguments);
            setTimeout(() => {
                this.checkUpstreamImage();
            }, 50);
        };

        // Attach callbacks to ALL controls to trigger client-side live preview ONLY
        (node.widgets || []).forEach(widget => {
            const origCallback = widget.callback;
            widget.callback = function (...args) {
                if (origCallback) origCallback.apply(this, args);
                node.updateClientLivePreview();
            };
        });

        // Helper to get Right Column Preview Geometry
        node.getRightColumnBounds = function () {
            const leftColW = getLeftColWidth(this);
            const margin = 10;
            const rx = leftColW + margin;
            const ry = 30; // Below node title header bar
            const rw = this.size[0] - rx - margin;
            const rh = this.size[1] - ry - margin;
            return { rx, ry, rw, rh, leftColW };
        };

        // Helper to calculate Mode Switcher Pill geometry
        node.getPillsGeometry = function () {
            const { rx, ry, rw } = this.getRightColumnBounds();
            const pillY = ry + 8;
            const pillH = 26;
            const gap = 6;
            const totalW = Math.max(180, rw - 20);
            const pillW = (totalW - gap * 2) / 3;

            const p1 = { x: rx + 10, y: pillY, w: pillW, h: pillH, mode: "graded_only", label: "Graded Only" };
            const p2 = { x: rx + 10 + pillW + gap, y: pillY, w: pillW, h: pillH, mode: "dual_view", label: "Dual View" };
            const p3 = { x: rx + 10 + (pillW + gap) * 2, y: pillY, w: pillW, h: pillH, mode: "split_wipe", label: "Split Wipe" };
            return [p1, p2, p3];
        };

        // Mouse Event Handler for Right-Column Controls, Mode Switcher Pills & Split Wipe Dragging
        const origOnMouseDown = node.onMouseDown;
        node.onMouseDown = function (event, pos, canvas) {
            this.imgs = null; // Always suppress standard ComfyUI image preview click capture

            const leftColW = getLeftColWidth(this);
            const { rx, ry, rw, rh } = this.getRightColumnBounds();

            // 1. Allow LiteGraph node title header bar (pos[1] < 30) or resize handle (bottom-right ~25px) to move/resize node!
            if (pos[1] < 30 || (pos[0] > this.size[0] - 25 && pos[1] > this.size[1] - 25)) {
                return false;
            }

            // Check if click is inside Right Column Area below title header
            if (pos[0] > leftColW + 5) {
                if (app.canvas) app.canvas.node_widget_drag = null;

                // 1. Check Mode Switcher Pills Click
                const pills = this.getPillsGeometry();
                for (const p of pills) {
                    if (pos[0] >= p.x && pos[0] <= p.x + p.w && pos[1] >= p.y && pos[1] <= p.y + p.h) {
                        this.previewMode = p.mode;
                        this.setDirtyCanvas(true, true);
                        return true;
                    }
                }

                // 2. Check Viewport Click (Lightbox / Split Wipe Drag)
                const viewportY = ry + 40;
                const viewportH = rh - 50;

                if (pos[0] >= rx + 10 && pos[0] <= rx + rw - 10 && pos[1] >= viewportY && pos[1] <= viewportY + viewportH) {
                    if (!this.liveGradeState || !this.liveGradeState.hasImage) {
                        this.checkUpstreamImage();
                    }

                    if (this.previewMode === "split_wipe") {
                        this.isDraggingWipe = true;
                        const relX = Math.max(0, Math.min(rw - 20, pos[0] - (rx + 10)));
                        this.splitWipeRatio = relX / (rw - 20);
                        this.setDirtyCanvas(true, true);
                        return true;
                    } else if (this.liveGradeState && this.liveGradeState.hasImage) {
                        if (this.previewMode === "dual_view" && pos[0] < rx + rw / 2) {
                            openLightbox("before", this);
                        } else {
                            openLightbox("after", this);
                        }
                        return true;
                    }
                }

                // Consume click inside right column panel to prevent any stray widget activation
                return true;
            }

            if (origOnMouseDown) {
                return origOnMouseDown.apply(this, arguments);
            }
            return false;
        };

        // Mouse Move for Split Wipe Dragging inside 40% Column
        const origOnMouseMove = node.onMouseMove;
        node.onMouseMove = function (event, pos, canvas) {
            if (this.isDraggingWipe) {
                const { rx, rw } = this.getRightColumnBounds();
                const relX = Math.max(0, Math.min(rw - 20, pos[0] - (rx + 10)));
                this.splitWipeRatio = relX / (rw - 20);
                this.setDirtyCanvas(true, true);
                return true;
            }

            if (this.activeDraggingWidget) {
                if (app.canvas) app.canvas.node_widget_drag = null;
                return true;
            }

            if (origOnMouseMove) return origOnMouseMove.apply(this, arguments);
            return false;
        };

        // Mouse Up to release Split Wipe Dragging
        const origOnMouseUp = node.onMouseUp;
        node.onMouseUp = function (event, pos, canvas) {
            if (this.isDraggingWipe) {
                this.isDraggingWipe = false;
                this.setDirtyCanvas(true, true);
                return true;
            }

            if (this.activeDraggingWidget) {
                if (app.canvas) app.canvas.node_widget_drag = null;
                return true;
            }

            if (origOnMouseUp) return origOnMouseUp.apply(this, arguments);
            return false;
        };

        // Set up original source image when workflow executes
        const origOnExecuted = node.onExecuted;
        node.onExecuted = function (message) {
            if (origOnExecuted) origOnExecuted.apply(this, arguments);

            // Suppress standard ComfyUI default image rendering overlay
            this.imgs = null;

            const images = message?.livegrade_images || message?.images;
            if (images && images.length > 0) {
                const imgInfo = images[0];
                const imgUrl = api.apiURL("/view?" + new URLSearchParams(imgInfo).toString());

                const img = new Image();
                img.crossOrigin = "anonymous";
                img.onload = () => {
                    const state = node.liveGradeState;
                    const maxDim = 1024;
                    let w = img.width;
                    let h = img.height;
                    if (w > maxDim || h > maxDim) {
                        if (w > h) {
                            h = Math.round((h * maxDim) / w);
                            w = maxDim;
                        } else {
                            w = Math.round((w * maxDim) / h);
                            h = maxDim;
                        }
                    }

                    state.width = w;
                    state.height = h;

                    state.origCanvas = document.createElement("canvas");
                    state.origCanvas.width = w;
                    state.origCanvas.height = h;
                    state.origCtx = state.origCanvas.getContext("2d", { willReadFrequently: true });
                    if (state.origCtx) state.origCtx.imageSmoothingQuality = "high";
                    state.origCtx.drawImage(img, 0, 0, w, h);

                    state.gradedCanvas = document.createElement("canvas");
                    state.gradedCanvas.width = w;
                    state.gradedCanvas.height = h;
                    state.gradedCtx = state.gradedCanvas.getContext("2d", { willReadFrequently: true });
                    if (state.gradedCtx) state.gradedCtx.imageSmoothingQuality = "high";

                    state.origImg = img;
                    state.currentUrl = imgUrl;
                    state.hasImage = true;

                    node.updateClientLivePreview();
                };
                img.src = imgUrl;
            }
        };

        // Custom Node Foreground Canvas Drawer: Right-Column Viewport + 3 Preview Modes
        const origOnDrawForeground = node.onDrawForeground;
        node.onDrawForeground = function (ctx, canvas) {
            // Keep default image renderer disabled
            this.imgs = null;

            // Re-enforce custom widget binding on every draw pass to prevent workflow load resets
            setupCustomWidgets(this);

            if (origOnDrawForeground) origOnDrawForeground.apply(this, arguments);

            if (this.flags.collapsed) return;

            // 1. Draw sleek disabled overlays over shadow_intensity / highlight_intensity ONLY when their tint is Neutral
            const sTint = getWidgetVal("shadow_tint", "Neutral");
            const hTint = getWidgetVal("highlight_tint", "Neutral");
            const sIntW = this.widgets?.find(w => w.name === "shadow_intensity");
            const hIntW = this.widgets?.find(w => w.name === "highlight_intensity");

            const drawDisabledOverlay = (widget, text) => {
                if (!widget || !widget.last_y) return;
                ctx.save();
                const leftW = getLeftColWidth(this);
                const pad = 12;
                const wX = pad;
                const wY = widget.last_y;
                const wW = leftW - pad * 2;
                const wH = 22;

                ctx.fillStyle = "rgba(22, 25, 33, 0.94)";
                ctx.beginPath();
                ctx.roundRect(wX, wY, wW, wH, 4);
                ctx.fill();

                ctx.strokeStyle = "rgba(255, 255, 255, 0.08)";
                ctx.lineWidth = 1;
                ctx.stroke();

                ctx.fillStyle = "#6B7280";
                ctx.font = "italic 10px Inter, sans-serif";
                ctx.textAlign = "center";
                ctx.fillText(text, wX + wW / 2, wY + wH / 2 + 3);

                ctx.restore();
            };

            if (sTint === "Neutral" && sIntW) {
                drawDisabledOverlay(sIntW, "(Select shadow tint to enable)");
            }
            if (hTint === "Neutral" && hIntW) {
                drawDisabledOverlay(hTint, "(Select highlight tint to enable)");
            }

            // 2. Right-Column Preview Viewport Setup
            const { rx, ry, rw, rh, leftColW } = this.getRightColumnBounds();

            if (rw < 140 || rh < 100) return;

            ctx.save();

            // Right Column Background Panel
            ctx.fillStyle = "rgba(18, 20, 26, 0.92)";
            ctx.strokeStyle = "rgba(255, 255, 255, 0.12)";
            ctx.lineWidth = 1;
            ctx.beginPath();
            ctx.roundRect(rx, ry, rw, rh, 8);
            ctx.fill();
            ctx.stroke();

            // Vertical Divider Line between Left Controls & Right Preview
            ctx.strokeStyle = "rgba(255, 255, 255, 0.15)";
            ctx.lineWidth = 1;
            ctx.beginPath();
            ctx.moveTo(leftColW + 5, ry);
            ctx.lineTo(leftColW + 5, ry + rh);
            ctx.stroke();

            // 3. Render Mode Switcher Pills Header
            const pills = this.getPillsGeometry();
            pills.forEach(p => {
                const isActive = (this.previewMode || "graded_only") === p.mode;
                ctx.fillStyle = isActive ? "#10B981" : "rgba(255, 255, 255, 0.08)";
                ctx.beginPath();
                ctx.roundRect(p.x, p.y, p.w, p.h, 13);
                ctx.fill();

                if (!isActive) {
                    ctx.strokeStyle = "rgba(255, 255, 255, 0.12)";
                    ctx.lineWidth = 1;
                    ctx.stroke();
                }

                ctx.font = isActive ? "bold 11px Inter, sans-serif" : "600 11px Inter, sans-serif";
                ctx.fillStyle = isActive ? "#FFFFFF" : "#9CA3AF";
                ctx.textAlign = "center";
                ctx.fillText(p.label, p.x + p.w / 2, p.y + p.h / 2 + 4);
            });

            // 4. Viewport Bounding Box
            const vX = rx + 10;
            const vY = ry + 42;
            const vW = rw - 20;
            const vH = rh - 50;

            const state = this.liveGradeState;

            // Attempt automatic upstream fetch if no image is loaded yet
            if (!state || !state.hasImage) {
                this.checkUpstreamImage();
            }

            if (!state || !state.hasImage || !state.origCanvas || !state.gradedCanvas) {
                ctx.fillStyle = "#8E9BAE";
                ctx.font = "italic 12px Inter, sans-serif";
                ctx.textAlign = "center";
                ctx.fillText("Connect an image node or run workflow once", vX + vW / 2, vY + vH / 2);
                ctx.restore();
                return;
            }

            // Helper to draw Aspect-Fit Canvas
            const drawAspectFit = (srcCanvas, targetX, targetY, targetW, targetH) => {
                const aspect = srcCanvas.width / srcCanvas.height;
                let fitW = targetW;
                let fitH = targetW / aspect;
                if (fitH > targetH) {
                    fitH = targetH;
                    fitW = targetH * aspect;
                }
                const offX = targetX + (targetW - fitW) / 2;
                const offY = targetY + (targetH - fitH) / 2;

                ctx.drawImage(srcCanvas, offX, offY, fitW, fitH);
                ctx.strokeStyle = "rgba(255, 255, 255, 0.15)";
                ctx.strokeRect(offX, offY, fitW, fitH);
                return { offX, offY, fitW, fitH };
            };

            const mode = this.previewMode || "graded_only";

            // MODE 1: Graded Only (100% Full Viewport Area)
            if (mode === "graded_only") {
                const bounds = drawAspectFit(state.gradedCanvas, vX, vY, vW, vH);

                ctx.font = "bold 11px Inter, sans-serif";
                ctx.textAlign = "left";
                ctx.fillStyle = "#10B981";
                ctx.fillText("COLOR GRADED", bounds.offX + 6, bounds.offY + 16);
            }
            // MODE 2: Dual View (Side-by-Side Comparison)
            else if (mode === "dual_view") {
                const gap = 8;
                const subW = (vW - gap) / 2;

                const bLeft = drawAspectFit(state.origCanvas, vX, vY, subW, vH);
                const bRight = drawAspectFit(state.gradedCanvas, vX + subW + gap, vY, subW, vH);

                ctx.font = "bold 11px Inter, sans-serif";
                ctx.textAlign = "left";

                ctx.fillStyle = "#8E9BAE";
                ctx.fillText("ORIGINAL", bLeft.offX + 6, bLeft.offY + 16);

                ctx.fillStyle = "#10B981";
                ctx.fillText("COLOR GRADED", bRight.offX + 6, bRight.offY + 16);
            }
            // MODE 3: Split Wipe (Full-Width Interactive Wipe Comparison)
            else if (mode === "split_wipe") {
                const bounds = drawAspectFit(state.gradedCanvas, vX, vY, vW, vH);
                const wipeRatio = Math.max(0, Math.min(1, this.splitWipeRatio ?? 0.5));
                const splitX = bounds.offX + bounds.fitW * wipeRatio;

                // Draw Original Left Side
                ctx.save();
                ctx.beginPath();
                ctx.rect(bounds.offX, bounds.offY, splitX - bounds.offX, bounds.fitH);
                ctx.clip();
                ctx.drawImage(state.origCanvas, bounds.offX, bounds.offY, bounds.fitW, bounds.fitH);
                ctx.restore();

                // Draw Interactive Vertical Split Handle Line
                ctx.fillStyle = "#10B981";
                ctx.shadowColor = "rgba(16, 185, 129, 0.8)";
                ctx.shadowBlur = 8;
                ctx.fillRect(splitX - 1, bounds.offY, 2, bounds.fitH);

                // Handle Knob Button in Middle
                const knobY = bounds.offY + bounds.fitH / 2;
                ctx.fillStyle = "#10B981";
                ctx.beginPath();
                ctx.arc(splitX, knobY, 12, 0, Math.PI * 2);
                ctx.fill();

                ctx.fillStyle = "#FFFFFF";
                ctx.font = "bold 11px Inter, sans-serif";
                ctx.textAlign = "center";
                ctx.fillText("✂", splitX, knobY + 4);

                // Labels
                ctx.font = "bold 11px Inter, sans-serif";
                ctx.textAlign = "left";
                ctx.fillStyle = "#8E9BAE";
                ctx.fillText("ORIGINAL", bounds.offX + 6, bounds.offY + 16);

                ctx.textAlign = "right";
                ctx.fillStyle = "#10B981";
                ctx.fillText("COLOR GRADED", bounds.offX + bounds.fitW - 6, bounds.offY + 16);
            }

            ctx.restore();
        };

        // Attach dynamic listener for LoadImage dropdown changes
        setTimeout(() => {
            node.checkUpstreamImage();
        }, 300);
    }
});
