document.addEventListener("DOMContentLoaded", function () {
    const form = document.getElementById("user_form");
    const modal = document.getElementById("createUserModal");

    if (!form || !modal) {
        return;
    }

    const fields = {
        firstName: document.getElementById("first_name"),
        lastName: document.getElementById("last_name"),
        username: document.getElementById("username"),
        email: document.getElementById("email"),
        password: document.getElementById("password"),
        confirmPassword: document.getElementById("confirm_password"),
        role: document.getElementById("role")
    };

    const submitButton = form.querySelector('button[type="submit"]');
    const namePattern = /^[A-Za-z][A-Za-z\s'-]{1,49}$/;
    const usernamePattern = /^[A-Za-z0-9._-]{3,20}$/;

    // Availability check timeouts
    let usernameCheckTimeout;
    let emailCheckTimeout;
    const availabilityStatus = {
        usernameAvailable: null,
        emailAvailable: null
    };

    function getOrCreateErrorElement(input) {
        const wrapper = input.closest(".mb-3");
        if (!wrapper) {
            return null;
        }

        let errorElement = wrapper.querySelector('.invalid-feedback[data-field-error="true"]');
        if (!errorElement) {
            errorElement = document.createElement("div");
            errorElement.className = "invalid-feedback";
            errorElement.dataset.fieldError = "true";
            
            // Insert after password-container if it exists, otherwise after the input
            const passwordContainer = input.closest(".password-container");
            if (passwordContainer) {
                passwordContainer.insertAdjacentElement("afterend", errorElement);
            } else {
                input.insertAdjacentElement("afterend", errorElement);
            }
        }

        return errorElement;
    }

    function markFieldValidity(input, isValid, message) {
        if (!input) {
            return isValid;
        }

        const hasValue = input.value.trim() !== "";
        const shouldBeValid = isValid && hasValue;

        const errorElement = getOrCreateErrorElement(input);
        input.classList.toggle("is-invalid", !isValid && hasValue);
        input.classList.toggle("is-valid", shouldBeValid);

        // Add inline styles for guaranteed visual feedback
        if (shouldBeValid) {
            input.style.borderColor = "#198754";
            input.style.borderWidth = "2px";
            input.style.backgroundColor = "#f0f9f7";
        } else if (!isValid && hasValue) {
            input.style.borderColor = "#dc3545";
            input.style.borderWidth = "2px";
            input.style.backgroundColor = "#fdf8f9";
        } else {
            input.style.borderColor = "";
            input.style.borderWidth = "";
            input.style.backgroundColor = "";
        }

        if (errorElement) {
            errorElement.textContent = message || "";
            if (message) {
                errorElement.style.display = "block";
                errorElement.style.color = "#dc3545";
                errorElement.style.fontSize = "0.875rem";
                errorElement.style.marginTop = "0.25rem";
            } else {
                errorElement.style.display = "none";
            }
        }

        return isValid;
    }

    function validateFirstName() {
        const value = fields.firstName.value.trim();
        if (!value) {
            return markFieldValidity(fields.firstName, false, "First name is required.");
        }
        if (!namePattern.test(value)) {
            return markFieldValidity(fields.firstName, false, "Use 2-50 letters. Spaces, apostrophes, and hyphens are allowed.");
        }
        return markFieldValidity(fields.firstName, true, "");
    }

    function validateLastName() {
        const value = fields.lastName.value.trim();
        if (!value) {
            return markFieldValidity(fields.lastName, false, "Last name is required.");
        }
        if (!namePattern.test(value)) {
            return markFieldValidity(fields.lastName, false, "Use 2-50 letters. Spaces, apostrophes, and hyphens are allowed.");
        }
        return markFieldValidity(fields.lastName, true, "");
    }

    function validateUsername() {
        const value = fields.username.value.trim();
        if (!value) {
            return markFieldValidity(fields.username, false, "Username is required.");
        }
        if (!usernamePattern.test(value)) {
            return markFieldValidity(fields.username, false, "Use 3-20 characters: letters, numbers, dot, underscore, or hyphen.");
        }
        // Check availability status from last AJAX call
        if (availabilityStatus.usernameAvailable === false) {
            return markFieldValidity(fields.username, false, "This username is already taken.");
        }
        return markFieldValidity(fields.username, true, "");
    }

    function validateEmail() {
        const value = fields.email.value.trim();
        if (!value) {
            return markFieldValidity(fields.email, false, "Email is required.");
        }
        if (!fields.email.checkValidity()) {
            return markFieldValidity(fields.email, false, "Enter a valid email address.");
        }
        // Check availability status from last AJAX call
        if (availabilityStatus.emailAvailable === false) {
            return markFieldValidity(fields.email, false, "This email is already registered.");
        }
        return markFieldValidity(fields.email, true, "");
    }

    function validatePassword() {
        const value = fields.password.value;
        if (!value) {
            return markFieldValidity(fields.password, false, "Password is required.");
        }
        return markFieldValidity(fields.password, true, "");
    }

    function validateConfirmPassword() {
        const value = fields.confirmPassword.value;
        if (!value) {
            return markFieldValidity(fields.confirmPassword, false, "Please confirm the password.");
        }
        if (value !== fields.password.value) {
            return markFieldValidity(fields.confirmPassword, false, "Passwords do not match.");
        }
        return markFieldValidity(fields.confirmPassword, true, "");
    }

    function validateRole() {
        const value = fields.role.value.trim();
        if (!value) {
            return markFieldValidity(fields.role, false, "Please select a role.");
        }
        return markFieldValidity(fields.role, true, "");
    }

    function validateForm() {
        const isValid = [
            validateFirstName(),
            validateLastName(),
            validateUsername(),
            validateEmail(),
            validatePassword(),
            validateConfirmPassword(),
            validateRole()
        ].every(Boolean);

        if (submitButton) {
            submitButton.disabled = !isValid;
        }

        return isValid;
    }

    // AJAX availability check for username
    function checkUsernameAvailability() {
        const username = fields.username.value.trim();
        
        clearTimeout(usernameCheckTimeout);
        
        if (!username || !usernamePattern.test(username)) {
            availabilityStatus.usernameAvailable = null;
            return;
        }

        usernameCheckTimeout = setTimeout(function () {
            fetch('/check_username_email_availability/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCsrfToken()
                },
                body: JSON.stringify({ username: username, email: '' })
            })
            .then(response => response.json())
            .then(data => {
                availabilityStatus.usernameAvailable = data.username_available;
                validateForm();
            })
            .catch(error => console.error('Error checking username:', error));
        }, 500); // Debounce for 500ms
    }

    // AJAX availability check for email
    function checkEmailAvailability() {
        const email = fields.email.value.trim();
        
        clearTimeout(emailCheckTimeout);
        
        if (!email || !fields.email.checkValidity()) {
            availabilityStatus.emailAvailable = null;
            return;
        }

        emailCheckTimeout = setTimeout(function () {
            fetch('/check_username_email_availability/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCsrfToken()
                },
                body: JSON.stringify({ username: '', email: email })
            })
            .then(response => response.json())
            .then(data => {
                availabilityStatus.emailAvailable = data.email_available;
                validateForm();
            })
            .catch(error => console.error('Error checking email:', error));
        }, 500); // Debounce for 500ms
    }

    function getCsrfToken() {
        const tokenInput = document.querySelector('[name=csrfmiddlewaretoken]');
        return tokenInput ? tokenInput.value : '';
    }

    fields.firstName.addEventListener("input", validateForm);
    fields.lastName.addEventListener("input", validateForm);
    fields.username.addEventListener("input", function () {
        checkUsernameAvailability();
        validateForm();
    });
    fields.email.addEventListener("input", function () {
        checkEmailAvailability();
        validateForm();
    });
    fields.password.addEventListener("input", validateForm);
    fields.confirmPassword.addEventListener("input", validateForm);
    fields.role.addEventListener("change", validateForm);

    form.addEventListener("submit", function (e) {
        if (!validateForm()) {
            e.preventDefault();
        }
    });

    modal.addEventListener("hidden.bs.modal", function () {
        form.reset();
        availabilityStatus.usernameAvailable = null;
        availabilityStatus.emailAvailable = null;
        Object.values(fields).forEach(function (input) {
            if (!input) {
                return;
            }
            input.classList.remove("is-invalid", "is-valid");
            input.style.borderColor = "";
            input.style.borderWidth = "";
            input.style.backgroundColor = "";
            const errorElement = getOrCreateErrorElement(input);
            if (errorElement) {
                errorElement.textContent = "";
                errorElement.style.display = "none";
            }
        });
        if (submitButton) {
            submitButton.disabled = false;
        }
    });

    validateForm();
});