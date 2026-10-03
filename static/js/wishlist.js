document.addEventListener(
    "DOMContentLoaded",
    function () {

        const csrfToken =
            document
                .querySelector(
                    'meta[name="csrf-token"]'
                )
                ?.getAttribute("content");


        document
            .querySelectorAll(".wishlist-btn")
            .forEach(function (button) {

                button.addEventListener(
                    "click",
                    async function (event) {

                        event.preventDefault();

                        event.stopPropagation();


                        const equipmentId =
                            button.dataset.equipmentId;


                        try {

                            const response =
                                await fetch(
                                    `/wishlist/toggle/${equipmentId}`,
                                    {
                                        method: "POST",

                                        headers: {
                                            "X-CSRFToken":
                                                csrfToken
                                        }
                                    }
                                );


                            const data =
                                await response.json();


                            if (!data.success) {

                                rentEZMessage(
                                    data.message ||
                                    "Unable to update wishlist.",
                                    "error",
                                    "Wishlist Update Failed"
                                );

                                return;
                            }


                            const icon =
                                button.querySelector("i");


                            if (data.wishlisted) {

                                button.classList.add(
                                    "active"
                                );

                                icon.className =
                                    "ri-heart-3-fill";

                            } else {

                                button.classList.remove(
                                    "active"
                                );

                                icon.className =
                                    "ri-heart-3-line";

                                const wishlistCard =
                                    button.closest(
                                        ".wishlist-card"
                                    );

                                if (wishlistCard) {

                                    wishlistCard.remove();

                                    const remainingCards =
                                        document.querySelectorAll(
                                            ".wishlist-card"
                                        );

                                    if (remainingCards.length === 0) {
                                        window.location.reload();
                                    }
                                }
                            }

                        } catch (error) {

                            console.error(
                                "Wishlist error:",
                                error
                            );

                            rentEZMessage(
                                "Unable to update your wishlist right now.",
                                "error",
                                "Wishlist Update Failed"
                            );
                        }

                    }
                );

            });

    }
);

document.addEventListener(
    "DOMContentLoaded",
    function () {

        const button =
            document.getElementById(
                "wishlistDetailButton"
            );

        if (!button) {
            return;
        }

        const csrfToken =
            document
                .querySelector(
                    'meta[name="csrf-token"]'
                )
                ?.getAttribute("content");


        button.addEventListener(
            "click",
            async function () {

                const equipmentId =
                    button.dataset.equipmentId;


                try {

                    const response =
                        await fetch(
                            `/wishlist/toggle/${equipmentId}`,
                            {
                                method: "POST",

                                headers: {
                                    "X-CSRFToken":
                                        csrfToken
                                }
                            }
                        );


                    const data =
                        await response.json();


                    if (!data.success) {

                        rentEZMessage(
                            data.message ||
                            "Unable to update wishlist.",
                            "error",
                            "Wishlist Update Failed"
                        );

                        return;
                    }


                    const icon =
                        button.querySelector("i");


                    if (data.wishlisted) {

                        button.classList.add("active");

                        icon.className =
                            "ri-heart-3-fill";

                    } else {

                        button.classList.remove("active");

                        icon.className =
                            "ri-heart-3-line";
                    }

                } catch (error) {

                    console.error(
                        "Wishlist error:",
                        error
                    );

                    rentEZMessage(
                        "Unable to update your wishlist right now.",
                        "error",
                        "Wishlist Update Failed"
                    );
                }

            }
        );

    }
);

