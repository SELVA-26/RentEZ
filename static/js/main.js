document.querySelectorAll(".carousel").forEach((carousel) => {

    const track =
        carousel.querySelector(".carousel-track");

    const cards =
        carousel.querySelectorAll(".carousel-card");

    const next =
        carousel.querySelector(".right");

    const prev =
        carousel.querySelector(".left");

    if (!track || !cards.length) {

        if (next) {
            next.style.display = "none";
        }

        if (prev) {
            prev.style.display = "none";
        }

        return;
    }

    let index = 0;

    function getVisibleCards() {

        if (window.innerWidth < 700) {
            return 1;
        }

        if (window.innerWidth < 1100) {
            return 2;
        }

        return 4;
    }

    function updateCarousel() {

        const gap =
            parseInt(
                getComputedStyle(track).gap
            ) || 0;

        const cardWidth =
            cards[0].offsetWidth + gap;

        track.style.transition =
            "transform .5s ease";

        track.style.transform =
            `translateX(-${index * cardWidth}px)`;
    }

    function updateButtons() {

        const visibleCards =
            getVisibleCards();

        const maxIndex =
            Math.max(
                0,
                cards.length - visibleCards
            );
        if (index > maxIndex) {

            index = maxIndex;

            updateCarousel();

        }
        if (prev) {

            prev.style.display =
                index === 0 ? "none" : "";

        }
        if (next) {

            next.style.display =
                index >= maxIndex ? "none" : "";

        }
    }
    if (next) {

        next.addEventListener(
            "click",
            () => {

                const visibleCards =
                    getVisibleCards();

                const maxIndex =
                    Math.max(
                        0,
                        cards.length - visibleCards
                    );

                if (index < maxIndex) {

                    index++;

                    updateCarousel();

                    updateButtons();

                }

            }
        );

    }
    if (prev) {

        prev.addEventListener(
            "click",
            () => {

                if (index > 0) {

                    index--;

                    updateCarousel();

                    updateButtons();

                }

            }
        );

    }
    window.addEventListener(
        "resize",
        () => {

            updateButtons();

            updateCarousel();

        }
    );
    updateButtons();

});
