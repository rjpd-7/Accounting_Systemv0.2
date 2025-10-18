document.addEventListener("DOMContentLoaded", function () {
    if(!localStorage.getItem('code_counter')){
        localStorage.setItem('code_counter', 0);
    }

    function generateAccountCode(){
        let type_of_acc = document.getElementById("account_type").value;
        let last_number = parseInt(localStorage.getItem('code_counter'), 10);

        if(type_of_acc === "Assets"){
            return (100000 + last_number).toString();
        }
        else if(type_of_acc === "Liabilities"){
            return (200000 + last_number).toString();
        }
        else if(type_of_acc === "Equity"){
            return (300000 + last_number).toString();
        }
        else if(type_of_acc === "Revenue"){
            return (400000 + last_number).toString();
        }
        else if(type_of_acc === "Expenses"){
            return (500000 + last_number).toString();
        }
        return "";
    }

    // Set account code when modal opens
    document.getElementById('staticBackdrop').addEventListener('shown.bs.modal', function () {
        localStorage.setItem('code_counter', parseInt(localStorage.getItem('code_counter'), 10) + 1);
        document.getElementById("account_code").value = generateAccountCode();
    });

    // Update account code when type changes
    document.getElementById("account_type").addEventListener("change", () => {
        document.getElementById("account_code").value = generateAccountCode();
    });

    // Handle form submit
    document.getElementById("account_form").addEventListener("submit", (e) => {
        //e.preventDefault();

        let account_code = document.getElementById("account_code").value;
        let account_name = document.getElementById("account_name").value;
        let account_type = document.getElementById("account_type").value;
        let account_description = document.getElementById("account_description").value;

        if (!account_name || !account_type) {
            e.preventDefault();
            alert("Please complete all fields.");
            return;
        }

        alert(`Account Created!\nAccount Code  : ${account_code}\nAccount Name : ${account_name}\nAccount Type   : ${account_type}\n\nAccount Description: ${account_description}`);

        // Increment code_counter
        localStorage.setItem('code_counter', parseInt(localStorage.getItem('code_counter'), 10) + 1);
        // Reset form and generate next code
        //e.target.reset();
        //document.getElementById("account_code").value = generateAccountCode();

    });
    
    // Reset the form when closed
    document.getElementById('staticBackdrop').addEventListener('hidden.bs.modal', function () {
        const form = document.getElementById('account_form');

        // Reset the entire form
        form.reset();

        // Reset journal code
        document.getElementById("account_code").value = generateAccountCode();

    });
});