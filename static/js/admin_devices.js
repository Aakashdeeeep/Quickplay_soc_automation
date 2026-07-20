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
})();
