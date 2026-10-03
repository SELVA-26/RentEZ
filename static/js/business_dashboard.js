const csrfToken =
    document
        .querySelector('meta[name="csrf-token"]')
        ?.getAttribute("content");
document.addEventListener("DOMContentLoaded", function () {

    const buttons = document.querySelectorAll(".status-btn");

    /*
    =====================================================
    CUSTOM CONFIRMATION MODAL
    =====================================================
    */

    function showStatusModal(button) {

        const equipmentId = button.dataset.equipmentId;
        const isActive = button.dataset.active === "true";

        const action = isActive
            ? "deactivate"
            : "reactivate";

        const title = isActive
            ? "Deactivate Equipment?"
            : "Reactivate Equipment?";

        const message = isActive
            ? "This equipment will be removed from customer listings. You can reactivate it anytime."
            : "This equipment will become visible to customers again.";

        const icon = isActive
            ? `
                <svg
                    viewBox="0 0 24 24"
                    aria-hidden="true">
                    <path
                        d="M2.5 12s3.5-5.5 9.5-5.5S21.5 12 21.5 12
                        18 17.5 12 17.5S2.5 12 2.5 12Z"
                        fill="none"
                        stroke="currentColor"
                        stroke-width="1.8"
                        stroke-linecap="round"
                        stroke-linejoin="round">
                    </path>

                    <circle
                        cx="12"
                        cy="12"
                        r="2.8"
                        fill="none"
                        stroke="currentColor"
                        stroke-width="1.8">
                    </circle>

                    <path
                        d="M4 4l16 16"
                        fill="none"
                        stroke="currentColor"
                        stroke-width="1.8"
                        stroke-linecap="round">
                    </path>
                </svg>
            `
            : `
                <svg
                    viewBox="0 0 24 24"
                    aria-hidden="true">
                    <path
                        d="M2.5 12s3.5-5.5 9.5-5.5S21.5 12 21.5 12
                        18 17.5 12 17.5 2.5 12 2.5 12Z"
                        fill="none"
                        stroke="currentColor"
                        stroke-width="1.8"
                        stroke-linecap="round"
                        stroke-linejoin="round">
                    </path>

                    <circle
                        cx="12"
                        cy="12"
                        r="2.8"
                        fill="none"
                        stroke="currentColor"
                        stroke-width="1.8">
                    </circle>
                </svg>
            `;

        const actionText = isActive
            ? "Deactivate"
            : "Reactivate";

        const actionClass = isActive
            ? "danger"
            : "primary";


        const overlay = document.createElement("div");

        overlay.className = "status-modal-overlay";

        overlay.innerHTML = `
            <div class="status-modal">

                <button
                    type="button"
                    class="status-modal-close"
                    aria-label="Close">
                    <i class="ri-close-line"></i>
                </button>

                <div class="status-modal-icon ${actionClass}">
                    ${icon}
                </div>

                <h3>${title}</h3>

                <p>${message}</p>

                <div class="status-modal-actions">

                    <button
                        type="button"
                        class="modal-cancel">
                        Cancel
                    </button>

                    <button
                        type="button"
                        class="modal-confirm ${actionClass}">
                        ${actionText}
                    </button>

                </div>

            </div>
        `;

        document.body.appendChild(overlay);

        requestAnimationFrame(() => {
            overlay.classList.add("show");
        });


        function closeModal() {

            overlay.classList.remove("show");

            setTimeout(() => {
                overlay.remove();
            }, 200);
        }


        overlay.querySelector(".status-modal-close")
            .addEventListener("click", closeModal);

        overlay.querySelector(".modal-cancel")
            .addEventListener("click", closeModal);


        overlay.addEventListener("click", function (event) {

            if (event.target === overlay) {
                closeModal();
            }

        });


        overlay.querySelector(".modal-confirm")
            .addEventListener("click", async function () {

                const confirmButton = this;

                confirmButton.disabled = true;

                confirmButton.innerHTML = `
                    <i class="ri-loader-4-line spinning"></i>
                    Please wait...
                `;

                try {

                    const response = await fetch(
                        `/business/toggle-equipment/${equipmentId}`,
                        {
                            method: "POST",
                            headers: {
                                "Content-Type": "application/json",
                                "X-CSRFToken": csrfToken
                            }
                        }
                    );

                    const data = await response.json();

                    if (!data.success) {
                        throw new Error(
                            data.message ||
                            "Unable to update equipment."
                        );
                    }

                    closeModal();

                    window.location.reload();

                } catch (error) {

                    confirmButton.disabled = false;

                    confirmButton.innerHTML = actionText;

                    rentEZMessage(
                        error.message ||
                        "Unable to update equipment.",
                        "error",
                        "Equipment Update Failed"
                    );
                }

            });
    }


    /*
    =====================================================
    EQUIPMENT STATUS BUTTONS
    =====================================================
    */

    buttons.forEach(function (button) {

        button.addEventListener("click", function () {
            showStatusModal(this);
        });

    });

});