document.addEventListener(
    "DOMContentLoaded",
    function () {

        const cartPage =
            document.querySelector(
                ".cart-page"
            );


        if (!cartPage) {
            return;
        }


        const totalDays =
            Number(
                cartPage.dataset.totalDays || 0
            );


        const csrfToken =
            document
                .querySelector(
                    'meta[name="csrf-token"]'
                )
                ?.getAttribute(
                    "content"
                )
            || "";


        function money(value) {

            return (
                "₹" +
                Math.round(
                    Number(value) || 0
                )
                .toLocaleString("en-IN")
            );

        }


        function updateTotals() {

            let subtotal = 0;


            document
                .querySelectorAll(
                    ".cart-quantity-control"
                )
                .forEach(
                    function (control) {

                        const unitPrice =
                            Number(
                                control.dataset.unitPrice
                                || 0
                            );


                        const quantity =
                            Number(
                                control.dataset.quantity
                                || 0
                            );


                        const lineTotal =
                            unitPrice *
                            quantity *
                            totalDays;


                        const row =
                            control.closest(
                                ".cart-item"
                            );


                        const lineTotalElement =
                            row?.querySelector(
                                "[data-line-total]"
                            );


                        if (
                            lineTotalElement
                        ) {

                            lineTotalElement.textContent =
                                `${money(
                                    lineTotal
                                )} total`;

                        }


                        subtotal +=
                            lineTotal;

                    }
                );


            document
                .querySelectorAll(
                    "[data-cart-subtotal]"
                )
                .forEach(
                    function (element) {

                        element.textContent =
                            money(
                                subtotal
                            );

                    }
                );


            document
                .querySelectorAll(
                    "[data-cart-total]"
                )
                .forEach(
                    function (element) {

                        element.textContent =
                            money(
                                subtotal
                            );

                    }
                );

        }


        function updateControlState(
            control
        ) {

            const quantity =
                Number(
                    control.dataset.quantity
                    || 0
                );


            const rawMaxQuantity =
                Number(
                    control.dataset.maxQuantity
                );

            const maxQuantity =
                Number.isFinite(
                    rawMaxQuantity
                )
                    ? Math.min(
                        Math.max(
                            rawMaxQuantity,
                            0
                        ),
                        100
                    )
                    : 100;


            const decreaseButton =
                control.querySelector(
                    ".cart-quantity-decrease"
                );


            const increaseButton =
                control.querySelector(
                    ".cart-quantity-increase"
                );


            const valueElement =
                control.querySelector(
                    ".cart-quantity-value"
                );


            if (valueElement) {

                valueElement.textContent =
                    quantity;

            }


            if (decreaseButton) {

                decreaseButton.disabled =
                    quantity <= 0;

            }


            if (increaseButton) {

                increaseButton.disabled =
                    quantity >= maxQuantity ||
                    quantity >= 100;

            }

        }


        function showMessage(
            message
        ) {

            let toast =
                document.getElementById(
                    "cartQuantityToast"
                );


            if (!toast) {

                toast =
                    document.createElement(
                        "div"
                    );


                toast.id =
                    "cartQuantityToast";


                toast.className =
                    "cart-quantity-toast";


                document.body.appendChild(
                    toast
                );

            }


            toast.textContent =
                message;


            toast.classList.add(
                "show"
            );


            clearTimeout(
                window.cartQuantityToastTimer
            );


            window.cartQuantityToastTimer =
                setTimeout(
                    function () {

                        toast.classList.remove(
                            "show"
                        );

                    },
                    2600
                );

        }


        function updateCartBadge(
            count
        ) {

            const cartLink =
                document.querySelector(
                    ".cart-link"
                );


            if (!cartLink) {
                return;
            }


            let badge =
                cartLink.querySelector(
                    ".cart-badge"
                );


            if (count > 0) {

                if (!badge) {

                    badge =
                        document.createElement(
                            "span"
                        );


                    badge.className =
                        "cart-badge";


                    cartLink.appendChild(
                        badge
                    );

                }


                badge.textContent =
                    count;

            }

            else if (badge) {

                badge.remove();

            }

        }


        async function changeQuantity(
            control,
            action
        ) {

            if (
                control.dataset.busy ===
                "true"
            ) {

                return;
            }


            control.dataset.busy =
                "true";


            updateControlState(
                control
            );


            const buttons =
                control.querySelectorAll(
                    ".cart-quantity-btn"
                );


            buttons.forEach(
                function (button) {

                    button.disabled =
                        true;

                }
            );


            try {

                const response =
                    await fetch(
                        "/cart/change-quantity",
                        {

                            method:
                                "POST",

                            headers: {

                                "Content-Type":
                                    "application/json",

                                "X-CSRFToken":
                                    csrfToken

                            },

                            body:
                                JSON.stringify({

                                    item_type:
                                        control.dataset.itemType,

                                    item_id:
                                        Number(
                                            control.dataset.itemId
                                        ),

                                    action:
                                        action

                                })

                        }
                    );


                const data =
                    await response.json();
                                if (response.status === 403) {

                    window.location.reload();

                    return;
                }

                if (
                    !response.ok ||
                    !data.success
                ) {

                    if (
                        data.max_quantity
                        !== undefined
                    ) {

                        control.dataset.maxQuantity =
                            Math.min(
                                Number(
                                    data.max_quantity
                                ),
                                100
                            );

                    }


                    showMessage(
                        data.message ||
                        "Unable to update the quantity."
                    );


                    return;

                }


                const newQuantity =
                    Number(
                        data.quantity || 0
                    );


                // -----------------------------------------
                // ITEM REMOVED
                // -----------------------------------------

                if (
                    newQuantity === 0
                ) {

                    const row =
                        control.closest(
                            ".cart-item"
                        );


                    if (row) {

                        row.remove();

                    }


                    updateCartBadge(
                        Number(
                            data.cart_count
                            || 0
                        )
                    );


                    if (
                        data.cart_empty
                    ) {

                        window.location.reload();

                        return;

                    }


                    updateTotals();

                }


                // -----------------------------------------
                // ITEM QUANTITY UPDATED
                // -----------------------------------------

                else {

                    control.dataset.quantity =
                        newQuantity;


                    if (
                        data.max_quantity
                        !== undefined
                    ) {

                        control.dataset.maxQuantity =
                            Math.min(
                                Number(
                                    data.max_quantity
                                ),
                                100
                            );

                    }


                    updateControlState(
                        control
                    );


                    updateTotals();


                    updateCartBadge(
                        Number(
                            data.cart_count
                            || 0
                        )
                    );

                }

            }

            catch (error) {

                console.error(
                    "Cart quantity update failed:",
                    error
                );


                showMessage(
                    "Unable to update the cart. Please try again."
                );

            }


            finally {

                if (
                    document.body.contains(
                        control
                    )
                ) {

                    control.dataset.busy =
                        "false";


                    updateControlState(
                        control
                    );

                }

            }

        }


        document.addEventListener(
            "click",
            function (event) {

                const button =
                    event.target.closest(
                        ".cart-quantity-btn"
                    );


                if (!button) {
                    return;
                }


                const control =
                    button.closest(
                        ".cart-quantity-control"
                    );


                if (!control) {
                    return;
                }


                const action =
                    button.classList.contains(
                        "cart-quantity-increase"
                    )
                        ? "increase"
                        : "decrease";


                changeQuantity(
                    control,
                    action
                );

            }
        );


        document
            .querySelectorAll(
                ".cart-quantity-control"
            )
            .forEach(
                function (control) {

                    updateControlState(
                        control
                    );

                }
            );


        updateTotals();

    }
);