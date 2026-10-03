// ================================
// PASSWORD TOGGLE
// ================================

const password = document.getElementById("password");
const confirmPassword = document.getElementById("confirmPassword");

const togglePassword = document.getElementById("togglePassword");
const toggleConfirmPassword =
    document.getElementById("toggleConfirmPassword");


// Password

togglePassword.addEventListener("click", () => {

    if (password.type === "password") {

        password.type = "text";

        togglePassword.classList.remove("ri-eye-off-line");
        togglePassword.classList.add("ri-eye-line");

    } else {

        password.type = "password";

        togglePassword.classList.remove("ri-eye-line");
        togglePassword.classList.add("ri-eye-off-line");

    }

});


// Confirm Password

toggleConfirmPassword.addEventListener("click", () => {

    if (confirmPassword.type === "password") {

        confirmPassword.type = "text";

        toggleConfirmPassword.classList.remove("ri-eye-off-line");
        toggleConfirmPassword.classList.add("ri-eye-line");

    } else {

        confirmPassword.type = "password";

        toggleConfirmPassword.classList.remove("ri-eye-line");
        toggleConfirmPassword.classList.add("ri-eye-off-line");

    }

});


// ================================
// FILE NAME
// ================================

const fileInput =
    document.getElementById("verification_document");

const fileName =
    document.getElementById("fileName");


fileInput.addEventListener("change", () => {

    if (fileInput.files.length > 0) {

        fileName.textContent =
            fileInput.files[0].name;

    } else {

        fileName.textContent =
            "Choose a document";

    }

});


// ================================
// FORM VALIDATION
// ================================

const form =
    document.getElementById("businessRegisterForm");

const submitBtn =
    document.getElementById("submitBtn");


form.addEventListener("submit", function (event) {

    // Password match

    if (password.value !== confirmPassword.value) {

        event.preventDefault();

        rentEZMessage(
            "The passwords you entered do not match.",
            "error",
            "Passwords Don't Match"
        );

        confirmPassword.focus();

        return;

    }


    // File validation

    if (fileInput.files.length === 0) {

        event.preventDefault();

        rentEZMessage(
            "Please upload a verification document before submitting your application.",
            "warning",
            "Document Required"
        );

        return;

    }


    const file =
        fileInput.files[0];

    const maxSize =
        10 * 1024 * 1024;


    if (file.size > maxSize) {

        event.preventDefault();

        rentEZMessage(
            "The verification document must be smaller than 10 MB.",
            "warning",
            "File Too Large"
        );

        return;

    }


    // Allowed file types

    const allowedTypes = [
        "application/pdf",
        "image/jpeg",
        "image/png"
    ];


    if (!allowedTypes.includes(file.type)) {

        event.preventDefault();

       rentEZMessage(
            "Please upload a PDF, JPG or PNG document.",
            "warning",
            "Invalid File Type"
        );

        return;

    }


    // Prevent multiple submissions

    submitBtn.disabled = true;

    submitBtn.querySelector("span").textContent =
        "Submitting Application...";

});


// ================================
// ERROR POPUP
// ================================

function closePopup() {

    const popup =
        document.getElementById("errorPopup");

    if (popup) {

        popup.remove();

    }

}


setTimeout(() => {

    closePopup();

}, 5000);

function closeSuccessModal() {

    const modal = document.getElementById("successOverlay");

    if (modal) {
        modal.remove();
    }

}