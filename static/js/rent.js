document.addEventListener(
    "DOMContentLoaded",
    function () {

        const startInput =
            document.getElementById(
                "startDate"
            );

        const endInput =
            document.getElementById(
                "endDate"
            );


        const totalDaysElement =
            document.getElementById(
                "totalDays"
            );

        const totalPriceElement =
            document.getElementById(
                "totalPrice"
            );


        const dateError =
            document.getElementById(
                "dateError"
            );


        const continueBtn =
            document.getElementById(
                "continueBtn"
            );


        const cartStepper =
            document.getElementById(
                "cartStepper"
            );


        const cartMinus =
            document.getElementById(
                "cartMinus"
            );


        const cartPlus =
            document.getElementById(
                "cartPlus"
            );


        const cartQuantityValue =
    document.getElementById(
        "cartQuantityValue"
    );


const quantityAvailableElement =
    document.getElementById(
        "quantityAvailable"
    );


    if (
        !startInput ||
        !endInput ||
        !totalDaysElement ||
        !totalPriceElement ||
        !dateError ||
        !continueBtn ||
        !cartStepper ||
        !cartMinus ||
        !cartPlus ||
        !cartQuantityValue ||
        !quantityAvailableElement
    ) {

        console.error(
            "RentEZ quantity controls are missing from the page."
        );

        return;
    }


        let quantity =
            Number(
                currentQuantity || 0
            );


        let maxQuantity = 0;

        let busy = false;

        let cartCurrentlyHasItems =
            Boolean(
                cartHasItems
            );


        let startPicker = null;

        let endPicker = null;


        function showError(message) {

            const span =
                dateError.querySelector(
                    "span"
                );


            if (span) {

                span.textContent =
                    message;

            }


            dateError.style.display =
                "flex";
        }


        function clearError() {

            dateError.style.display =
                "none";

        }


        function updateCartBadge(count) {

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


        function calculateTotal() {

            if (
                !startInput.value ||
                !endInput.value
            ) {

                totalDaysElement.textContent =
                    "0 days";

                totalPriceElement.textContent =
                    "₹0";

                return;
            }


            const start =
                new Date(
                    `${startInput.value}T00:00:00`
                );


            const end =
                new Date(
                    `${endInput.value}T00:00:00`
                );


            const difference =
                (
                    end - start
                )
                /
                (
                    1000 *
                    60 *
                    60 *
                    24
                );


            if (difference <= 0) {

                totalDaysElement.textContent =
                    "0 days";

                totalPriceElement.textContent =
                    "₹0";

                return;
            }


            const total =
                difference *
                Number(dailyRate) *
                quantity;


            totalDaysElement.textContent =
                `${difference}${
                    difference === 1
                        ? " day"
                        : " days"
                }`;


            totalPriceElement.textContent =
                "₹" +
                Math.round(total)
                    .toLocaleString("en-IN");

        }


        function renderQuantityUI() {

            const inCart =
                quantity > 0;


            continueBtn.hidden =
                inCart;


            cartStepper.hidden =
                !inCart;


            cartQuantityValue.textContent =
                quantity;


            continueBtn.disabled =
                busy ||
                !startInput.value ||
                !endInput.value ||
                maxQuantity < 1;


            cartMinus.disabled =
                busy;


            cartPlus.disabled =
                busy ||
                !startInput.value ||
                !endInput.value ||
                maxQuantity < 1 ||
                quantity >= maxQuantity ||
                quantity >= 100;


            calculateTotal();

        }


        function setDatesLocked(
            locked
        ) {

            if (
                !startPicker ||
                !endPicker
            ) {
                return;
            }


            startPicker.set(
                "clickOpens",
                !locked
            );


            endPicker.set(
                "clickOpens",
                !locked
            );


            startInput.classList.toggle(
                "date-locked",
                locked
            );


            endInput.classList.toggle(
                "date-locked",
                locked
            );

        }


        async function checkAvailability() {

            if (
                !startInput.value ||
                !endInput.value
            ) {

                maxQuantity = 0;


                quantityAvailableElement.textContent =
                    "Select dates to see rental availability";


                renderQuantityUI();

                return;
            }


            const start =
                new Date(
                    `${startInput.value}T00:00:00`
                );


            const end =
                new Date(
                    `${endInput.value}T00:00:00`
                );


            const days =
                (
                    end - start
                )
                /
                (
                    1000 *
                    60 *
                    60 *
                    24
                );


            if (days <= 0) {

                maxQuantity = 0;

                quantityAvailableElement.textContent =
                    "Select valid dates";

                renderQuantityUI();

                return;
            }


            if (days > 30) {

                maxQuantity = 0;

                quantityAvailableElement.textContent =
                    "Maximum rental period is 30 days";

                renderQuantityUI();

                return;
            }


            try {

                const response =
                    await fetch(
                        `/check-availability/${equipmentId}` +
                        `?start_date=${
                            encodeURIComponent(
                                startInput.value
                            )
                        }` +
                        `&end_date=${
                            encodeURIComponent(
                                endInput.value
                            )
                        }`
                    );


                const data =
                    await response.json();


                if (!data.success) {

                    maxQuantity = 0;

                    quantityAvailableElement.textContent =
                        data.message ||
                        "Availability unavailable";

                    renderQuantityUI();

                    return;
                }


                maxQuantity =
                    Math.min(
                        Number(
                            data.max_quantity ??
                            data.available_quantity ??
                            0
                        ),
                        100
                    );


                if (maxQuantity <= 0) {

                    quantityAvailableElement.textContent =
                        "No units available for your selected dates";

                }

                else {

                    quantityAvailableElement.textContent =
                        `Up to ${maxQuantity} unit${
                            maxQuantity === 1
                                ? ""
                                : "s"
                        } available for your selected dates`;

                }


                renderQuantityUI();

            }

            catch (error) {

                console.error(
                    "Equipment availability check failed:",
                    error
                );


                maxQuantity = 0;


                quantityAvailableElement.textContent =
                    "Unable to check rental availability";


                renderQuantityUI();

            }

        }


        async function changeQuantity(
            action
        ) {

            if (busy) {
                return;
            }


            clearError();


            if (
                action !== "decrease"
            ) {

                if (!startInput.value) {

                    showError(
                        "Please select a start date."
                    );

                    return;
                }


                if (!endInput.value) {

                    showError(
                        "Please select an end date."
                    );

                    return;
                }

            }


            busy = true;

            renderQuantityUI();


            try {

                const csrfToken =
                    document
                        .querySelector(
                            'meta[name="csrf-token"]'
                        )
                        ?.getAttribute(
                            "content"
                        );


                const response =
                    await fetch(
                        "/cart/change-quantity",
                        {
                            method: "POST",

                            headers: {
                                "Content-Type":
                                    "application/json",

                                "X-CSRFToken":
                                    csrfToken || ""
                            },

                            body:
                                JSON.stringify({
                                    item_type:
                                        "Equipment",

                                    item_id:
                                        equipmentId,

                                    action:
                                        action,

                                    start_date:
                                        startInput.value,

                                    end_date:
                                        endInput.value
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
                        data.max_quantity !==
                        undefined
                    ) {

                        maxQuantity =
                            Math.min(
                                Number(
                                    data.max_quantity
                                ),
                                100
                            );

                    }


                    showError(
                        data.message ||
                        "Unable to update the quantity."
                    );


                    return;
                }


                quantity =
                    Number(
                        data.quantity || 0
                    );


                updateCartBadge(
                    Number(
                        data.cart_count || 0
                    )
                );


                if (
                    data.max_quantity !==
                    undefined
                ) {

                    maxQuantity =
                        Math.min(
                            Number(
                                data.max_quantity
                            ),
                            100
                        );

                }


                cartCurrentlyHasItems =
                    !Boolean(
                        data.cart_empty
                    );


                if (
                    quantity === 0
                ) {

                    if (
                        data.cart_empty
                    ) {

                        cartCurrentlyHasItems =
                            false;


                        setDatesLocked(
                            false
                        );


                        quantityAvailableElement.textContent =
                            "Select dates to see rental availability";


                        maxQuantity = 0;


                        await checkAvailability();

                    }

                }

                else {

                    setDatesLocked(
                        true
                    );


                    quantityAvailableElement.textContent =
                        `Quantity ${quantity} · Up to ${maxQuantity} available for these dates`;

                }

            }

            catch (error) {

                console.error(
                    "Quantity update failed:",
                    error
                );


                showError(
                    "Unable to update the cart. Please try again."
                );

            }

            finally {

                busy = false;

                renderQuantityUI();

            }

        }


        const today =
            new Date();

        today.setHours(
            0,
            0,
            0,
            0
        );


        startPicker =
            flatpickr(
                startInput,
                {
                    minDate:
                        today,

                    dateFormat:
                        "Y-m-d",

                    clickOpens:
                        !cartCurrentlyHasItems,


                    onChange:
                        function (
                            selectedDates
                        ) {

                            if (
                                cartCurrentlyHasItems
                            ) {
                                return;
                            }


                            clearError();


                            if (
                                !selectedDates.length
                            ) {

                                endInput.value =
                                    "";

                                maxQuantity =
                                    0;


                                quantityAvailableElement.textContent =
                                    "Select dates to see rental availability";


                                quantity = 0;


                                renderQuantityUI();

                                return;
                            }


                            const selectedStart =
                                selectedDates[0];


                            const maxEnd =
                                new Date(
                                    selectedStart
                                );


                            maxEnd.setDate(
                                maxEnd.getDate()
                                + 30
                            );


                            endPicker.set(
                                "minDate",
                                selectedStart
                            );


                            endPicker.set(
                                "maxDate",
                                maxEnd
                            );


                            endPicker.clear();


                            maxQuantity =
                                0;


                            quantityAvailableElement.textContent =
                                "Select return date";


                            renderQuantityUI();

                        }

                }
            );


        endPicker =
            flatpickr(
                endInput,
                {
                    minDate:
                        today,

                    dateFormat:
                        "Y-m-d",

                    clickOpens:
                        !cartCurrentlyHasItems,


                    onChange:
                        function () {

                            if (
                                cartCurrentlyHasItems
                            ) {
                                return;
                            }


                            clearError();

                            checkAvailability();

                        }

                }
            );


        // ---------------------------------------------
        // RESTORE CART DATES
        // ---------------------------------------------

        if (
            cartStartDate
        ) {

            startPicker.setDate(
                cartStartDate,
                false
            );


            const selectedStart =
                new Date(
                    `${cartStartDate}T00:00:00`
                );


            const maxEnd =
                new Date(
                    selectedStart
                );


            maxEnd.setDate(
                maxEnd.getDate()
                + 30
            );


            endPicker.set(
                "minDate",
                selectedStart
            );


            endPicker.set(
                "maxDate",
                maxEnd
            );

        }


        if (
            cartEndDate
        ) {

            endPicker.setDate(
                cartEndDate,
                false
            );

        }


        setDatesLocked(
            cartCurrentlyHasItems
        );


        cartMinus.addEventListener(
            "click",
            function () {

                changeQuantity(
                    "decrease"
                );

            }
        );


        cartPlus.addEventListener(
            "click",
            function () {

                changeQuantity(
                    "increase"
                );

            }
        );


        continueBtn.addEventListener(
            "click",
            function () {

                changeQuantity(
                    "add"
                );

            }
        );


        renderQuantityUI();


        if (
            startInput.value &&
            endInput.value
        ) {

            checkAvailability();

        }

    }
);