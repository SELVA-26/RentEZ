document.addEventListener(
    "DOMContentLoaded",
    function () {

        const button =
            document.getElementById(
                "notificationButton"
            );

        const panel =
            document.getElementById(
                "notificationPanel"
            );

        const markAll =
            document.getElementById(
                "markAllNotificationsRead"
            );


        if (!button || !panel) {
            return;
        }


        button.addEventListener(
            "click",
            function (event) {

                event.stopPropagation();

                panel.classList.toggle(
                    "show"
                );

            }
        );


        panel.addEventListener(
            "click",
            function (event) {

                event.stopPropagation();

            }
        );


        document.addEventListener(
            "click",
            function () {

                panel.classList.remove(
                    "show"
                );

            }
        );


        // =========================================
        // MARK ONE AS READ
        // =========================================

        document
            .querySelectorAll(
                ".notification-item[data-notification-id]"
            )
            .forEach(
                function (item) {

                    item.addEventListener(
                        "click",
                        function () {

                            const notificationId =
                                item.dataset.notificationId;

                            const csrfToken =
                                document
                                    .querySelector(
                                        'meta[name="csrf-token"]'
                                    )
                                    ?.getAttribute(
                                        "content"
                                    );


                            fetch(
                                `/notifications/read/${notificationId}`,
                                {
                                    method: "POST",

                                    headers: {
                                        "X-CSRFToken":
                                            csrfToken
                                    }
                                }
                            ).catch(
                                function (error) {

                                    console.error(
                                        "Notification read error:",
                                        error
                                    );

                                }
                            );

                        }
                    );

                }
            );


        // =========================================
        // MARK ALL AS READ
        // =========================================

        if (markAll) {

            markAll.addEventListener(
                "click",
                async function () {

                    const csrfToken =
                        document
                            .querySelector(
                                'meta[name="csrf-token"]'
                            )
                            ?.getAttribute(
                                "content"
                            );


                    try {

                        const response =
                            await fetch(
                                "/notifications/mark-all-read",
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


                        if (data.success) {

                            window.location.reload();

                        }

                    } catch (error) {

                        console.error(
                            "Mark-all-read failed:",
                            error
                        );

                    }

                }
            );

        }

    }
);