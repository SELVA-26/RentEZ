document.addEventListener("DOMContentLoaded", function () {

    const checks =
        document.querySelectorAll(
            ".equipment-check"
        );

    const total =
        document.getElementById(
            "componentTotal"
        );

    const packagePrice =
        document.getElementById(
            "price_per_day"
        );

    const pricePreview =
        document.getElementById(
            "packagePricePreview"
        );

    const savings =
        document.getElementById(
            "packageSavings"
        );


    function updateSummary() {

        let componentTotal = 0;


        checks.forEach(function (checkbox) {

            if (!checkbox.checked) {
                return;
            }

            const equipmentRow =
                checkbox.closest(
                    ".equipment-row"
                );

            const rateElement =
                equipmentRow.querySelector(
                    ".equipment-rate"
                );

            const quantityInput =
                equipmentRow.querySelector(
                    ".equipment-quantity"
                );

            if (!rateElement || !quantityInput) {
                return;
            }

            const rate =
                parseFloat(
                    rateElement.textContent
                        .replace(/[^\d.]/g, "")
                ) || 0;

            const quantity =
                parseInt(
                    quantityInput.value,
                    10
                ) || 0;

            componentTotal +=
                rate * quantity;

        });


        total.textContent =
            `₹${componentTotal.toFixed(0)}/day`;


        const enteredPrice =
            parseFloat(
                packagePrice.value
            ) || 0;


        pricePreview.textContent =
            `₹${enteredPrice.toFixed(0)}/day`;


        if (
            componentTotal > 0
            && enteredPrice > 0
            && enteredPrice < componentTotal
        ) {

            const saving =
                componentTotal - enteredPrice;

            savings.textContent =
                `Customer saves ₹${saving.toFixed(0)}/day`;

        }
        else if (
            componentTotal > 0
            && enteredPrice === componentTotal
        ) {

            savings.textContent =
                "Package price matches the component value.";

        }
        else if (
            componentTotal > 0
            && enteredPrice > componentTotal
        ) {

            savings.textContent =
                "Package price is higher than the combined equipment value.";

        }
        else {

            savings.textContent =
                "Select equipment and enter a package price.";

        }
    }


    checks.forEach(function (checkbox) {

        checkbox.addEventListener(
            "change",
            function () {

                const row =
                    checkbox.closest(
                        ".equipment-row"
                    );

                const quantity =
                    row.querySelector(
                        ".equipment-quantity"
                    );

                quantity.disabled =
                    !checkbox.checked;


                if (
                    checkbox.checked
                    && !quantity.value
                ) {
                    quantity.value = 1;
                }


                updateSummary();

            }
        );

    });


    document
        .querySelectorAll(
            ".equipment-quantity"
        )
        .forEach(function (input) {

            input.addEventListener(
                "input",
                updateSummary
            );

        });


    packagePrice.addEventListener(
        "input",
        updateSummary
    );


    updateSummary();

});