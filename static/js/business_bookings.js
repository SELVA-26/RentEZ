const csrfToken =
    document
        .querySelector('meta[name="csrf-token"]')
        ?.getAttribute("content");
document.addEventListener("DOMContentLoaded", function () {

    const cancelButtons =
        document.querySelectorAll(".cancel-btn");

    cancelButtons.forEach(function (button) {

        button.addEventListener("click", function () {

            const bookingId =
                this.dataset.bookingId;

            const paymentStatus =
                this.dataset.paymentStatus;

            openBusinessCancelModal(
                bookingId,
                paymentStatus
            );

        });

    });


    function openBusinessCancelModal(
        bookingId,
        paymentStatus
    ) {

        const overlay =
            document.createElement("div");

        overlay.className =
            "business-cancel-overlay";

        const paid =
            paymentStatus === "Paid";

        overlay.innerHTML = `
            <div class="business-cancel-modal">

                <button
                    class="business-cancel-close"
                    type="button">
                    <i class="ri-close-line"></i>
                </button>

                <div class="business-cancel-icon">
                    <i class="ri-error-warning-line"></i>
                </div>

                <h2>
                    ${paid
                        ? "Cancel Booking & Refund Customer?"
                        : "Cancel Booking?"
                    }
                </h2>

                <p>
                    ${
                        paid
                        ? "This booking will be cancelled and the customer's payment for this booking will be refunded."
                        : "This booking will be cancelled and the customer will be notified."
                    }
                </p>

                <div class="business-cancel-actions">

                    <button
                        type="button"
                        class="business-cancel-no">
                             Go Back
                    </button>

                    <button
                        type="button"
                        class="business-cancel-yes">
                        ${paid
                            ? "Cancel & Refund Customer"
                            : "Cancel Booking"
                        }
                    </button>

                </div>

            </div>
        `;

        document.body.appendChild(overlay);

        requestAnimationFrame(function () {
            overlay.classList.add("show");
        });


        function closeModal() {

            overlay.classList.remove("show");

            setTimeout(function () {
                overlay.remove();
            }, 180);
        }


        overlay.querySelector(
            ".business-cancel-close"
        ).addEventListener(
            "click",
            closeModal
        );


        overlay.querySelector(
            ".business-cancel-no"
        ).addEventListener(
            "click",
            closeModal
        );


        overlay.querySelector(
            ".business-cancel-yes"
        ).addEventListener(
            "click",
            async function () {

                const confirmButton = this;

                confirmButton.disabled = true;

                confirmButton.innerHTML = `
                    <i class="ri-loader-4-line spinning"></i>
                    Processing...
                `;

                try {

                    const response =
                        await fetch(
                            `/business/cancel-booking/${bookingId}`,
                            {
                                method: "POST",
                                headers: {
                                    "X-CSRFToken": csrfToken
                                }
                            }
                        );

                    const data =
                        await response.json();

                    if (!data.success) {
                        throw new Error(
                            data.message ||
                            "Unable to cancel booking."
                        );
                    }

                    closeModal();

                    window.location.reload();

                } catch (error) {

                    confirmButton.disabled = false;

                    confirmButton.textContent =
                        paid
                        ? "Cancel & Refund"
                        : "Cancel Booking";

                    rentEZMessage(
                        error.message ||
                        "Unable to cancel the booking.",
                        "error",
                        "Cancellation Failed"
                    );
                }

            }
        );

    }

});