const password =
    document.getElementById("password");

const confirmPassword =
    document.getElementById("confirmPassword");

const togglePassword =
    document.getElementById("togglePassword");

const toggleConfirmPassword =
    document.getElementById("toggleConfirmPassword");

const fullname =
    document.getElementById("fullname");

const phone =
    document.getElementById("phone");

const registerForm =
    document.querySelector("form");


// =====================================================
// PASSWORD VISIBILITY
// =====================================================

togglePassword.addEventListener(
    "click",
    () => {

        if (password.type === "password") {

            password.type = "text";

            togglePassword.classList.remove(
                "ri-eye-off-line"
            );

            togglePassword.classList.add(
                "ri-eye-line"
            );

        } else {

            password.type = "password";

            togglePassword.classList.remove(
                "ri-eye-line"
            );

            togglePassword.classList.add(
                "ri-eye-off-line"
            );
        }

    }
);


// =====================================================
// CONFIRM PASSWORD VISIBILITY
// =====================================================

toggleConfirmPassword.addEventListener(
    "click",
    () => {

        if (
            confirmPassword.type === "password"
        ) {

            confirmPassword.type = "text";

            toggleConfirmPassword.classList.remove(
                "ri-eye-off-line"
            );

            toggleConfirmPassword.classList.add(
                "ri-eye-line"
            );

        } else {

            confirmPassword.type = "password";

            toggleConfirmPassword.classList.remove(
                "ri-eye-line"
            );

            toggleConfirmPassword.classList.add(
                "ri-eye-off-line"
            );
        }

    }
);


// =====================================================
// FULL NAME INPUT
// Remove numbers while typing/pasting
// =====================================================

fullname.addEventListener(
    "input",
    () => {

        fullname.value =
            fullname.value.replace(
                /[0-9]/g,
                ""
            );

    }
);


// =====================================================
// PHONE INPUT
// Allow digits only
// Maximum 10 digits
// =====================================================

phone.addEventListener(
    "input",
    () => {

        phone.value =
            phone.value
                .replace(/\D/g, "")
                .slice(0, 10);

    }
);


// =====================================================
// FORM VALIDATION
// =====================================================

registerForm.addEventListener(
    "submit",
    function (e) {

        const nameValue =
            fullname.value.trim();

        const phoneValue =
            phone.value.trim();


        // ---------------------------------------------
        // NAME
        // ---------------------------------------------

        if (
            !/^[A-Za-z][A-Za-z .'-]*[A-Za-z]$/
                .test(nameValue)
        ) {

            e.preventDefault();

            rentEZMessage(
                "Please enter a valid full name. Numbers are not allowed.",
                "error",
                "Invalid Name"
            );

            return;
        }


        // ---------------------------------------------
        // PHONE
        // ---------------------------------------------

        if (
            !/^[6-9][0-9]{9}$/
                .test(phoneValue)
        ) {

            e.preventDefault();

            rentEZMessage(
                "Enter a valid 10-digit Indian mobile number starting with 6, 7, 8 or 9.",
                "error",
                "Invalid Phone Number"
            );

            return;
        }


        // ---------------------------------------------
        // OBVIOUS FAKE NUMBER
        // ---------------------------------------------

        if (
            new Set(phoneValue).size === 1
        ) {

            e.preventDefault();

            rentEZMessage(
                "Please enter a valid mobile number.",
                "error",
                "Invalid Phone Number"
            );

            return;
        }


        // ---------------------------------------------
        // PASSWORD MATCH
        // ---------------------------------------------

        if (
            password.value !==
            confirmPassword.value
        ) {

            e.preventDefault();

            rentEZMessage(
                "The passwords you entered do not match.",
                "error",
                "Passwords Don't Match"
            );

            return;
        }

    }
);