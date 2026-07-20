(function () {
    const addBtn = document.getElementById("add-device-btn");
    if (!addBtn) return;

    const modal = document.getElementById("device-modal");
    const modalTitle = document.getElementById("device-modal-title");
    const modalClose = document.getElementById("device-modal-close");
    const saveBtn = document.getElementById("device-save-btn");
    const formResult = document.getElementById("device-form-result");

    const fSlotId = document.getElementById("f-slot-id");
    const fDeviceType = document.getElementById("f-device-type");
    const fMac = document.getElementById("f-mac-address");
    const fNetwork = document.getElementById("f-network");
    const fIp = document.getElementById("f-last-known-ip");
    const fPlatform = document.getElementById("f-platform");
    const fRokuAppId = document.getElementById("f-roku-app-id");
    const fFriendlyName = document.getElementById("f-friendly-name");

    let editingSlotId = null;

    function resetForm() {
        fSlotId.value = "";
        fDeviceType.selectedIndex = 0;
        fMac.value = "";
        fNetwork.value = "";
        fIp.value = "";
        fPlatform.value = "";
        fRokuAppId.value = "";
        fFriendlyName.value = "";
        formResult.textContent = "";
        formResult.className = "launch-result";
    }

    function openAdd() {
        editingSlotId = null;
        resetForm();
        modalTitle.textContent = "Add device";
        fSlotId.disabled = false;
        modal.classList.remove("hidden");
    }

    function openEdit(btn) {
        editingSlotId = btn.dataset.slotId;
        resetForm();
        modalTitle.textContent = `Edit ${editingSlotId}`;
        fSlotId.value = editingSlotId;
        fSlotId.disabled = true; // slot_id is the permanent key, not editable
        fDeviceType.value = btn.dataset.deviceType;
        fMac.value = btn.dataset.macAddress;
        fNetwork.value = btn.dataset.network;
        fIp.value = btn.dataset.lastKnownIp;
        fPlatform.value = btn.dataset.platform;
        fRokuAppId.value = btn.dataset.rokuAppId;
        fFriendlyName.value = btn.dataset.friendlyName;
        modal.classList.remove("hidden");
    }

    function closeModal() {
        modal.classList.add("hidden");
    }

    addBtn.addEventListener("click", openAdd);
    modalClose.addEventListener("click", closeModal);
    modal.addEventListener("click", (e) => {
        if (e.target === modal) closeModal();
    });

    document.querySelectorAll(".edit-device-btn").forEach((btn) => {
        btn.addEventListener("click", () => openEdit(btn));
    });

    document.querySelectorAll(".delete-device-btn").forEach((btn) => {
        btn.addEventListener("click", async () => {
            const slotId = btn.dataset.slotId;
            if (!confirm(`Remove ${slotId} from the registry? This does not affect the physical device.`)) {
                return;
            }
            const resp = await fetch(`/api/devices/${encodeURIComponent(slotId)}`, { method: "DELETE" });
            const data = await resp.json();
            if (data.success) {
                window.location.reload();
            } else {
                alert(data.message || "Delete failed.");
            }
        });
    });

    saveBtn.addEventListener("click", async () => {
        const payload = {
            slot_id: fSlotId.value.trim(),
            device_type: fDeviceType.value,
            mac_address: fMac.value.trim(),
            network: fNetwork.value,
            last_known_ip: fIp.value.trim(),
            platform: fPlatform.value.trim(),
            roku_app_id: fRokuAppId.value.trim(),
            friendly_name: fFriendlyName.value.trim(),
        };

        if (!payload.slot_id) {
            formResult.textContent = "Slot ID is required.";
            formResult.className = "launch-result error";
            return;
        }

        saveBtn.disabled = true;
        formResult.textContent = "Saving...";
        formResult.className = "launch-result";

        try {
            const url = editingSlotId
                ? `/api/devices/${encodeURIComponent(editingSlotId)}`
                : "/api/devices";
            const method = editingSlotId ? "PUT" : "POST";
            const resp = await fetch(url, {
                method,
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload),
            });
            const data = await resp.json();
            if (data.success) {
                window.location.reload();
            } else {
                formResult.textContent = data.message || "Save failed.";
                formResult.className = "launch-result error";
            }
        } catch (err) {
            formResult.textContent = "Request failed: " + err;
            formResult.className = "launch-result error";
        } finally {
            saveBtn.disabled = false;
        }
    });

    // ---- Add TV (bulk) ----

    const deviceTypes = JSON.parse(document.getElementById("device-types-data").textContent);

    const addTvBtn = document.getElementById("add-tv-btn");
    const addTvModal = document.getElementById("add-tv-modal");
    const addTvModalClose = document.getElementById("add-tv-modal-close");
    const tvName = document.getElementById("tv-name");
    const tvChannelCount = document.getElementById("tv-channel-count");
    const tvGenerateBtn = document.getElementById("tv-generate-btn");
    const tvRowsSection = document.getElementById("tv-rows-section");
    const tvRowsBody = document.getElementById("tv-rows-body");
    const tvFillType = document.getElementById("tv-fill-type");
    const tvFillAllBtn = document.getElementById("tv-fill-all-btn");
    const tvCreateBtn = document.getElementById("tv-create-btn");
    const tvCreateResult = document.getElementById("tv-create-result");

    function deviceTypeOptions(selected) {
        return deviceTypes.map((dt) =>
            `<option value="${dt}" ${dt === selected ? "selected" : ""}>${dt}</option>`
        ).join("");
    }

    function openAddTv() {
        tvName.value = "";
        tvChannelCount.value = 16;
        tvRowsSection.classList.add("hidden");
        tvRowsBody.innerHTML = "";
        tvCreateResult.textContent = "";
        tvCreateResult.className = "launch-result";
        addTvModal.classList.remove("hidden");
    }

    function closeAddTv() {
        addTvModal.classList.add("hidden");
    }

    addTvBtn.addEventListener("click", openAddTv);
    addTvModalClose.addEventListener("click", closeAddTv);
    addTvModal.addEventListener("click", (e) => {
        if (e.target === addTvModal) closeAddTv();
    });

    tvGenerateBtn.addEventListener("click", () => {
        const count = parseInt(tvChannelCount.value, 10);
        if (!tvName.value.trim() || !count || count < 1) {
            alert("Enter a TV name and a channel count of at least 1.");
            return;
        }
        tvRowsBody.innerHTML = "";
        for (let ch = 1; ch <= count; ch++) {
            const tr = document.createElement("tr");
            tr.innerHTML = `
                <td>CH${ch}</td>
                <td><select class="tv-row-type">${deviceTypeOptions(deviceTypes[0])}</select></td>
                <td><input type="text" class="tv-row-mac" placeholder="optional"></td>
            `;
            tvRowsBody.appendChild(tr);
        }
        tvRowsSection.classList.remove("hidden");
        tvCreateResult.textContent = "";
        tvCreateResult.className = "launch-result";
    });

    tvFillAllBtn.addEventListener("click", () => {
        const value = tvFillType.value;
        tvRowsBody.querySelectorAll(".tv-row-type").forEach((sel) => {
            sel.value = value;
        });
    });

    tvCreateBtn.addEventListener("click", async () => {
        const tvId = tvName.value.trim();
        if (!tvId) {
            alert("Enter a TV name.");
            return;
        }

        const rows = Array.from(tvRowsBody.querySelectorAll("tr"));
        const devices = rows.map((tr, idx) => ({
            slot_id: `${tvId}-CH${idx + 1}`,
            device_type: tr.querySelector(".tv-row-type").value,
            mac_address: tr.querySelector(".tv-row-mac").value.trim(),
        }));

        tvCreateBtn.disabled = true;
        tvCreateResult.textContent = "Creating...";
        tvCreateResult.className = "launch-result";

        try {
            const resp = await fetch("/api/devices/bulk", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ devices }),
            });
            const data = await resp.json();
            const failed = (data.results || []).filter((r) => !r.success);

            if (failed.length === 0) {
                tvCreateResult.textContent = `Created all ${data.created_count} channels for ${tvId}. Reloading...`;
                tvCreateResult.className = "launch-result success";
                setTimeout(() => window.location.reload(), 1200);
            } else {
                const lines = failed.map((r) => `${r.slot_id}: ${r.message}`).join("\n");
                tvCreateResult.textContent =
                    `Created ${data.created_count}/${data.total}. Failed:\n${lines}`;
                tvCreateResult.className = "launch-result error";
                tvCreateResult.style.whiteSpace = "pre-line";
            }
        } catch (err) {
            tvCreateResult.textContent = "Request failed: " + err;
            tvCreateResult.className = "launch-result error";
        } finally {
            tvCreateBtn.disabled = false;
        }
    });
})();
