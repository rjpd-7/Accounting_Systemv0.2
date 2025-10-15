document.addEventListener('DOMContentLoaded', function() {
    var editButtons = document.querySelectorAll('button[data-bs-target="#EDITstaticBackdrop"]');
    var updateAccountName = document.getElementById('update_account_name');
    var updateAccountId = document.getElementById('update_account_id');
    var updateForm = document.getElementById('updateAccountForm');

    editButtons.forEach(function(btn) {
        btn.addEventListener('click', function() {
            updateAccountName.value = btn.getAttribute('data-name');
            updateAccountId.value = btn.getAttribute('data-id');
            updateForm.action = '/update_account/' + btn.getAttribute('data-id') + '/'; // Adjust URL as needed
        });
    });
});