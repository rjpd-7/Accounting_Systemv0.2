document.addEventListener("DOMContentLoaded", function () {
    if(!localStorage.getItem('journal_code_counter')){
        localStorage.setItem('journal_code_counter', 0);
    }

    function generateJournalCode(){
        let last_number = parseInt(localStorage.getItem('journal_code_counter'), 10);
        // Incremental part, padded to 10 digits
        let incremental = last_number.toString().padStart(10, '0');
        // Prefix 'JE' + 10 digit incremental = 12 digits total
        return 'JE-' + incremental;
    }

    // Generate journal code once insert journal modal opens
    document.getElementById('staticBackdrop').addEventListener('shown.bs.modal', function () {
         console.log("Modal opened"); // Debug log
        document.getElementById("journal_code").value = generateJournalCode();
    });

    // Handle form submit
    document.getElementById("journal_form").addEventListener("submit", (e) => {
        //e.preventDefault();

        let journal_code = document.getElementById("journal_code").value;

        //if (!account_name || !account_type) {
        //    alert("Please complete all fields.");
        //    return;
        //}

        alert(`Account Created!\nAccount Code  : ${account_code}\nAccount Name : ${account_name}\nAccount Type   : ${account_type}`);

        // Increment code_counter
        localStorage.setItem('journal_code_counter', parseInt(localStorage.getItem('journal_code_counter'), 10) + 1);

    });
});