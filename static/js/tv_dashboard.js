(function () {
    const grid = document.querySelector(".tv-grid");
    if (!grid) return;

    const tvId = grid.dataset.tvId;
    const presets = JSON.parse(document.getElementById("presets-data").textContent);

    const overlay = document.getElementById("action-overlay");
    const overlayClose = document.getElementById("overlay-close");
    const infoChannel = document.getElementById("info-channel");
    const infoMeta = document.getElementById("info-meta");
    const appSelector = document.getElementById("app-selector");
    const appSelectorEmpty = document.getElementById("app-selector-empty");
    const toggleBtns = Array.from(document.querySelectorAll(".toggle-btn"));
    const primaryLaunchBtn = document.getElementById("primary-launch-btn");
    const primaryLaunchResult = document.getElementById("primary-launch-result");
    const advancedSection = document.getElementById("advanced-section");
    const advPlatform = document.getElementById("adv-platform");
    const advPreset = document.getElementById("adv-preset");
    const advContentId = document.getElementById("adv-content-id");
    const advLaunchBtn = document.getElementById("adv-launch-btn");
    const advLaunchResult = document.getElementById("adv-launch-result");

    let activeSlotId = null;
    let selectedPlatform = null;
    let selectedContentType = null;

    function updateLaunchEnabled() {
        primaryLaunchBtn.disabled = !(selectedPlatform && selectedContentType);
    }

    function selectApp(platform, chipEl) {
        selectedPlatform = platform;
        Array.from(appSelector.children).forEach((c) => c.classList.remove("selected"));
        if (chipEl) chipEl.classList.add("selected");
        updateLaunchEnabled();
    }

    function selectContentType(contentType, btnEl) {
        selectedContentType = contentType;
        toggleBtns.forEach((b) => b.classList.remove("selected"));
        btnEl.classList.add("selected");
        updateLaunchEnabled();
    }

    function populateAdvPresets() {
        const platform = advPlatform.value;
        const options = presets[platform] || [];
        advPreset.innerHTML = "";
        const blank = document.createElement("option");
        blank.value = "";
        blank.textContent = "-- choose a preset --";
        advPreset.appendChild(blank);
        options.forEach((opt) => {
            const el = document.createElement("option");
            el.value = opt.content_id;
            el.textContent = opt.label;
            advPreset.appendChild(el);
        });
    }
    advPlatform.addEventListener("change", populateAdvPresets);
    populateAdvPresets();

    async function openOverlay(tile) {
        activeSlotId = tile.dataset.slotId;
        selectedPlatform = null;
        selectedContentType = null;

        const channel = tile.dataset.channel;
        infoChannel.textContent = channel ? `CH${channel}` : activeSlotId;
        infoMeta.innerHTML =
            `${tile.dataset.deviceType} &middot; ` +
            `${tile.dataset.network || "network unknown"} &middot; ` +
            `${tile.dataset.ip || "no IP"}`;

        primaryLaunchResult.textContent = "";
        primaryLaunchResult.className = "launch-result";
        advLaunchResult.textContent = "";
        advLaunchResult.className = "launch-result";
        advContentId.value = "";
        advancedSection.open = false;

        toggleBtns.forEach((b) => b.classList.remove("selected"));
        appSelector.innerHTML = "";
        appSelectorEmpty.classList.add("hidden");
        updateLaunchEnabled();

        overlay.classList.remove("hidden");

        try {
            const resp = await fetch(`/api/devices/${encodeURIComponent(activeSlotId)}/apps`);
            const data = await resp.json();
            const apps = data.apps || [];
            if (apps.length === 0) {
                appSelectorEmpty.classList.remove("hidden");
            } else {
                apps.forEach((app) => {
                    const chip = document.createElement("button");
                    chip.type = "button";
                    chip.className = "app-chip";
                    chip.textContent = app.label;
                    chip.addEventListener("click", () => selectApp(app.platform, chip));
                    appSelector.appendChild(chip);
                });
                // Only one option in the common case (catalog fallback) —
                // pre-select it so operators just pick Live/VOD and go.
                if (apps.length === 1) {
                    selectApp(apps[0].platform, appSelector.children[0]);
                }
            }
        } catch (err) {
            appSelectorEmpty.classList.remove("hidden");
            appSelectorEmpty.textContent = "Couldn't load app info: " + err;
        }
    }

    function closeOverlay() {
        overlay.classList.add("hidden");
        activeSlotId = null;
    }

    grid.addEventListener("click", (e) => {
        const tile = e.target.closest(".tv-tile");
        if (tile) openOverlay(tile);
    });

    overlayClose.addEventListener("click", closeOverlay);
    overlay.addEventListener("click", (e) => {
        if (e.target === overlay) closeOverlay();
    });

    toggleBtns.forEach((btn) => {
        btn.addEventListener("click", () => selectContentType(btn.dataset.contentType, btn));
    });

    primaryLaunchBtn.addEventListener("click", async () => {
        if (!selectedPlatform || !selectedContentType) return;

        primaryLaunchBtn.disabled = true;
        primaryLaunchResult.textContent = "Launching...";
        primaryLaunchResult.className = "launch-result";

        try {
            const resp = await fetch("/api/launch_auto", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    slot_id: activeSlotId,
                    platform: selectedPlatform,
                    content_type: selectedContentType,
                }),
            });
            const data = await resp.json();
            const label = data.launched_title ? ` — "${data.launched_title}"` : "";
            primaryLaunchResult.textContent = (data.message || "") + label;
            primaryLaunchResult.className = "launch-result " + (data.success ? "success" : "error");
        } catch (err) {
            primaryLaunchResult.textContent = "Request failed: " + err;
            primaryLaunchResult.className = "launch-result error";
        } finally {
            updateLaunchEnabled();
        }
    });

    advLaunchBtn.addEventListener("click", async () => {
        // Blank is valid here — it means "just open the app", for
        // platforms without a working deep-link format yet.
        const contentId = advContentId.value.trim() || advPreset.value;

        advLaunchBtn.disabled = true;
        advLaunchResult.textContent = "Launching...";
        advLaunchResult.className = "launch-result";

        try {
            const resp = await fetch("/api/launch", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    slot_id: activeSlotId,
                    platform: advPlatform.value,
                    content_id: contentId,
                }),
            });
            const data = await resp.json();
            advLaunchResult.textContent = data.message;
            advLaunchResult.className = "launch-result " + (data.success ? "success" : "error");
        } catch (err) {
            advLaunchResult.textContent = "Request failed: " + err;
            advLaunchResult.className = "launch-result error";
        } finally {
            advLaunchBtn.disabled = false;
        }
    });

    function refreshStatus() {
        fetch(`/api/tv/${encodeURIComponent(tvId)}/status`)
            .then((resp) => resp.json())
            .then((statuses) => {
                document.querySelectorAll(".tv-tile").forEach((tile) => {
                    const slotId = tile.dataset.slotId;
                    const dot = tile.querySelector("[data-status-dot]");
                    const info = statuses[slotId];
                    if (!info) {
                        dot.className = "status-dot status-dot-unknown";
                        dot.title = "unknown";
                        return;
                    }
                    dot.title = info.detail;
                    if (!info.online) {
                        dot.className = "status-dot status-dot-offline";
                    } else if (info.detail && info.detail.indexOf("unauthorized") !== -1) {
                        dot.className = "status-dot status-dot-warn";
                    } else {
                        dot.className = "status-dot status-dot-online";
                    }
                });
            })
            .catch(() => {});
    }

    refreshStatus();
    setInterval(refreshStatus, 15000);
})();
