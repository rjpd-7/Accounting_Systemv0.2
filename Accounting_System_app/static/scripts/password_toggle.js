/**
 * Password Toggle Utility
 * Handles password visibility toggling for password input fields
 */

class PasswordToggle {
    constructor(toggleButtonId, passwordInputId) {
        this.toggleButton = document.querySelector(toggleButtonId);
        this.passwordInput = document.querySelector(passwordInputId);
        this.icon = this.toggleButton?.querySelector("i");
        
        if (this.toggleButton && this.passwordInput) {
            this.init();
        }
    }

    init() {
        this.toggleButton.addEventListener("click", () => {
            this.toggle();
        });
    }

    toggle() {
        const type = this.passwordInput.getAttribute("type") === "password" ? "text" : "password";
        this.passwordInput.setAttribute("type", type);
        
        this.icon.classList.toggle("bi-eye");
        this.icon.classList.toggle("bi-eye-slash");
    }
}

// Initialize password toggles when DOM is ready
document.addEventListener('DOMContentLoaded', function() {
    // Create User Modal password toggles
    new PasswordToggle("#togglePassword", "#password");
    new PasswordToggle("#toggleConfirmPassword", "#confirm_password");
    
    // Change Password Modal toggles
    new PasswordToggle("#toggleNewPassword", "#new_password");
    new PasswordToggle("#toggleConfirmNewPassword", "#confirm_new_password");

    // Teacher own-password modal toggles
    new PasswordToggle("#toggleCurrentPassword", "#current_password");
    new PasswordToggle("#toggleNewPasswordOwn", "#new_password_own");
    new PasswordToggle("#toggleConfirmNewPasswordOwn", "#confirm_new_password_own");
});
