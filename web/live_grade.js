import { app } from "/scripts/app.js";
import { api } from "/scripts/api.js";

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

    const c00 = [c000[0] * (1 - dx) + c100[0] * dx, c000[1] * (1 - dx) + c100[1] * dx, c000[2] * (1 - dx) + c100[2] * dx];
    const c10 = [c010[0] * (1 - dx) + c110[0] * dx, c010[1] * (1 - dx) + c110[1] * dx, c010[2] * (1 - dx) + c110[2] * dx];
    const c01 = [c001[0] * (1 - dx) + c101[0] * dx, c001[1] * (1 - dx) + c101[1] * dx, c001[2] * (1 - dx) + c101[2] * dx];
    const c11 = [c011[0] * (1 - dx) + c111[0] * dx, c011[1] * (1 - dx) + c111[1] * dx, c011[2] * (1 - dx) + c111[2] * dx];

    const c0 = [c00[0] * (1 - dy) + c10[0] * dy, c00[1] * (1 - dy) + c10[1] * dy, c00[2] * (1 - dy) + c10[2] * dy];
    const c1 = [c01[0] * (1 - dy) + c11[0] * dy, c01[1] * (1 - dy) + c11[1] * dy, c01[2] * (1 - dy) + c11[2] * dy];

    return [
        c0[0] * (1 - dz) + c1[0] * dz,
        c0[1] * (1 - dz) + c1[1] * dz,
        c0[2] * (1 - dz) + c1[2] * dz
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
    btnAfter.innerHTML = "AFTER (Live Graded)";
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

app.registerExtension({
    name: "HackAfterDark.LiveGrade",
    async nodeCreated(node) {
        if (node.comfyClass !== "HackAfterDarkLiveGrade") return;

        // Disable standard ComfyUI default image rendering overlay
        node.imgs = null;

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

        // Client-Side Real-Time Color Grading Engine
        node.updateClientLivePreview = async function () {
            const state = this.liveGradeState;
            if (!state.hasImage || !state.origCtx || !state.gradedCtx || state.isUpdating) return;

            state.isUpdating = true;
            try {
                const lutFile = getWidgetVal("lut_file", "None");
                const strength = Number(getWidgetVal("strength", 1.0));
                const exposure = Number(getWidgetVal("exposure", 0.0));
                const contrast = Number(getWidgetVal("contrast", 1.0));
                const blackLift = Number(getWidgetVal("black_lift", 0.0));
                const hue = Number(getWidgetVal("hue", 0.0));
                const saturation = Number(getWidgetVal("saturation", 1.0));
                const tintGM = Number(getWidgetVal("tint_green_magenta", 0.0));
                const tintAB = Number(getWidgetVal("tint_amber_blue", 0.0));
                const clipOutput = Boolean(getWidgetVal("clip_output", true));

                let lutData = null;
                if (lutFile && lutFile !== "None" && lutFile !== "No LUTs found" && strength > 0) {
                    lutData = await fetchLutData(lutFile);
                }

                const W = state.width;
                const H = state.height;
                const srcData = state.origCtx.getImageData(0, 0, W, H);
                const dstData = state.gradedCtx.createImageData(W, H);

                const src = srcData.data;
                const dst = dstData.data;
                const numPixels = W * H;

                for (let i = 0; i < numPixels; i++) {
                    const px = i * 4;
                    let r = src[px] / 255.0;
                    let g = src[px + 1] / 255.0;
                    let b = src[px + 2] / 255.0;
                    const a = src[px + 3];

                    // 1. 3D LUT Application
                    if (lutData && strength > 0) {
                        const [lr, lg, lb] = sampleLut(r, g, b, lutData);
                        r = (1.0 - strength) * r + strength * lr;
                        g = (1.0 - strength) * g + strength * lg;
                        b = (1.0 - strength) * b + strength * lb;
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

                    // 5. Output Clipping
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
                state.origCtx = state.origCanvas.getContext("2d");
                state.origCtx.drawImage(img, 0, 0, w, h);

                state.gradedCanvas = document.createElement("canvas");
                state.gradedCanvas.width = w;
                state.gradedCanvas.height = h;
                state.gradedCtx = state.gradedCanvas.getContext("2d");

                state.origImg = img;
                state.currentUrl = url;
                state.hasImage = true;

                const minHeight = 460;
                if (this.size[1] < minHeight) {
                    this.setSize([Math.max(this.size[0], 340), minHeight]);
                }

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

        // Click handler to launch Full-Screen Lightbox Asset Viewer when clicking node preview box
        const origOnMouseDown = node.onMouseDown;
        node.onMouseDown = function (event, pos, canvas) {
            this.imgs = null; // Always suppress standard ComfyUI image preview click capture

            let widgetsHeight = 280;
            if (this.widgets && this.widgets.length > 0) {
                const lastWidget = this.widgets[this.widgets.length - 1];
                widgetsHeight = lastWidget.last_y ? lastWidget.last_y + 30 : 280;
            }

            const pad = 12;
            const boxX = pad;
            const boxY = widgetsHeight;
            const boxW = this.size[0] - pad * 2;
            const boxH = this.size[1] - widgetsHeight - pad;

            if (pos[0] >= boxX && pos[0] <= boxX + boxW && pos[1] >= boxY && pos[1] <= boxY + boxH) {
                if (!this.liveGradeState || !this.liveGradeState.hasImage) {
                    this.checkUpstreamImage();
                }
                if (this.liveGradeState && this.liveGradeState.hasImage) {
                    if (pos[0] < boxX + boxW / 2) {
                        openLightbox("before", this);
                    } else {
                        openLightbox("after", this);
                    }
                    return true;
                }
            }

            if (origOnMouseDown) {
                return origOnMouseDown.apply(this, arguments);
            }
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
                    state.origCtx = state.origCanvas.getContext("2d");
                    state.origCtx.drawImage(img, 0, 0, w, h);

                    state.gradedCanvas = document.createElement("canvas");
                    state.gradedCanvas.width = w;
                    state.gradedCanvas.height = h;
                    state.gradedCtx = state.gradedCanvas.getContext("2d");

                    state.origImg = img;
                    state.currentUrl = imgUrl;
                    state.hasImage = true;

                    const minHeight = 460;
                    if (node.size[1] < minHeight) {
                        node.setSize([Math.max(node.size[0], 340), minHeight]);
                    }

                    node.updateClientLivePreview();
                };
                img.src = imgUrl;
            }
        };

        // Custom Node Foreground Canvas Drawer
        const origOnDrawForeground = node.onDrawForeground;
        node.onDrawForeground = function (ctx, canvas) {
            // Keep default image renderer disabled
            this.imgs = null;

            if (origOnDrawForeground) origOnDrawForeground.apply(this, arguments);

            if (this.flags.collapsed) return;

            let widgetsHeight = 280;
            if (this.widgets && this.widgets.length > 0) {
                const lastWidget = this.widgets[this.widgets.length - 1];
                widgetsHeight = lastWidget.last_y ? lastWidget.last_y + 30 : 280;
            }

            const pad = 12;
            const availableWidth = this.size[0] - pad * 2;
            const availableHeight = this.size[1] - widgetsHeight - pad;

            if (availableHeight < 80 || availableWidth < 120) return;

            const boxX = pad;
            const boxY = widgetsHeight;
            const boxW = availableWidth;
            const boxH = availableHeight;

            ctx.save();
            ctx.fillStyle = "rgba(18, 20, 26, 0.85)";
            ctx.strokeStyle = "rgba(255, 255, 255, 0.12)";
            ctx.lineWidth = 1;
            ctx.beginPath();
            ctx.roundRect(boxX, boxY, boxW, boxH, 8);
            ctx.fill();
            ctx.stroke();

            const state = this.liveGradeState;

            // Attempt automatic upstream fetch if no image is loaded yet
            if (!state || !state.hasImage) {
                this.checkUpstreamImage();
            }

            if (!state || !state.hasImage || !state.origCanvas || !state.gradedCanvas) {
                ctx.fillStyle = "#8E9BAE";
                ctx.font = "italic 11px Inter, sans-serif";
                ctx.textAlign = "center";
                ctx.fillText("Connect an image node or run workflow once", boxX + boxW / 2, boxY + boxH / 2);
                ctx.restore();
                return;
            }

            const thumbGap = 8;
            const thumbW = (boxW - thumbGap - pad * 2) / 2;
            const thumbH = boxH - pad * 2 - 20;

            if (thumbW > 20 && thumbH > 20) {
                const leftX = boxX + pad;
                const leftY = boxY + pad + 20;
                const rightX = leftX + thumbW + thumbGap;
                const rightY = leftY;

                const drawAspectFitCanvas = (srcCanvas, x, y, w, h) => {
                    const aspect = srcCanvas.width / srcCanvas.height;
                    let targetW = w;
                    let targetH = w / aspect;
                    if (targetH > h) {
                        targetH = h;
                        targetW = h * aspect;
                    }
                    const offsetX = x + (w - targetW) / 2;
                    const offsetY = y + (h - targetH) / 2;

                    ctx.drawImage(srcCanvas, offsetX, offsetY, targetW, targetH);
                    ctx.strokeStyle = "rgba(255, 255, 255, 0.15)";
                    ctx.strokeRect(offsetX, offsetY, targetW, targetH);
                };

                drawAspectFitCanvas(state.origCanvas, leftX, leftY, thumbW, thumbH);
                drawAspectFitCanvas(state.gradedCanvas, rightX, rightY, thumbW, thumbH);

                ctx.font = "bold 11px Inter, sans-serif";
                ctx.textAlign = "left";

                ctx.fillStyle = "#8E9BAE";
                ctx.fillText("ORIGINAL", leftX + 4, leftY - 6);

                ctx.fillStyle = "#10B981";
                ctx.fillText("LIVE GRADED (REAL-TIME)", rightX + 4, rightY - 6);
            }

            ctx.restore();
        };

        // Attach dynamic listener for LoadImage dropdown changes
        setTimeout(() => {
            node.checkUpstreamImage();
        }, 300);
    }
});
