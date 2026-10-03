/* =====================================================
   DESCRIPTION CHARACTER COUNTER
===================================================== */

const description =
    document.getElementById("description");

const charCount =
    document.getElementById("char-count");

if (description && charCount) {

    description.addEventListener("input", function () {

        charCount.textContent =
            `${this.value.length} / 500`;

    });

}


/* =====================================================
   IMAGE PREVIEW + VALIDATION
===================================================== */

const imageInput =
    document.getElementById("image");

const imagePreview =
    document.getElementById("image-preview");

const allowedExtensions = [
    "jpg",
    "jpeg",
    "png",
    "webp"
];

const maxImageSize =
    5 * 1024 * 1024;


function showUploadError(message) {

    let errorBox =
        document.getElementById("upload-error");

    if (!errorBox) {

        errorBox =
            document.createElement("div");

        errorBox.id =
            "upload-error";

        errorBox.className =
            "upload-error";

        imagePreview.parentNode.insertBefore(
            errorBox,
            imagePreview
        );
    }

    errorBox.innerHTML = `
        <i>!</i>
        <span>${message}</span>
    `;
}


function clearUploadError() {

    const errorBox =
        document.getElementById("upload-error");

    if (errorBox) {
        errorBox.remove();
    }
}


if (imageInput && imagePreview) {

    imageInput.addEventListener("change", function () {

        imagePreview.innerHTML = "";

        clearUploadError();

        const file =
            this.files[0];

        if (!file) {
            return;
        }

        const extension =
            file.name
                .split(".")
                .pop()
                .toLowerCase();


        if (!allowedExtensions.includes(extension)) {

            showUploadError(
                "Please upload a JPG, JPEG, PNG or WEBP image."
            );

            this.value = "";

            return;
        }


        if (file.size > maxImageSize) {

            showUploadError(
                "Image size must be 5 MB or less."
            );

            this.value = "";

            return;
        }


        const reader =
            new FileReader();


        reader.onload = function (event) {

            imagePreview.innerHTML = `
                <div class="preview-wrapper">

                    <img
                        src="${event.target.result}"
                        alt="Equipment preview"
                    >

                    <span class="preview-name">
                        ${file.name}
                    </span>

                </div>
            `;
        };


        reader.readAsDataURL(file);

    });

}