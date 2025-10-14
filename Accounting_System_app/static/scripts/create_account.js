// Auto input for the hidden date_time_created in create accounts
document.addEventListener('DOMContentLoaded', function() {
    const date_time_input = document.getElementById('account_date_time');
    account_date_time.value = new Date().toISOString().slice(0, 19).replace('T', ' ');
});