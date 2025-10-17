document.addEventListener("DOMContentLoaded", function() {
    const editButtons = document.querySelectorAll(".edit-btn");

    editButtons.forEach(btn => {
        btn.addEventListener("click", function() {
            document.getElementById("edit_entry_id").value = this.dataset.id;
            document.getElementById("edit_journal_code").value = this.dataset.code;
            document.getElementById("edit_entry_date").value = this.dataset.date;
            document.getElementById("edit_account_name").value = this.dataset.name;
            document.getElementById("edit_debit").value = this.dataset.debit;
            document.getElementById("edit_credit").value = this.dataset.credit;
            document.getElementById("edit_description").value = this.dataset.description;
        });
    });
});