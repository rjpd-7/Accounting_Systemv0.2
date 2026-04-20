document.addEventListener('DOMContentLoaded', function () {
    function fmt(v){ return (v===null||v===undefined) ? '0.00' : parseFloat(v).toFixed(2); }
    var groupForecastChartInstance = null;

    function getDateFiltersFromPageOrUrl(){
        var s = document.getElementById('start_date');
        var e = document.getElementById('end_date');
        var start = s ? s.value : '';
        var end = e ? e.value : '';

        if (!start || !end){
            var params = new URLSearchParams(window.location.search);
            if (!start) start = params.get('start_date') || '';
            if (!end) end = params.get('end_date') || '';
        }

        return { start: start, end: end };
    }

    function colorByIndex(idx, alpha){
        var hue = (idx * 57) % 360;
        if (alpha === undefined) alpha = 1;
        return 'hsla(' + hue + ', 70%, 45%, ' + alpha + ')';
    }

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

    function buildFetchUrl(accountId){
        var url = buildUrl(accountId);
        var dates = getDateFiltersFromPageOrUrl();
        var params = new URLSearchParams();
        if (dates.start) params.set('start_date', dates.start);
        if (dates.end) params.set('end_date', dates.end);
        return url + (params.toString() ? '?' + params.toString() : '');
    }

    function buildGroupForecastUrl(groupId){
        var url = ledgerGroupForecastUrlTemplate.replace('/0/', '/' + encodeURIComponent(groupId) + '/');
        var dates = getDateFiltersFromPageOrUrl();
        var params = new URLSearchParams();
        if (dates.start) params.set('start_date', dates.start);
        if (dates.end) params.set('end_date', dates.end);
        params.set('projection_months', '3');
        return url + (params.toString() ? '?' + params.toString() : '');
    }

    function openModal(accountId){
        var fetchUrl = buildFetchUrl(accountId);

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

    function resetForecastTable(){
        var head = document.getElementById('groupForecastTableHead');
        var body = document.getElementById('groupForecastTableBody');
        if (head) head.innerHTML = '';
        if (body) body.innerHTML = '';
    }

    function renderForecastTable(projectionLabels, accounts){
        var head = document.getElementById('groupForecastTableHead');
        var body = document.getElementById('groupForecastTableBody');
        if (!head || !body) return;

        if (!projectionLabels || !projectionLabels.length || !accounts || !accounts.length){
            head.innerHTML = '<tr><th>Forecast</th></tr>';
            body.innerHTML = '<tr><td class="text-muted">No projection data available.</td></tr>';
            return;
        }

        var headerHtml = '<tr><th>Account</th>';
        projectionLabels.forEach(function(label){
            headerHtml += '<th class="text-end">' + label + '</th>';
        });
        headerHtml += '</tr>';
        head.innerHTML = headerHtml;

        var bodyHtml = '';
        accounts.forEach(function(acc){
            bodyHtml += '<tr>';
            bodyHtml += '<td>' + (acc.account_code || '') + ' - ' + (acc.account_name || 'Account') + '</td>';
            projectionLabels.forEach(function(_, idx){
                var projectedValue = (acc.projected && acc.projected.length > idx) ? acc.projected[idx] : 0;
                bodyHtml += '<td class="text-end">' + fmt(projectedValue) + '</td>';
            });
            bodyHtml += '</tr>';
        });
        body.innerHTML = bodyHtml;
    }

    function renderForecastChart(labels, accounts){
        var canvas = document.getElementById('groupForecastChart');
        if (!canvas) return;

        var datasets = [];
        var historyLength = 0;
        if (accounts && accounts.length && accounts[0].historical){
            historyLength = accounts[0].historical.length;
        }

        accounts.forEach(function(acc, index){
            var historical = acc.historical || [];
            var projected = acc.projected || [];
            var lineColor = colorByIndex(index, 1);
            var fillColor = colorByIndex(index, 0.15);

            datasets.push({
                label: (acc.account_name || 'Account') + ' (Actual)',
                data: historical.concat(Array(projected.length).fill(null)),
                borderColor: lineColor,
                backgroundColor: fillColor,
                borderWidth: 2,
                tension: 0.25,
                spanGaps: false,
                pointRadius: 3
            });

            var projectionData = Array(Math.max(historyLength - 1, 0)).fill(null);
            if (historical.length){
                projectionData.push(historical[historical.length - 1]);
            }
            projectionData = projectionData.concat(projected);

            datasets.push({
                label: (acc.account_name || 'Account') + ' (Projected)',
                data: projectionData,
                borderColor: lineColor,
                backgroundColor: 'transparent',
                borderDash: [6, 6],
                borderWidth: 2,
                tension: 0.25,
                spanGaps: true,
                pointRadius: 2
            });
        });

        if (groupForecastChartInstance){
            groupForecastChartInstance.destroy();
        }

        groupForecastChartInstance = new Chart(canvas.getContext('2d'), {
            type: 'line',
            data: {
                labels: labels,
                datasets: datasets
            },
            options: {
                responsive: true,
                maintainAspectRatio: true,
                interaction: {
                    mode: 'nearest',
                    intersect: false
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        title: {
                            display: true,
                            text: 'Monthly Net Movement (Debit - Credit)'
                        }
                    },
                    x: {
                        title: {
                            display: true,
                            text: 'Month'
                        }
                    }
                },
                plugins: {
                    legend: {
                        position: 'bottom'
                    }
                }
            }
        });
    }

    function openGroupForecastModal(groupId, groupName){
        var modalEl = document.getElementById('groupForecastModal');
        var titleEl = document.getElementById('groupForecastModalLabel');
        var statusEl = document.getElementById('groupForecastStatus');
        if (!modalEl || !titleEl || !statusEl) return;

        titleEl.textContent = 'Account Forecast - ' + (groupName || 'Group');
        statusEl.textContent = 'Loading forecast data...';
        resetForecastTable();

        var bs = bootstrap.Modal.getOrCreateInstance(modalEl);
        bs.show();

        fetch(buildGroupForecastUrl(groupId), { headers: { 'X-Requested-With': 'XMLHttpRequest' }})
        .then(function(r){ return r.json(); })
        .then(function(data){
            if (!data || !data.success){
                statusEl.textContent = (data && data.error) ? data.error : 'Failed to load forecast data.';
                if (groupForecastChartInstance){
                    groupForecastChartInstance.destroy();
                    groupForecastChartInstance = null;
                }
                resetForecastTable();
                return;
            }

            if (!data.has_history || !data.labels || !data.labels.length){
                statusEl.textContent = 'No transaction history found for the selected date range.';
                if (groupForecastChartInstance){
                    groupForecastChartInstance.destroy();
                    groupForecastChartInstance = null;
                }
                renderForecastTable(data.projection_labels || [], data.accounts || []);
                return;
            }

            renderForecastChart(data.labels, data.accounts || []);
            renderForecastTable(data.projection_labels || [], data.accounts || []);

            var accountCount = (data.accounts || []).length;
            statusEl.textContent = 'Loaded ' + accountCount + ' account(s). Forecast horizon: ' + (data.projection_months || 0) + ' month(s).';
        })
        .catch(function(err){
            console.error(err);
            statusEl.textContent = 'Failed to load forecast data.';
            resetForecastTable();
        });
    }

    var exportForecastBtn = document.getElementById('exportGroupForecastPngBtn');
    if (exportForecastBtn){
        exportForecastBtn.addEventListener('click', function(){
            if (!groupForecastChartInstance){
                alert('No graph available to export yet.');
                return;
            }

            var titleEl = document.getElementById('groupForecastModalLabel');
            var groupName = titleEl ? titleEl.textContent.replace('Account Forecast - ', '').trim() : 'group-forecast';
            var safeName = (groupName || 'group-forecast').replace(/[^a-zA-Z0-9-_]+/g, '_');

            var link = document.createElement('a');
            link.href = groupForecastChartInstance.toBase64Image('image/png', 1);
            link.download = safeName + '_forecast.png';
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
        });
    }

    // attach click handler (delegated in case rows are re-rendered)
    document.addEventListener('click', function(e){
        var forecastBtn = e.target.closest('.group-forecast-btn');
        if (forecastBtn){
            var groupId = forecastBtn.getAttribute('data-group-id');
            var groupName = forecastBtn.getAttribute('data-group-name');
            if (groupId) openGroupForecastModal(groupId, groupName);
            return;
        }

        var row = e.target.closest('.ledger-row');
        if (!row) return;
        row.style.cursor = 'pointer';
        var accountId = row.getAttribute('data-account-id');
        if (accountId) openModal(accountId);
    });
});