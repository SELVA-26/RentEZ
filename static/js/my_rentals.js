let selectedCancelForm = null;


// =========================
// OPEN CANCEL MODAL
// =========================

function openCancelModal(button) {

    selectedCancelForm =
        button.closest("form");

    const modal =
        document.getElementById("cancelModal");

    const title =
        document.getElementById("cancelModalTitle");

    const message =
        document.getElementById("cancelModalMessage");

    const confirmButton =
        document.getElementById("confirmCancelButton");

    if (!modal) {
        return;
    }

    const paymentStatus =
        button.dataset.paymentStatus;

    const isOrder =
        button.dataset.isOrder === "true";


    if (isOrder && paymentStatus === "Paid") {

        title.textContent =
            "Cancel Order & Refund?";

        message.textContent =
            "This will cancel every rental in this order and initiate a full refund to your original payment method.";

        confirmButton.textContent =
            "Cancel Order & Refund";

    } else if (isOrder) {

        title.textContent =
            "Cancel Order?";

        message.textContent =
            "This will cancel every rental in this order. This action cannot be undone.";

        confirmButton.textContent =
            "Yes, Cancel Order";

    } else if (paymentStatus === "Paid") {

        title.textContent =
            "Cancel Booking & Refund?";

        message.textContent =
            "Your booking will be cancelled and a full refund will be initiated to your original payment method.";

        confirmButton.textContent =
            "Cancel & Refund";

    } else {

        title.textContent =
            "Cancel Booking?";

        message.textContent =
            "Are you sure you want to cancel this unpaid booking?";

        confirmButton.textContent =
            "Yes, Cancel";
    }

    modal.classList.add("active");

    document.body.classList.add("modal-open");
}


// =========================
// CLOSE CANCEL MODAL
// =========================

function closeCancelModal() {

    const modal = document.getElementById("cancelModal");

    if (!modal) {
        return;
    }

    modal.classList.remove("active");

    document.body.classList.remove("modal-open");

    selectedCancelForm = null;
}


// =========================
// CONFIRM CANCELLATION
// =========================

function confirmCancellation() {

    if (selectedCancelForm) {

        selectedCancelForm.submit();

    }

}


// =========================
// CLICK OUTSIDE MODAL
// =========================

document.addEventListener("DOMContentLoaded", function () {

    const modal = document.getElementById("cancelModal");

    if (!modal) {
        return;
    }

    modal.addEventListener("click", function (event) {

        if (event.target === modal) {

            closeCancelModal();

        }

    });

});


// =========================
// ESCAPE KEY
// =========================

document.addEventListener("keydown", function (event) {

    if (event.key === "Escape") {

        closeCancelModal();

    }

});


document.addEventListener("DOMContentLoaded", function () {

    const pendingRefunds =
        document.querySelectorAll(
            '[data-payment-status="Refund Pending"]'
        );

    pendingRefunds.forEach(function (element) {

        const orderId =
            element.dataset.orderId;

        const bookingId =
            element.dataset.bookingId;

        const endpoint = orderId
            ? `/check-order-refund-status/${orderId}`
            : `/check-refund-status/${bookingId}`;


        async function checkRefund() {

            try {

                const response =
                    await fetch(endpoint);

                const data =
                    await response.json();

                if (!data.success) {
                    return;
                }

                if (
                    data.status === "Refunded"
                    || data.status === "Refund Failed"
                ) {

                    location.reload();

                }

            } catch (error) {

                console.error(
                    "Refund status check failed:",
                    error
                );

            }

        }

        checkRefund();

        setInterval(
            checkRefund,
            15000
        );

    });

});