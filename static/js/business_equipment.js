document.addEventListener(
    "DOMContentLoaded",
    function () {

        const grid =
            document.getElementById(
                "manageEquipmentGrid"
            );

        const searchInput =
            document.getElementById(
                "equipmentSearch"
            );

        const categoryFilter =
            document.getElementById(
                "categoryFilter"
            );

        const sortFilter =
            document.getElementById(
                "sortFilter"
            );

        const resultText =
            document.getElementById(
                "equipmentResults"
            );

        const countElement =
            document.getElementById(
                "equipmentCount"
            );

        const noResults =
            document.getElementById(
                "equipmentNoResults"
            );


        if (
            !grid ||
            !searchInput ||
            !categoryFilter ||
            !sortFilter
        ) {
            return;
        }


        const cards = Array.from(
            grid.querySelectorAll(
                ".manage-equipment-card"
            )
        );


        function updateResults() {

            const search =
                searchInput.value
                    .trim()
                    .toLowerCase();

            const category =
                categoryFilter.value
                    .trim()
                    .toLowerCase();


            let visibleCards =
                cards.filter(
                    function (card) {

                        const name =
                            card.dataset.name || "";

                        const cardCategory =
                            card.dataset.category || "";


                        const matchesSearch =
                            !search ||
                            name.includes(search);


                        const matchesCategory =
                            category === "all" ||
                            cardCategory === category;


                        return (
                            matchesSearch &&
                            matchesCategory
                        );

                    }
                );


            // =================================================
            // SORT
            // =================================================

            const sort =
                sortFilter.value;


            visibleCards.sort(
                function (a, b) {

                    if (sort === "price-low") {

                        return (
                            parseFloat(
                                a.dataset.price
                            ) -
                            parseFloat(
                                b.dataset.price
                            )
                        );

                    }


                    if (sort === "price-high") {

                        return (
                            parseFloat(
                                b.dataset.price
                            ) -
                            parseFloat(
                                a.dataset.price
                            )
                        );

                    }


                    if (sort === "name") {

                        return (
                            a.dataset.name
                                .localeCompare(
                                    b.dataset.name
                                )
                        );

                    }


                    // Latest
                    return (
                        parseInt(
                            a.dataset.order
                        ) -
                        parseInt(
                            b.dataset.order
                        )
                    );

                }
            );


            // =================================================
            // REBUILD GRID
            // =================================================

            cards.forEach(
                function (card) {

                    card.style.display = "none";

                }
            );


            visibleCards.forEach(
                function (card) {

                    card.style.display = "";

                    grid.appendChild(card);

                }
            );


            // =================================================
            // RESULT COUNT
            // =================================================

            if (resultText) {

                resultText.textContent =
                    `Showing ${visibleCards.length} equipment item${
                        visibleCards.length === 1
                            ? ""
                            : "s"
                    }`;

            }


           if (countElement) {

                countElement.textContent =
                    visibleCards.length;

            }

            // =================================================
            // NO RESULTS
            // =================================================

            if (noResults) {

                noResults.style.display =
                    visibleCards.length === 0
                        ? "block"
                        : "none";

            }

        }


        searchInput.addEventListener(
            "input",
            updateResults
        );


        categoryFilter.addEventListener(
            "change",
            updateResults
        );


        sortFilter.addEventListener(
            "change",
            updateResults
        );


        updateResults();

    }
);