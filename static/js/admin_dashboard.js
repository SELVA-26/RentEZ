/* =====================================================
   ADMIN DASHBOARD
===================================================== */


/* =====================================================
   SEARCH + FILTER
===================================================== */

const searchInput = document.getElementById("businessSearch");
const statusFilter = document.getElementById("statusFilter");
const businessCards = document.querySelectorAll(".business-card");
const resultsCount = document.getElementById("resultsCount");


function filterBusinesses() {

    const searchValue =
        searchInput.value.toLowerCase().trim();

    const statusValue =
        statusFilter.value;

    let visibleCount = 0;


    businessCards.forEach(card => {

        const name =
            card.dataset.name || "";

        const email =
            card.dataset.email || "";

        const status =
            card.dataset.status || "";


        const matchesSearch =
            name.includes(searchValue) ||
            email.includes(searchValue);


        const matchesStatus =
            statusValue === "all" ||
            status === statusValue;


        if (matchesSearch && matchesStatus) {

            card.style.display = "";

            visibleCount++;

        } else {

            card.style.display = "none";

        }

    });


    resultsCount.textContent =
        visibleCount +
        (visibleCount === 1
            ? " business"
            : " businesses");

}


if (searchInput) {

    searchInput.addEventListener(
        "input",
        filterBusinesses
    );

}


if (statusFilter) {

    statusFilter.addEventListener(
        "change",
        filterBusinesses
    );

}


/* =====================================================
   APPROVE MODAL
===================================================== */

const approveModal =
    document.getElementById("approveModal");

const approveForm =
    document.getElementById("approveForm");

const approveBusinessName =
    document.getElementById("approveBusinessName");


function openApproveModal(button) {

    const businessId =
        button.dataset.businessId;

    const businessName =
        button.dataset.businessName;


    approveBusinessName.textContent =
        businessName;


    approveForm.action =
        "/admin/business/" +
        businessId +
        "/approve";


    approveModal.classList.add("active");

    document.body.style.overflow = "hidden";
}


function closeApproveModal() {

    approveModal.classList.remove("active");

    document.body.style.overflow = "";

}


/* =====================================================
   REJECT MODAL
===================================================== */

const rejectModal =
    document.getElementById("rejectModal");

const rejectForm =
    document.getElementById("rejectForm");

const rejectBusinessName =
    document.getElementById("rejectBusinessName");

const rejectionReason =
    document.getElementById("rejectionReason");


function openRejectModal(button) {

    const businessId =
        button.dataset.businessId;

    const businessName =
        button.dataset.businessName;


    rejectBusinessName.textContent =
        businessName;


    rejectForm.action =
        "/admin/business/" +
        businessId +
        "/reject";


    rejectionReason.value = "";


    rejectModal.classList.add("active");

    document.body.style.overflow = "hidden";


    setTimeout(() => {

        rejectionReason.focus();

    }, 100);

}


function closeRejectModal() {

    rejectModal.classList.remove("active");

    document.body.style.overflow = "";

}


/* =====================================================
   CLOSE WHEN CLICKING OUTSIDE
===================================================== */

if (approveModal) {

    approveModal.addEventListener(
        "click",
        function(event) {

            if (event.target === approveModal) {

                closeApproveModal();

            }

        }
    );

}


if (rejectModal) {

    rejectModal.addEventListener(
        "click",
        function(event) {

            if (event.target === rejectModal) {

                closeRejectModal();

            }

        }
    );

}


/* =====================================================
   ESCAPE KEY
===================================================== */

document.addEventListener(
    "keydown",
    function(event) {

        if (event.key !== "Escape") {
            return;
        }


        closeApproveModal();

        closeRejectModal();

    }
);


/* =====================================================
   ADMIN TABS
===================================================== */

const adminTabs =
    document.querySelectorAll(".admin-tab");

const adminContents =
    document.querySelectorAll(".admin-tab-content");


adminTabs.forEach(function (tab) {

    tab.addEventListener("click", function () {

        const target =
            this.dataset.tab;


        adminTabs.forEach(function (item) {
            item.classList.remove("active");
        });


        adminContents.forEach(function (content) {
            content.classList.remove("active");
        });


        this.classList.add("active");


        const targetContent =
            document.querySelector(
                `[data-content="${target}"]`
            );


        if (targetContent) {
            targetContent.classList.add("active");
        }

    });

});