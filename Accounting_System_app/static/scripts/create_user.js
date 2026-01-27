document.addEventListener("DOMContentLoaded", function () {
    // Handle form submit
    document.getElementById("user_form").addEventListener("submit", (e) => {
        let first_name = document.getElementById("first_name").value;
        let last_name = document.getElementById("last_name").value;
        let username = document.getElementById("username").value;
        let email = document.getElementById("email").value;
        let password = document.getElementById("password").value;
        let role = document.getElementById("role").value;

        if (!first_name || !last_name || !username || !email || !password || !role) {
            e.preventDefault();
            alert("Please complete all fields.");
            return;
        }

        // Optional: Show confirmation
        // alert(`User Created!\nName: ${first_name} ${last_name}\nUsername: ${username}\nEmail: ${email}\nRole: ${role}`);
    });

    // Reset the form when modal is closed
    document.getElementById('createUserModal').addEventListener('hidden.bs.modal', function () {
        const form = document.getElementById('user_form');
        form.reset();
    });
});