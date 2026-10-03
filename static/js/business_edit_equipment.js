const csrfToken =
    document
        .querySelector('meta[name="csrf-token"]')
        ?.getAttribute("content");
document.addEventListener("DOMContentLoaded", function () {

    const deleteButton = document.getElementById("deleteEquipmentButton");
    const deleteModal = document.getElementById("deleteModal");
    const resultModal = document.getElementById("resultModal");

    const closeDeleteModal = document.getElementById("closeDeleteModal");
    const cancelDelete = document.getElementById("cancelDelete");
    const confirmDelete = document.getElementById("confirmDelete");

    const closeResultModal = document.getElementById("closeResultModal");
    const resultButton = document.getElementById("resultButton");

    const resultIcon = document.getElementById("resultIcon");
    const resultTitle = document.getElementById("resultTitle");
    const resultMessage = document.getElementById("resultMessage");


    // =========================
    // SAFETY CHECK
    // =========================

    if (!deleteButton) {
        console.error("Delete button not found.");
        return;
    }


    const deleteUrl = deleteButton.dataset.deleteUrl;


    // =========================
    // OPEN DELETE MODAL
    // =========================

    deleteButton.addEventListener("click", function () {

        deleteModal.classList.add("active");

    });


    // =========================
    // CLOSE DELETE MODAL
    // =========================

    function closeDeleteConfirmation() {

        deleteModal.classList.remove("active");

    }

    closeDeleteModal.addEventListener(
        "click",
        closeDeleteConfirmation
    );

    cancelDelete.addEventListener(
        "click",
        closeDeleteConfirmation
    );


    // =========================
    // CONFIRM DELETE
    // =========================

    confirmDelete.addEventListener("click", async function () {

        confirmDelete.disabled = true;
        confirmDelete.textContent = "Deleting...";

        try {

            const response = await fetch(
                deleteUrl,
                {
                    method: "POST",
                    headers: {
                        "X-Requested-With": "XMLHttpRequest",
                        "X-CSRFToken": csrfToken
                    }
                }
            );

            const data = await response.json();

            closeDeleteConfirmation();


            // =========================
            // SUCCESS
            // =========================

            if (data.success) {

                resultIcon.textContent = "✓";
                resultIcon.className =
                    "modal-icon success-icon";

                resultTitle.textContent =
                    "Equipment Deleted";

                resultMessage.textContent =
                    "The equipment has been successfully removed from your inventory.";

                resultModal.classList.add("active");


                resultButton.onclick = function () {

                    window.location.href =
                        "/business-dashboard";

                };

            }


            // =========================
            // CANNOT DELETE / ERROR
            // =========================

            else {

                resultIcon.textContent = "!";
                resultIcon.className =
                    "modal-icon warning-icon";

                resultTitle.textContent =
                    "Cannot Delete Equipment";

                resultMessage.textContent =
                    data.message ||
                    "This equipment cannot be deleted.";

                resultModal.classList.add("active");


                resultButton.onclick = function () {

                    resultModal.classList.remove("active");

                };

            }

        }

        catch (error) {

            console.error(
                "Delete request failed:",
                error
            );

            closeDeleteConfirmation();

            resultIcon.textContent = "!";
            resultIcon.className =
                "modal-icon warning-icon";

            resultTitle.textContent =
                "Something Went Wrong";

            resultMessage.textContent =
                "Unable to delete the equipment. Please try again.";

            resultModal.classList.add("active");


            resultButton.onclick = function () {

                resultModal.classList.remove("active");

            };

        }

        finally {

            confirmDelete.disabled = false;
            confirmDelete.textContent = "Yes, Delete";

        }

    });


    // =========================
    // CLOSE RESULT MODAL
    // =========================

    closeResultModal.addEventListener(
        "click",
        function () {

            resultModal.classList.remove("active");

        }
    );


    // =========================
    // CLICK OUTSIDE MODAL
    // =========================

    deleteModal.addEventListener(
        "click",
        function (event) {

            if (event.target === deleteModal) {
                closeDeleteConfirmation();
            }

        }
    );


    resultModal.addEventListener(
        "click",
        function (event) {

            if (event.target === resultModal) {
                resultModal.classList.remove("active");
            }

        }
    );

});