(function () {

    function createModal() {

        let existing = document.getElementById("rentEZMessageOverlay");

        if (existing) {
            return existing;
        }

        const overlay = document.createElement("div");

        overlay.id = "rentEZMessageOverlay";
        overlay.className = "rentez-message-overlay";

        overlay.innerHTML = `
            <div class="rentez-message-modal">

                <button
                    type="button"
                    class="rentez-message-close"
                    aria-label="Close">
                    <i class="ri-close-line"></i>
                </button>

                <div
                    class="rentez-message-icon"
                    id="rentEZMessageIcon">
                </div>

                <h2 id="rentEZMessageTitle">
                    Something went wrong
                </h2>

                <p id="rentEZMessageText"></p>

                <button
                    type="button"
                    class="rentez-message-button"
                    id="rentEZMessageButton">
                    Okay
                </button>

            </div>
        `;

        document.body.appendChild(overlay);

        const close = function () {

            overlay.classList.remove("show");

        };

        overlay
            .querySelector(".rentez-message-close")
            .addEventListener("click", close);

        overlay
            .querySelector("#rentEZMessageButton")
            .addEventListener("click", close);

        overlay.addEventListener("click", function (event) {

            if (event.target === overlay) {
                close();
            }

        });

        document.addEventListener("keydown", function (event) {

            if (
                event.key === "Escape" &&
                overlay.classList.contains("show")
            ) {
                close();
            }

        });

        return overlay;
    }


    window.rentEZMessage = function (
        message,
        type = "error",
        title = null
    ) {

        const overlay = createModal();

        const icon =
            document.getElementById("rentEZMessageIcon");

        const heading =
            document.getElementById("rentEZMessageTitle");

        const text =
            document.getElementById("rentEZMessageText");

        const button =
            document.getElementById("rentEZMessageButton");


        overlay.classList.remove(
            "error",
            "success",
            "warning"
        );

        overlay.classList.add(type);


        if (type === "success") {

            icon.innerHTML =
                '<i class="ri-check-line"></i>';

            heading.textContent =
                title || "Success";

        } else if (type === "warning") {

            icon.innerHTML =
                '<i class="ri-error-warning-line"></i>';

            heading.textContent =
                title || "Please check";

        } else {

            icon.innerHTML =
                '<i class="ri-close-line"></i>';

            heading.textContent =
                title || "Something went wrong";
        }


        text.textContent = message;

        button.textContent = "Okay";

        overlay.classList.add("show");
    };


    window.closeRentEZMessage = function () {

        const overlay =
            document.getElementById(
                "rentEZMessageOverlay"
            );

        if (overlay) {
            overlay.classList.remove("show");
        }

    };


    function injectStyles() {

        if (
            document.getElementById(
                "rentEZMessageStyles"
            )
        ) {
            return;
        }

        const style =
            document.createElement("style");

        style.id = "rentEZMessageStyles";

        style.textContent = `

            .rentez-message-overlay {

                position: fixed;
                inset: 0;
                z-index: 99999;

                display: flex;
                align-items: center;
                justify-content: center;

                padding: 20px;

                background: rgba(15, 23, 42, .45);

                opacity: 0;
                visibility: hidden;

                transition:
                    opacity .2s ease,
                    visibility .2s ease;

            }


            .rentez-message-overlay.show {

                opacity: 1;
                visibility: visible;

            }


            .rentez-message-modal {

                position: relative;

                width: min(
                    420px,
                    100%
                );

                padding: 30px 26px 24px;

                text-align: center;

                background: #ffffff;

                border: 1px solid #e2e8f0;

                border-radius: 18px;

                box-shadow:
                    0 24px 70px
                    rgba(15, 23, 42, .20);

                transform:
                    translateY(10px)
                    scale(.98);

                transition:
                    transform .2s ease;

            }


            .rentez-message-overlay.show
            .rentez-message-modal {

                transform:
                    translateY(0)
                    scale(1);

            }


            .rentez-message-close {

                position: absolute;

                top: 12px;
                right: 12px;

                width: 32px;
                height: 32px;

                display: flex;
                align-items: center;
                justify-content: center;

                border: 0;
                border-radius: 50%;

                background: #f8fafc;

                color: #64748b;

                font-size: 17px;

                cursor: pointer;

            }


            .rentez-message-close:hover {

                background: #f1f5f9;
                color: #0f172a;

            }


            .rentez-message-icon {

                width: 54px;
                height: 54px;

                margin: 0 auto 15px;

                display: flex;
                align-items: center;
                justify-content: center;

                border-radius: 50%;

                font-size: 25px;

            }


            .rentez-message-overlay.error
            .rentez-message-icon {

                background: #fef2f2;
                color: #dc2626;

            }


            .rentez-message-overlay.warning
            .rentez-message-icon {

                background: #fffbeb;
                color: #d97706;

            }


            .rentez-message-overlay.success
            .rentez-message-icon {

                background: #ecfdf5;
                color: #059669;

            }


            .rentez-message-modal h2 {

                margin: 0 0 8px;

                color: #0f172a;

                font-size: 18px;
                font-weight: 700;

            }


            .rentez-message-modal p {

                margin: 0 auto 22px;

                max-width: 340px;

                color: #64748b;

                font-size: 11px;
                line-height: 1.65;

            }


            .rentez-message-button {

                min-width: 110px;

                padding: 10px 18px;

                border: 0;
                border-radius: 9px;

                background: #0f172a;
                color: #ffffff;

                font-family: inherit;
                font-size: 11px;
                font-weight: 600;

                cursor: pointer;

            }


            .rentez-message-button:hover {

                opacity: .9;

            }

        `;

        document.head.appendChild(style);
    }


    if (
        document.readyState === "loading"
    ) {

        document.addEventListener(
            "DOMContentLoaded",
            injectStyles
        );

    } else {

        injectStyles();

    }

})();