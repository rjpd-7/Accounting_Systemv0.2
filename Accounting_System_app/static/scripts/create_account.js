document.addEventListener("DOMContentLoaded", function () {
    function generateAccountCode(){
        let type_of_acc = document.getElementById("account_type").value;
        
        // Fetch the next code from the server
        fetch(`/api/next_account_code/?type=${encodeURIComponent(type_of_acc)}`)
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    document.getElementById("account_code").value = data.code;
                }
            })
            .catch(error => console.error('Error fetching account code:', error));
    }

    // Set account code when modal opens
    document.getElementById('staticBackdrop').addEventListener('shown.bs.modal', function () {
        generateAccountCode();
    });

    // Update account code when type changes
    document.getElementById("account_type").addEventListener("change", () => {
        generateAccountCode();
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

    });
    
    // Reset the form when closed
    document.getElementById('staticBackdrop').addEventListener('hidden.bs.modal', function () {
        const form = document.getElementById('account_form');

        // Reset the entire form
        form.reset();

        // Generate next code after reset
        generateAccountCode();

    });
});