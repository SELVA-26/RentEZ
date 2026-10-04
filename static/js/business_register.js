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

// ================================
// REGISTRATION NUMBER FORMAT
// ================================

const registrationNumber =
    document.getElementById("registration_number");

const documentType =
    document.getElementById("document_type");

const registrationHelp =
    document.getElementById("registrationHelp");


function updateRegistrationFormat() {

    const type = documentType.value;

    registrationNumber.value =
        registrationNumber.value.toUpperCase();

    // GSTIN
    if (type === "GST Certificate") {

        registrationNumber.placeholder =
            "Enter 15-character GSTIN";

        registrationNumber.maxLength = 15;

        registrationNumber.pattern =
            "[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]";

        registrationHelp.textContent =
            "Format: 15-character GSTIN, for example 27ABCDE1234F1Z5.";

    }

    // UDYAM
    else if (type === "Udyam Registration") {

        registrationNumber.placeholder =
            "UDYAM-MH-00-0000000";

        registrationNumber.maxLength = 19;

        registrationNumber.pattern =
            "UDYAM-[A-Z]{2}-[0-9]{2}-[0-9]{7}";

        registrationHelp.textContent =
            "Format: UDYAM-XX-00-0000000.";

    }

    // Other registration documents
    else {

        registrationNumber.placeholder =
            "Enter registration number";

        registrationNumber.maxLength = 100;

        registrationNumber.removeAttribute("pattern");

        registrationHelp.textContent =
            "Enter the registration number exactly as shown on the submitted document.";

    }

}


// Update when document type changes
documentType.addEventListener(
    "change",
    updateRegistrationFormat
);


// Convert input to uppercase
registrationNumber.addEventListener(
    "input",
    function () {

        this.value =
            this.value.toUpperCase();

    }
);


// Set initial state
updateRegistrationFormat();

form.addEventListener("submit", function (event) {
        // Registration number validation

    const type = documentType.value;

    const value =
        registrationNumber.value
            .trim()
            .toUpperCase();

    registrationNumber.value = value;


    let registrationPattern = null;

    if (type === "GST Certificate") {

        registrationPattern =
            /^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]$/;

    }
    else if (type === "Udyam Registration") {

        registrationPattern =
            /^UDYAM-[A-Z]{2}-[0-9]{2}-[0-9]{7}$/;

    }


    if (
        registrationPattern &&
        !registrationPattern.test(value)
    ) {

        event.preventDefault();

        rentEZMessage(
            type === "GST Certificate"
                ? "Enter a valid 15-character GSTIN in the required format."
                : "Enter a valid Udyam Registration Number in the format UDYAM-XX-00-0000000.",
            "error",
            "Invalid Registration Number"
        );

        registrationNumber.focus();

        return;
    }
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