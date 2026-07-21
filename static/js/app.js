(function () {
    const grid = document.querySelector(".device-grid");
    if (!grid) return;

    const network = grid.dataset.network;
    const presets = JSON.parse(document.getElementById("presets-data").textContent);

    const modal = document.getElementById("launch-modal");
    const modalTitle = document.getElementById("modal-slot-title");
    const platformSelect = document.getElementById("platform-select");
    const presetSelect = document.getElementById("preset-select");
    const customInput = document.getElementById("custom-content-id");
    const launchBtn = document.getElementById("launch-btn");
    const launchResult = document.getElementById("launch-result");
    const closeBtn = document.getElementById("modal-close");
    const assignedBox = document.getElementById("assigned-box");
    const assignedText = document.getElementById("assigned-text");
    const useAssignedBtn = document.getElementById("use-assigned-btn");

    let activeSlotId = null;
    let activeAssigned = null;

    function ensurePlatformOption(platform) {
        const exists = Array.from(platformSelect.options).some((o) => o.value === platform);
        if (!exists) {
            const el = document.createElement("option");
            el.value = platform;
            el.textContent = platform + " (assigned)";
            platformSelect.appendChild(el);
        }
    }

    function populatePresets() {
        const platform = platformSelect.value;
        const options = presets[platform] || [];
        presetSelect.innerHTML = "";
        const blank = document.createElement("option");
        blank.value = "";
        blank.textContent = "-- choose a preset --";
        presetSelect.appendChild(blank);
        options.forEach((opt) => {
            const el = document.createElement("option");
            el.value = opt.content_id;
            el.textContent = opt.label;
            presetSelect.appendChild(el);
        });
    }

    function openModal(tile) {
        activeSlotId = tile.dataset.slotId;
        modalTitle.textContent = `Launch on ${activeSlotId}`;
        customInput.value = "";
        launchResult.textContent = "";
        launchResult.className = "launch-result";

        // Drop any "(assigned)" option left over from a previous tile.
        Array.from(platformSelect.options).forEach((o) => {
            if (o.textContent.endsWith("(assigned)")) o.remove();
        });

        const savedPlatform = tile.dataset.platform;
        if (savedPlatform && presets[savedPlatform]) {
            platformSelect.value = savedPlatform;
        }
        populatePresets();

        activeAssigned = tile.dataset.assignedPlatform
            ? {
                  platform: tile.dataset.assignedPlatform,
                  title: tile.dataset.assignedTitle,
                  type: tile.dataset.assignedType,
                  contentId: tile.dataset.assignedContentId,
                  restricted: tile.dataset.assignedRestricted === "true",
              }
            : null;

        if (activeAssigned) {
            let text = `Assigned: ${activeAssigned.title} (${activeAssigned.type}) on ${activeAssigned.platform}`;
            if (activeAssigned.restricted) text += " — ⚠ OPS-only, will be blocked here";
            if (!activeAssigned.contentId) text += " — no content ID mapped yet, use manual entry below";
            assignedText.textContent = text;
            useAssignedBtn.disabled = !activeAssigned.contentId;
            assignedBox.classList.remove("hidden");
        } else {
            assignedBox.classList.add("hidden");
        }

        modal.classList.remove("hidden");
    }

    function closeModal() {
        modal.classList.add("hidden");
        activeSlotId = null;
        activeAssigned = null;
    }

    useAssignedBtn.addEventListener("click", () => {
        if (!activeAssigned || !activeAssigned.contentId) return;
        ensurePlatformOption(activeAssigned.platform);
        platformSelect.value = activeAssigned.platform;
        populatePresets();
        customInput.value = activeAssigned.contentId;
    });

    grid.addEventListener("click", (e) => {
        const tile = e.target.closest(".device-tile");
        if (tile) openModal(tile);
    });

    closeBtn.addEventListener("click", closeModal);
    modal.addEventListener("click", (e) => {
        if (e.target === modal) closeModal();
    });

    platformSelect.addEventListener("change", populatePresets);

    launchBtn.addEventListener("click", async () => {
        // Blank is valid — it means "just open the app", for platforms
        // without a working deep-link format yet.
        const contentId = customInput.value.trim() || presetSelect.value;

        launchBtn.disabled = true;
        launchResult.textContent = "Launching...";
        launchResult.className = "launch-result";

        try {
            const resp = await fetch("/api/launch", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    slot_id: activeSlotId,
                    platform: platformSelect.value,
                    content_id: contentId,
                }),
            });
            const data = await resp.json();
            launchResult.textContent = data.message;
            launchResult.className = "launch-result " + (data.success ? "success" : "error");
        } catch (err) {
            launchResult.textContent = "Request failed: " + err;
            launchResult.className = "launch-result error";
        } finally {
            launchBtn.disabled = false;
        }
    });

    function refreshStatus() {
        fetch(`/api/network/${encodeURIComponent(network)}/status`)
            .then((resp) => resp.json())
            .then((statuses) => {
                document.querySelectorAll(".device-tile").forEach((tile) => {
                    const slotId = tile.dataset.slotId;
                    const badge = tile.querySelector("[data-status-badge]");
                    const info = statuses[slotId];
                    if (!info) {
                        badge.textContent = "unknown";
                        badge.className = "device-tile-status status-unknown";
                        return;
                    }
                    badge.textContent = info.detail;
                    if (!info.online) {
                        badge.className = "device-tile-status status-offline";
                    } else if (info.detail && info.detail.indexOf("unauthorized") !== -1) {
                        badge.className = "device-tile-status status-warn";
                    } else {
                        badge.className = "device-tile-status status-online";
                    }
                });
            })
            .catch(() => {});
    }

    refreshStatus();
    setInterval(refreshStatus, 15000);

    const scanBtn = document.getElementById("scan-btn");
    const scanStatus = document.getElementById("scan-status");

    if (scanBtn) {
        scanBtn.addEventListener("click", async () => {
            scanBtn.disabled = true;
            scanBtn.textContent = "Scanning...";
            scanStatus.classList.remove("hidden");
            scanStatus.textContent = `Scanning ${network} — this can take up to a minute...`;

            try {
                const resp = await fetch(`/api/scan/${encodeURIComponent(network)}`, { method: "POST" });
                const data = await resp.json();
                if (data.error) {
                    scanStatus.textContent = `Scan failed: ${data.error}`;
                } else {
                    scanStatus.textContent =
                        `Scan complete: ${data.matched.length} known device(s) updated, ` +
                        `${data.unregistered.length} unregistered device(s) found, ` +
                        `${data.cleared.length} no longer seen on ${network}. Reloading...`;
                    setTimeout(() => window.location.reload(), 1500);
                }
            } catch (err) {
                scanStatus.textContent = "Scan request failed: " + err;
            } finally {
                scanBtn.disabled = false;
                scanBtn.textContent = "Scan this network";
            }
        });
    }
})();
