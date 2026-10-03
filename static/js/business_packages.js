document.addEventListener("DOMContentLoaded", function () {

    const csrfToken =
        document
            .querySelector('meta[name="csrf-token"]')
            ?.getAttribute("content");


    document
        .querySelectorAll(".toggle-btn")
        .forEach(function (button) {

            button.addEventListener(
                "click",
                async function () {

                    const packageId =
                        button.dataset.packageId;


                    try {

                        const response =
                            await fetch(
                                `/business/packages/${packageId}/toggle`,
                                {
                                    method: "POST",
                                    headers: {
                                        "X-CSRFToken": csrfToken
                                    }
                                }
                            );


                        const data =
                            await response.json();


                        if (!data.success) {

                            rentEZMessage(
                                data.message ||
                                "Unable to update package.",
                                "error",
                                "Package Update Failed"
                            );

                            return;
                        }


                        window.location.reload();

                    } catch (error) {

                        console.error(error);

                        rentEZMessage(
                            "Unable to update package right now.",
                            "error",
                            "Package Update Failed"
                        );
                    }

                }
            );

        });

});