const csrfToken =
    document
        .querySelector(
            'meta[name="csrf-token"]'
        )
        ?.getAttribute("content");


document.addEventListener(
    "DOMContentLoaded",
    function () {

        let paymentCompleted = false;
        let paymentFailureRecorded = false;


        const options = {

            key: razorpayKey,

            amount: razorpayAmount,

            currency: "INR",

            name: "RentEZ",

            description:
                "RentEZ Rental Order",

            order_id:
                razorpayOrderId,


            handler: function (response) {

                paymentCompleted = true;

                const payButton =
                    document.getElementById("pay-btn");

                if (payButton) {

                    payButton.disabled = true;

                    payButton.innerHTML = `
                        <span>
                            Payment successful...
                        </span>
                        <i class="ri-loader-4-line"></i>
                    `;

                }


                fetch(
                    "/order-payment-success",
                    {

                        method: "POST",

                        headers: {

                            "Content-Type":
                                "application/json",

                            "X-CSRFToken":
                                csrfToken

                        },

                        body: JSON.stringify({

                            order_id:
                                orderId,

                            razorpay_payment_id:
                                response
                                    .razorpay_payment_id,

                            razorpay_order_id:
                                response
                                    .razorpay_order_id,

                            razorpay_signature:
                                response
                                    .razorpay_signature

                        })

                    }
                )

                .then(
                    response =>
                        response.json()
                )

                .then(data => {

                    if (data.success) {

                        window.location.href =
                            data.redirect;

                        return;
                    }

                    if (
                        typeof rentEZMessage ===
                        "function"
                    ) {

                        rentEZMessage(
                            data.message ||
                            "Unable to verify the payment.",
                            "error",
                            "Payment Verification Failed"
                        );

                    } else {

                        alert(
                            data.message ||
                            "Unable to verify the payment."
                        );

                    }

                })

                .catch(error => {

                    console.error(error);

                    alert(
                        "Something went wrong while "
                        + "verifying your payment."
                    );

                });

            },


            modal: {

                ondismiss: function () {

                    if (paymentCompleted) {
                        return;
                    }

                    console.log(
                        "Razorpay window closed."
                    );

                }

            },


            theme: {
                color: "#2563EB"
            }

        };


        const rzp =
            new Razorpay(options);


        rzp.on(
            "payment.failed",
            function (response) {

                if (paymentFailureRecorded) {
                    return;
                }

                paymentFailureRecorded = true;


                fetch(
                    "/order-payment-failed",
                    {

                        method: "POST",

                        headers: {

                            "Content-Type":
                                "application/json",

                            "X-CSRFToken":
                                csrfToken

                        },

                        body: JSON.stringify({

                            order_id:
                                orderId,

                            razorpay_order_id:
                                razorpayOrderId

                        })

                    }
                );

            }
        );


        document.getElementById(
            "pay-btn"
        ).onclick = function (e) {

            e.preventDefault();

            rzp.open();

        };

    }
);