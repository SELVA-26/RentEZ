const searchInput =
    document.getElementById("searchInput");

const categoryFilter =
    document.getElementById("categoryFilter");

const sortFilter =
    document.getElementById("sortFilter");

const equipmentGrid =
    document.getElementById("equipmentGrid");

const wrappers =
    Array.from(
        document.querySelectorAll(".equipment-card-wrap")
    );

const noResults =
    document.getElementById("noResults");

const noResultsTitle =
    document.getElementById("noResultsTitle");

const noResultsMessage =
    document.getElementById("noResultsMessage");

const resultsCount =
    document.getElementById("resultsCount");


/* =====================================================
   CATEGORY FROM URL
===================================================== */

const urlParams =
    new URLSearchParams(
        window.location.search
    );

const categoryFromURL =
    urlParams.get("category");


if (categoryFromURL) {

    const matchingOption =
        Array.from(
            categoryFilter.options
        ).find(
            option =>
                option.value === categoryFromURL
        );

    if (matchingOption) {

        categoryFilter.value =
            categoryFromURL;
    }
}


/* =====================================================
   FILTER EQUIPMENT
===================================================== */

function filterEquipment() {

    const searchText =
        searchInput.value
            .toLowerCase()
            .trim();

    const selectedCategory =
        categoryFilter.value;

    const sortValue =
        sortFilter.value;


    /* =================================================
       FILTER WRAPPERS
    ================================================= */

    let visibleWrappers =
        wrappers.filter(wrapper => {

            const card =
                wrapper.querySelector(
                    ".equipment-card"
                );

            if (!card) {
                return false;
            }


            const name =
                card.dataset.name || "";

            const category =
                card.dataset.category || "";


            const matchesSearch =
                name.includes(searchText);

            const matchesCategory =
                selectedCategory === "all" ||
                category === selectedCategory;


            return (
                matchesSearch &&
                matchesCategory
            );
        });


    /* =================================================
       SORT
    ================================================= */

    if (sortValue === "price-asc") {

        visibleWrappers.sort(
            (a, b) => {

                const cardA =
                    a.querySelector(
                        ".equipment-card"
                    );

                const cardB =
                    b.querySelector(
                        ".equipment-card"
                    );

                return (
                    Number(cardA.dataset.price) -
                    Number(cardB.dataset.price)
                );
            }
        );

    }


    else if (sortValue === "price-desc") {

        visibleWrappers.sort(
            (a, b) => {

                const cardA =
                    a.querySelector(
                        ".equipment-card"
                    );

                const cardB =
                    b.querySelector(
                        ".equipment-card"
                    );

                return (
                    Number(cardB.dataset.price) -
                    Number(cardA.dataset.price)
                );
            }
        );

    }


    else if (sortValue === "name-asc") {

        visibleWrappers.sort(
            (a, b) => {

                const cardA =
                    a.querySelector(
                        ".equipment-card"
                    );

                const cardB =
                    b.querySelector(
                        ".equipment-card"
                    );

                return (
                    (cardA.dataset.name || "")
                        .localeCompare(
                            cardB.dataset.name || ""
                        )
                );
            }
        );
    }


    /* =================================================
       DISPLAY WRAPPERS
    ================================================= */

    wrappers.forEach(wrapper => {

        wrapper.style.display = "none";

    });


    visibleWrappers.forEach(wrapper => {

        wrapper.style.display = "";

        equipmentGrid.appendChild(
            wrapper
        );

    });


    /* =================================================
       EMPTY STATE
    ================================================= */

    if (visibleWrappers.length === 0) {

        noResults.style.display =
            "block";


        if (wrappers.length === 0) {

            noResultsTitle.textContent =
                "No equipment currently available";

            noResultsMessage.textContent =
                "Verified businesses haven't listed any equipment yet.";

            resultsCount.textContent =
                "";

        }

        else if (selectedCategory !== "all") {

            noResultsTitle.textContent =
                `No ${selectedCategory.toLowerCase()} currently available`;

            noResultsMessage.textContent =
                "Try another category or check back later.";

            resultsCount.textContent =
                "";

        }

        else {

            noResultsTitle.textContent =
                "No equipment found";

            noResultsMessage.textContent =
                "Try changing your search or sort options.";

            resultsCount.textContent =
                "";

        }

    }

    else {

        noResults.style.display =
            "none";

        resultsCount.textContent =
            `Showing ${visibleWrappers.length} of ${wrappers.length} items`;
    }

}


/* =====================================================
   EVENTS
===================================================== */

searchInput.addEventListener(
    "input",
    filterEquipment
);

categoryFilter.addEventListener(
    "change",
    filterEquipment
);

sortFilter.addEventListener(
    "change",
    filterEquipment
);


/* =====================================================
   INITIAL LOAD
===================================================== */

filterEquipment();