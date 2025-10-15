// Pre-fills the update modal with the selected account
document.addEventListener('DOMContentLoaded', function() {
    var edit_buttons = document.querySelectorAll('button[data-bs-target="#EDITstaticBackdrop"]');
    var updateAccountName = document.getElementById('update_account_name');
    var updateAccountId = document.getElementById('update_account_id');
    var updateForm = document.getElementById('updateAccountForm');
    var oldAccountName = "";

    edit_buttons.forEach(function(btn) {
        btn.addEventListener('click', function() {
            oldAccountName = btn.getAttribute('data-name');
            updateAccountName.value = oldAccountName;
            updateAccountId.value = btn.getAttribute('data-id');
            updateForm.action = '/update_account/' + btn.getAttribute('data-id') + '/'; // Adjust URL as needed
        });
    });

    // Alerts with old and updated account name
    updateForm.addEventListener('submit', function() {
        if (!updateAccountName.value.trim()) {
            alert('Account name cannot be empty!');
            return;
        }
        alert('Account name has been updated!\nOld Name: ' + oldAccountName + '\nNew Name: ' + updateAccountName.value.trim());
    });
});