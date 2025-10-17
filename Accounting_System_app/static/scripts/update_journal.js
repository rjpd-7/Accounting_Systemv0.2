document.addEventListener("DOMContentLoaded", function () {
    // === Edit Modal Variables ===
    const editModal = document.getElementById("EDITstaticBackdrop");
    const editForm = document.getElementById("edit_journal_form");
    const editTbody = document.getElementById("edit-journal-entry-body");
    const editAddRowBtn = document.getElementById("edit-add-journal-row");
    const editClearAmountsBtn = document.getElementById("edit-clear-amounts-btn");
    const editTotalDebitField = document.getElementById("edit_total_debit");
    const editTotalCreditField = document.getElementById("edit_total_credit");
    const editAllAccountsSelect = document.getElementById("edit-all-accounts-select");

    // Open Edit Modal and Fill Data 
    editModal.addEventListener("show.bs.modal", function (event) {
        const button = event.relatedTarget;

        // These attributes come from the edit button on your table
        const entryDate = button.getAttribute("data-entrydate");
        const description = button.getAttribute("data-description");
        const entries = JSON.parse(button.getAttribute("data-entries"));

        document.getElementById("edit-entry-date").value = entryDate;
        document.getElementById("journal_description").value = description;

        // Clear any previous rows
        editTbody.innerHTML = "";

        entries.forEach((entry, index) => {
            const isFirstRow = index === 0;

            const newRow = document.createElement("tr");
            newRow.innerHTML = `
                <td>
                    <select name="edit_account_name" required>
                        ${
                            [...editAllAccountsSelect.options]
                                .filter(
                                    (opt) =>
                                        !isFirstRow ||
                                        opt.dataset.type === "Assets" ||
                                        opt.dataset.type === "Expenses"
                                )
                                .map(
                                    (opt) =>
                                        `<option value="${opt.value}" data-type="${opt.dataset.type}" ${
                                            opt.value == entry.account_id ? "selected" : ""
                                        }>${opt.text}</option>`
                                )
                                .join("")
                        }
                    </select>
                </td>
                <td><input type="text" name="edit_account_type" value="${entry.account_type}" readonly></td>
                <td><input type="number" name="edit_debit" step="0.01" min="0" value="${entry.debit}" ${
                isFirstRow ? "" : ""
            }></td>
                <td><input type="number" name="edit_credit" step="0.01" min="0" value="${entry.credit}" ${
                isFirstRow ? "readonly" : ""
            }></td>
                <td>${isFirstRow ? "" : '<button type="button" class="btn btn-danger btn-sm edit-remove-row">Remove</button>'}</td>
            `;

            editTbody.appendChild(newRow);
            attachEditListeners(newRow, isFirstRow);
        });

        calculateEditTotals();
    });

    // Add Row in Edit Modal 
    editAddRowBtn.addEventListener("click", function () {
        const newRow = document.createElement("tr");
        newRow.innerHTML = `
            <td><select name="edit_account_name" required>${editAllAccountsSelect.innerHTML}</select></td>
            <td><input type="text" name="edit_account_type" readonly></td>
            <td><input type="number" name="edit_debit" step="0.01" min="0"></td>
            <td><input type="number" name="edit_credit" step="0.01" min="0"></td>
            <td><button type="button" class="btn btn-danger btn-sm edit-remove-row">Remove</button></td>
        `;
        editTbody.appendChild(newRow);
        attachEditListeners(newRow, false);
    });

    //  Remove Row in Edit Modal 
    editTbody.addEventListener("click", function (e) {
        if (e.target.classList.contains("edit-remove-row")) {
            const row = e.target.closest("tr");
            row.remove();
            calculateEditTotals();
        }
    });

    // Clear All Debit/Credit Values 
    editClearAmountsBtn.addEventListener("click", function () {
        editTbody
            .querySelectorAll('input[name="edit_debit"], input[name="edit_credit"]')
            .forEach((input) => {
                input.value = "";
            });
        calculateEditTotals();
    });

    //  Account Type Restriction and Update 
    function updateEditAccountType(selectElem, isFirstRow) {
        const row = selectElem.closest("tr");
        const typeInput = row.querySelector('input[name="edit_account_type"]');
        const debitInput = row.querySelector('input[name="edit_debit"]');
        const creditInput = row.querySelector('input[name="edit_credit"]');
        const selectedOption = selectElem.options[selectElem.selectedIndex];
        const type = selectedOption ? selectedOption.getAttribute("data-type") : "";

        typeInput.value = type;

        if (isFirstRow) {
            // First row restriction: must be Assets/Expenses (debit only)
            if (type !== "Assets" && type !== "Expenses") {
                alert("The first row must be a debit-type account (Assets or Expenses).");
                selectElem.selectedIndex = 0;
                typeInput.value = "";
                return;
            }
            debitInput.removeAttribute("readonly");
            creditInput.value = "";
            creditInput.setAttribute("readonly", true);
        } else {
            if (type === "Assets" || type === "Expenses") {
                debitInput.removeAttribute("readonly");
                creditInput.value = "";
                creditInput.setAttribute("readonly", true);
            } else if (
                type === "Liabilities" ||
                type === "Equity" ||
                type === "Revenue"
            ) {
                creditInput.removeAttribute("readonly");
                debitInput.value = "";
                debitInput.setAttribute("readonly", true);
            } else {
                debitInput.removeAttribute("readonly");
                creditInput.removeAttribute("readonly");
            }
        }

        calculateEditTotals();
    }

    // Attach Listeners to Row 
    function attachEditListeners(row, isFirstRow) {
        const selectElem = row.querySelector('select[name="edit_account_name"]');
        selectElem.addEventListener("change", function () {
            updateEditAccountType(this, isFirstRow);
        });
        updateEditAccountType(selectElem, isFirstRow);

        row.querySelectorAll('input[name="edit_debit"], input[name="edit_credit"]').forEach((input) => {
            input.addEventListener("input", calculateEditTotals);
        });
    }

    // Calculate Totals 
    function calculateEditTotals() {
        let totalDebit = 0;
        let totalCredit = 0;

        editTbody.querySelectorAll('input[name="edit_debit"]').forEach((input) => {
            totalDebit += parseFloat(input.value) || 0;
        });
        editTbody.querySelectorAll('input[name="edit_credit"]').forEach((input) => {
            totalCredit += parseFloat(input.value) || 0;
        });

        editTotalDebitField.value = totalDebit.toFixed(2);
        editTotalCreditField.value = totalCredit.toFixed(2);

        // Styling based on balance
        if (totalDebit === totalCredit && totalDebit !== 0) {
            editTotalDebitField.style.backgroundColor = "#d4edda";
            editTotalCreditField.style.backgroundColor = "#d4edda";
            editTotalDebitField.style.color = "#155724";
            editTotalCreditField.style.color = "#155724";
        } else {
            editTotalDebitField.style.backgroundColor = "#f8d7da";
            editTotalCreditField.style.backgroundColor = "#f8d7da";
            editTotalDebitField.style.color = "#721c24";
            editTotalCreditField.style.color = "#721c24";
        }
    }

    // Validate Before Submit 
    editForm.addEventListener("submit", function (e) {
        const totalDebit = parseFloat(editTotalDebitField.value) || 0;
        const totalCredit = parseFloat(editTotalCreditField.value) || 0;

        if (totalDebit !== totalCredit) {
            e.preventDefault();
            alert("Total Debit and Credit must be equal before saving!");
            return;
        }

        alert("Journal Entry Updated Successfully!");
    });
});