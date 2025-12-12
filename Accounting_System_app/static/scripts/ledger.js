document.addEventListener('DOMContentLoaded', function () {
    function fmt(v){ return (v===null||v===undefined) ? '0.00' : parseFloat(v).toFixed(2); }

    function buildUrl(accountId){
        // ledgerTransactionsUrlTemplate from template: "/.../ledger/account/0/transactions/"
        return ledgerTransactionsUrlTemplate.replace('/0/', '/' + encodeURIComponent(accountId) + '/');
    }

    function getDateFilters(){
        var s = document.getElementById('start_date');
        var e = document.getElementById('end_date');
        return {
            start: s ? s.value : '',
            end: e ? e.value : ''
        };
    }

    function openModal(accountId){
        var url = buildUrl(accountId);
        var dates = getDateFilters();
        var params = new URLSearchParams();
        if (dates.start) params.set('start_date', dates.start);
        if (dates.end) params.set('end_date', dates.end);
        var fetchUrl = url + (params.toString() ? '?' + params.toString() : '');

        fetch(fetchUrl, { headers: { 'X-Requested-With': 'XMLHttpRequest' }})
        .then(r => r.json())
        .then(data => {
            if (!data.success) { alert('Could not load transactions'); return; }

            var info = document.getElementById('ledgerAccountInfo');
            info.textContent = `${data.account.code || ''} — ${data.account.name || ''} (${data.account.type || ''})`;

            var tbody = document.getElementById('ledger-transactions-body');
            tbody.innerHTML = '';

            var totalD = 0, totalC = 0, running = 0;
            data.transactions.forEach(function(tx){
                var tr = document.createElement('tr');

                var tdNo = document.createElement('td'); tdNo.textContent = tx.entry_no || ''; tr.appendChild(tdNo);
                var tdDate = document.createElement('td'); tdDate.textContent = tx.entry_date || ''; tr.appendChild(tdDate);
                var tdDesc = document.createElement('td'); tdDesc.textContent = tx.description || ''; tr.appendChild(tdDesc);

                var tdD = document.createElement('td'); tdD.className = 'text-end'; tdD.textContent = fmt(tx.debit); tr.appendChild(tdD);
                var tdC = document.createElement('td'); tdC.className = 'text-end'; tdC.textContent = fmt(tx.credit); tr.appendChild(tdC);

                // running balance per account (debit - credit)
                running += (parseFloat(tx.debit || 0) - parseFloat(tx.credit || 0));
                // optionally show running in a new cell: append if desired

                tbody.appendChild(tr);

                totalD += parseFloat(tx.debit || 0);
                totalC += parseFloat(tx.credit || 0);
            });

            document.getElementById('ledger-modal-total-debit').textContent = fmt(totalD);
            document.getElementById('ledger-modal-total-credit').textContent = fmt(totalC);

            var modalEl = document.getElementById('ledgerAccountModal');
            var bs = bootstrap.Modal.getOrCreateInstance(modalEl);
            bs.show();
        })
        .catch(err => { console.error(err); alert('Failed to load transactions'); });
    }

    // attach click handler (delegated in case rows are re-rendered)
    document.addEventListener('click', function(e){
        var row = e.target.closest('.ledger-row');
        if (!row) return;
        row.style.cursor = 'pointer';
        var accountId = row.getAttribute('data-account-id');
        if (accountId) openModal(accountId);
    });
});