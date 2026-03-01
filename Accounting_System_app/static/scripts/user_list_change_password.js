// Password toggle for password field
const togglePassword = document.querySelector("#togglePassword");
const password = document.querySelector("#password");
const passwordIcon = togglePassword.querySelector("i");

togglePassword.addEventListener("click", function () {
    const type = password.getAttribute("type") === "password" ? "text" : "password";
    password.setAttribute("type", type);

    passwordIcon.classList.toggle("bi-eye");
    passwordIcon.classList.toggle("bi-eye-slash");
});

// Password toggle for confirm password field
const toggleConfirmPassword = document.querySelector("#toggleConfirmPassword");
const confirmPassword = document.querySelector("#confirm_password");
const confirmPasswordIcon = toggleConfirmPassword.querySelector("i");

toggleConfirmPassword.addEventListener("click", function () {
    const type = confirmPassword.getAttribute("type") === "password" ? "text" : "password";
    confirmPassword.setAttribute("type", type);

    confirmPasswordIcon.classList.toggle("bi-eye");
    confirmPasswordIcon.classList.toggle("bi-eye-slash");
});

// Password toggle for new password field
const toggleNewPassword = document.querySelector("#toggleNewPassword");
const newPassword = document.querySelector("#new_password");
const newPasswordIcon = toggleNewPassword.querySelector("i");

toggleNewPassword.addEventListener("click", function () {
    const type = newPassword.getAttribute("type") === "password" ? "text" : "password";
    newPassword.setAttribute("type", type);

    newPasswordIcon.classList.toggle("bi-eye");
    newPasswordIcon.classList.toggle("bi-eye-slash");
});

// Password toggle for confirm new password field
const toggleConfirmNewPassword = document.querySelector("#toggleConfirmNewPassword");
const confirmNewPassword = document.querySelector("#confirm_new_password");
const confirmNewPasswordIcon = toggleConfirmNewPassword.querySelector("i");

toggleConfirmNewPassword.addEventListener("click", function () {
    const type = confirmNewPassword.getAttribute("type") === "password" ? "text" : "password";
    confirmNewPassword.setAttribute("type", type);

    confirmNewPasswordIcon.classList.toggle("bi-eye");
    confirmNewPasswordIcon.classList.toggle("bi-eye-slash");
});

// Open change password modal
function openChangePasswordModal(userId, username) {
    document.getElementById('change_password_user_id').value = userId;
    document.getElementById('changePasswordUsername').textContent = username;
    document.getElementById('new_password').value = '';
    document.getElementById('confirm_new_password').value = '';
    document.getElementById('changePasswordError').style.display = 'none';
    
    const modal = new bootstrap.Modal(document.getElementById('changePasswordModal'));
    modal.show();
}

// Handle change password form submission
document.getElementById('change_password_form').addEventListener('submit', function(e) {
    e.preventDefault();
    
    const newPassword = document.getElementById('new_password').value;
    const confirmNewPassword = document.getElementById('confirm_new_password').value;
    const userId = document.getElementById('change_password_user_id').value;
    const errorDiv = document.getElementById('changePasswordError');
    
    if (newPassword !== confirmNewPassword) {
        errorDiv.textContent = 'Passwords do not match!';
        errorDiv.style.display = 'block';
        return;
    }
    
    if (newPassword.length < 8) {
        errorDiv.textContent = 'Password must be at least 8 characters long!';
        errorDiv.style.display = 'block';
        return;
    }
    
    // Submit password change via AJAX
    fetch("{% url 'AccountingSystem:change_user_password' %}", {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value
        },
        body: JSON.stringify({
            user_id: userId,
            new_password: newPassword
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            bootstrap.Modal.getInstance(document.getElementById('changePasswordModal')).hide();
            alert('Password changed successfully!');
        } else {
            errorDiv.textContent = data.error || 'Failed to change password';
            errorDiv.style.display = 'block';
        }
    })
    .catch(error => {
        errorDiv.textContent = 'An error occurred while changing the password';
        errorDiv.style.display = 'block';
        console.error('Error:', error);
    });
});

// Toggle user active status
function toggleUserStatus(userId, isActive) {
    const action = isActive ? 'deactivate' : 'activate';
    if (!confirm(`Are you sure you want to ${action} this user?`)) {
        return;
    }
    
    fetch("{% url 'AccountingSystem:toggle_user_active' %}", {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value
        },
        body: JSON.stringify({
            user_id: userId
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            location.reload(); // Reload to reflect changes
        } else {
            alert('Failed to update user status: ' + (data.error || 'Unknown error'));
        }
    })
    .catch(error => {
        alert('An error occurred while updating user status');
        console.error('Error:', error);
    });
}