const passwordInput = document.getElementById("password");
const togglePassword = document.getElementById("togglePassword");

if (togglePassword && passwordInput) {

    togglePassword.addEventListener("click", function () {

        if (passwordInput.type === "password") {

            passwordInput.type = "text";

            togglePassword.classList.remove(
                "ri-eye-off-line"
            );

            togglePassword.classList.add(
                "ri-eye-line"
            );

        } else {

            passwordInput.type = "password";

            togglePassword.classList.remove(
                "ri-eye-line"
            );

            togglePassword.classList.add(
                "ri-eye-off-line"
            );

        }

    });

}