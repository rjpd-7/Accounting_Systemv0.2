// Pre-fills the update modal with the selected account
document.addEventListener('DOMContentLoaded', function() {
    var edit_buttons = document.querySelectorAll('button[data-bs-target="#EDITstaticBackdrop"]');
    var updateAccountName = document.getElementById('update_account_name');
    var updateAccountDescription = document.getElementById('update_account_description');
    var updateAccountId = document.getElementById('update_account_id');
    var updateForm = document.getElementById('updateAccountForm');
    var oldAccountName = "";
    var oldAccountDescription = "";

    edit_buttons.forEach(function(btn) {
        btn.addEventListener('click', function() {
            oldAccountName = btn.getAttribute('data-name');
            updateAccountName.value = oldAccountName;
            oldAccountDescription = btn.getAttribute('data-description') || "";
            updateAccountDescription.value = oldAccountDescription
            updateAccountId.value = btn.getAttribute('data-id');
            updateForm.action = '/update_account/' + btn.getAttribute('data-id') + '/'; // Adjust URL as needed
        });
    });

    updateForm.addEventListener('submit', function(e) {
        if (!updateAccountName.value.trim()) {
            alert('Account name cannot be empty!');
            e.preventDefault();
            return;
        }
        alert('Account name has been updated!\nOld Name: ' + oldAccountName + '\nNew Name: ' + updateAccountName.value.trim() + '\nOld Description: ' + oldAccountDescription + '\nNew Description: ' + updateAccountDescription.value.trim());
    });
});