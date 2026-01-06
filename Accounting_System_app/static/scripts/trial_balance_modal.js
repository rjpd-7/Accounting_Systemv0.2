document.addEventListener('DOMContentLoaded', function () {
    var form = document.getElementById('trial-balance-form');
    var resultsContainer = document.getElementById('tb-results');
    var clearBtn = document.getElementById('tb-clear-btn');
    var modalEl = document.getElementById('trialBalanceModal');

    function fmt(n) { return (n === null || n === undefined) ? '0.00' : parseFloat(n).toFixed(2); }

    function renderResults(data) {
        if (!data || !Array.isArray(data.accounts) || data.accounts.length === 0) {
            resultsContainer.innerHTML = '<div class="text-muted">No accounts or transactions for selected period.</div>';
            return;
        }

        var html = [];
        html.push('<div class="table-responsive">');
        html.push('<table class="table table-sm table-bordered mb-3">');
        html.push('<thead class="table-light"><tr><th>Account</th><th class="text-end">Debit</th><th class="text-end">Credit</th><th class="text-end">Balance</th></tr></thead>');
        html.push('<tbody>');

        var totalDebit = 0;
        var totalCredit = 0;

        data.accounts.forEach(function(acc, idx) {
            var rowId = 'tb-acc-' + acc.id;
            html.push('<tr class="align-middle">');
            html.push('<td><strong>' + (acc.code || '') + '</strong> &nbsp; ' + (acc.name || '') + '</td>');
            html.push('<td class="text-end">' + fmt(acc.total_debit) + '</td>');
            html.push('<td class="text-end">' + fmt(acc.total_credit) + '</td>');
            html.push('<td class="text-end">' + fmt(acc.balance) + '</td>');
            //html.push('<td class="text-center"><button class="btn btn-sm btn-outline-secondary tb-toggle" data-target="#' + rowId + '">Transactions</button></td>');
            html.push('</tr>');

            // accumulate totals
            totalDebit += parseFloat(acc.total_debit || 0);
            totalCredit += parseFloat(acc.total_credit || 0);

            // hidden transactions row
            html.push('<tr id="' + rowId + '" class="tb-trans-row" style="display:none;">');
            html.push('<td colspan="5">');
            html.push('<div class="table-responsive">');
            html.push('<table class="table table-sm mb-0">');
            html.push('<thead><tr><th>Entry No</th><th>Date</th><th>Description</th><th class="text-end">Debit</th><th class="text-end">Credit</th></tr></thead>');
            html.push('<tbody>');
            if (acc.transactions && acc.transactions.length) {
                acc.transactions.forEach(function(tx) {
                    html.push('<tr>');
                    html.push('<td>' + (tx.entry_no || '') + '</td>');
                    html.push('<td>' + (tx.entry_date || '') + '</td>');
                    html.push('<td>' + (tx.description || '') + '</td>');
                    html.push('<td class="text-end">' + fmt(tx.debit) + '</td>');
                    html.push('<td class="text-end">' + fmt(tx.credit) + '</td>');
                    html.push('</tr>');
                });
            } else {
                html.push('<tr><td colspan="5" class="text-muted">No transactions</td></tr>');
            }
            html.push('</tbody>');
            html.push('</table>');
            html.push('</div>');
            html.push('</td>');
            html.push('</tr>');
        });

        html.push('</tbody>');

        // totals footer
        html.push('<tfoot class="table-light fw-bold">');
        html.push('<tr>');
        html.push('<td class="text-end">Totals</td>');
        html.push('<td class="text-end">' + fmt(totalDebit) + '</td>');
        html.push('<td class="text-end">' + fmt(totalCredit) + '</td>');
        html.push('<td class="text-end">' + fmt(totalDebit - totalCredit) + '</td>');
        //html.push('<td></td>');
        html.push('</tr>');
        html.push('</tfoot>');

        html.push('</table></div>');
        resultsContainer.innerHTML = html.join('');
    }

    function fetchTrialBalance(start, end) {
        var params = new URLSearchParams();
        if (start) params.set('start_date', start);
        if (end) params.set('end_date', end);
        var url = trialBalanceJsonUrl + (params.toString() ? ('?' + params.toString()) : '');

        resultsContainer.innerHTML = '<div class="text-muted">Loading...</div>';

        fetch(url, { headers: { 'X-Requested-With': 'XMLHttpRequest' } })
            .then(function (r) { return r.json(); })
            .then(function (data) {
                if (!data.success) {
                    resultsContainer.innerHTML = '<div class="text-danger">Failed to load trial balance.</div>';
                    return;
                }
                renderResults(data);
            })
            .catch(function (err) {
                console.error(err);
                resultsContainer.innerHTML = '<div class="text-danger">Error fetching data.</div>';
            });
    }

    if (form) {
        form.addEventListener('submit', function (e) {
            e.preventDefault();
            var start = document.getElementById('tb-start-date').value;
            var end = document.getElementById('tb-end-date').value;
            fetchTrialBalance(start, end);
            // update download link
            updateDownloadLink(start, end);
        });
    }

    if (clearBtn) {
        clearBtn.addEventListener('click', function () {
            document.getElementById('tb-start-date').value = '';
            document.getElementById('tb-end-date').value = '';
            resultsContainer.innerHTML = '<div class="text-muted">No data. Choose a date range and click Generate.</div>';
            updateDownloadLink('', '');
        });
    }

    // delegate click to toggle transaction rows
    document.addEventListener('click', function (e) {
        var btn = e.target.closest('.tb-toggle');
        if (!btn) return;
        var target = document.querySelector(btn.getAttribute('data-target'));
        if (!target) return;
        if (target.style.display === 'none' || !target.style.display) {
            target.style.display = '';
        } else {
            target.style.display = 'none';
        }
    });

    // optional: auto-generate using page-level filters if present when modal opens
    function updateDownloadLink(start, end) {
        var link = document.getElementById('tb-download-link');
        if (!link) return;
        var params = new URLSearchParams();
        if (start) params.set('start_date', start);
        if (end) params.set('end_date', end);
        var pdfUrl = trialBalancePdfUrl + (params.toString() ? ('?' + params.toString()) : '');
        link.href = pdfUrl;
        // Enable button only if at least one date is set
        if (start || end) {
            link.classList.remove('disabled');
            link.onclick = null;
        } else {
            link.classList.add('disabled');
            link.onclick = function() { return false; };
        }
    }

    if (modalEl) {
        modalEl.addEventListener('show.bs.modal', function () {
            // optionally prefill from page filters if you use start_date/end_date on the page
            var pageStart = document.getElementById('start_date') ? document.getElementById('start_date').value : '';
            var pageEnd = document.getElementById('end_date') ? document.getElementById('end_date').value : '';
            if (pageStart) document.getElementById('tb-start-date').value = pageStart;
            if (pageEnd) document.getElementById('tb-end-date').value = pageEnd;
            updateDownloadLink(document.getElementById('tb-start-date').value, document.getElementById('tb-end-date').value);
        });
    }
});