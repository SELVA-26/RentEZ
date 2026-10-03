const password = document.getElementById("password");
const toggle = document.getElementById("togglePassword");

toggle.addEventListener("click", () => {

    if (password.type === "password") {

        password.type = "text";

        toggle.classList.remove("ri-eye-off-line");
        toggle.classList.add("ri-eye-line");

    } else {

        password.type = "password";

        toggle.classList.remove("ri-eye-line");
        toggle.classList.add("ri-eye-off-line");

    }

});

function closePopup(){
    const popup = document.getElementById("errorPopup");

    if(popup){
        popup.remove();
    }
}

setTimeout(() => {
    closePopup();
}, 4000);