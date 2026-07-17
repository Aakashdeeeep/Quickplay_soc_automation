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

    let activeSlotId = null;

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

        const savedPlatform = tile.dataset.platform;
        if (savedPlatform && presets[savedPlatform]) {
            platformSelect.value = savedPlatform;
        }
        populatePresets();

        modal.classList.remove("hidden");
    }

    function closeModal() {
        modal.classList.add("hidden");
        activeSlotId = null;
    }

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
        const contentId = customInput.value.trim() || presetSelect.value;
        if (!contentId) {
            launchResult.textContent = "Pick a preset or enter a content ID.";
            launchResult.className = "launch-result error";
            return;
        }

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
})();
