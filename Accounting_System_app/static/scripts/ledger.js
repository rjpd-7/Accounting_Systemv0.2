document.addEventListener('DOMContentLoaded', function () {
    function fmt(v){ return (v===null||v===undefined) ? '0.00' : parseFloat(v).toFixed(2); }
    var groupForecastChartInstance = null;

    function pad2(n){ return String(n).padStart(2, '0'); }

    function monthKey(dateStr){
        if (!dateStr) return null;
        var d = new Date(dateStr);
        if (isNaN(d.getTime())) return null;
        return d.getFullYear() + '-' + pad2(d.getMonth() + 1);
    }

    function parseMonthKey(key){
        var p = (key || '').split('-');
        if (p.length !== 2) return null;
        var y = parseInt(p[0], 10);
        var m = parseInt(p[1], 10);
        if (isNaN(y) || isNaN(m)) return null;
        return { year: y, month: m };
    }

    function nextMonthKey(key){
        var parsed = parseMonthKey(key);
        if (!parsed) return null;
        var y = parsed.year;
        var m = parsed.month + 1;
        if (m > 12){
            m = 1;
            y += 1;
        }
        return y + '-' + pad2(m);
    }

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

    function linearRegressionForecast(values, futurePoints){
        var n = values.length;
        if (!n) return [];
        if (n === 1){
            return Array(futurePoints).fill(values[0]);
        }

        var sumX = 0, sumY = 0, sumXY = 0, sumXX = 0;
        for (var i = 0; i < n; i++){
            sumX += i;
            sumY += values[i];
            sumXY += i * values[i];
            sumXX += i * i;
        }

        var denom = (n * sumXX) - (sumX * sumX);
        var slope = denom === 0 ? 0 : ((n * sumXY) - (sumX * sumY)) / denom;
        var intercept = (sumY - (slope * sumX)) / n;

        var result = [];
        for (var j = 0; j < futurePoints; j++){
            var x = n + j;
            result.push((slope * x) + intercept);
        }
        return result;
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

    function getGroupAccounts(groupId){
        var rows = document.querySelectorAll('.ledger-row[data-group-id="' + groupId + '"]');
        var seen = {};
        var accounts = [];

        rows.forEach(function(row){
            var id = row.getAttribute('data-account-id');
            var name = row.getAttribute('data-account-name') || 'Account';
            if (!id || seen[id]) return;
            seen[id] = true;
            accounts.push({ id: id, name: name });
        });

        return accounts;
    }

    function aggregateMonthlyNet(transactions){
        var monthly = {};
        (transactions || []).forEach(function(tx){
            var key = monthKey(tx.entry_date);
            if (!key) return;
            if (!(key in monthly)) monthly[key] = 0;
            monthly[key] += (parseFloat(tx.debit || 0) - parseFloat(tx.credit || 0));
        });
        return monthly;
    }

    function openGroupForecastModal(groupId, groupName){
        var modalEl = document.getElementById('groupForecastModal');
        var titleEl = document.getElementById('groupForecastModalLabel');
        var statusEl = document.getElementById('groupForecastStatus');
        var canvas = document.getElementById('groupForecastChart');
        if (!modalEl || !canvas || !titleEl || !statusEl) return;

        titleEl.textContent = 'Account Forecast - ' + (groupName || 'Group');
        statusEl.textContent = 'Loading account histories...';

        var bs = bootstrap.Modal.getOrCreateInstance(modalEl);
        bs.show();

        var accounts = getGroupAccounts(groupId);
        if (!accounts.length){
            statusEl.textContent = 'No accounts found in this group.';
            if (groupForecastChartInstance){
                groupForecastChartInstance.destroy();
                groupForecastChartInstance = null;
            }
            return;
        }

        Promise.all(accounts.map(function(acc){
            return fetch(buildFetchUrl(acc.id), { headers: { 'X-Requested-With': 'XMLHttpRequest' }})
                .then(function(r){ return r.json(); })
                .then(function(data){
                    return {
                        id: acc.id,
                        name: acc.name,
                        ok: !!(data && data.success),
                        transactions: (data && data.success) ? (data.transactions || []) : []
                    };
                })
                .catch(function(){
                    return { id: acc.id, name: acc.name, ok: false, transactions: [] };
                });
        }))
        .then(function(results){
            var monthlyByAccount = {};
            var allMonthsSet = {};
            var successful = 0;

            results.forEach(function(r){
                if (r.ok) successful += 1;
                var monthly = aggregateMonthlyNet(r.transactions);
                monthlyByAccount[r.id] = { name: r.name, monthly: monthly };
                Object.keys(monthly).forEach(function(m){ allMonthsSet[m] = true; });
            });

            var historyMonths = Object.keys(allMonthsSet).sort();
            if (!historyMonths.length){
                statusEl.textContent = 'No transaction history found for the selected date range.';
                if (groupForecastChartInstance){
                    groupForecastChartInstance.destroy();
                    groupForecastChartInstance = null;
                }
                return;
            }

            var projectionSteps = 3;
            var futureMonths = [];
            var lastMonth = historyMonths[historyMonths.length - 1];
            for (var i = 0; i < projectionSteps; i++){
                lastMonth = nextMonthKey(lastMonth);
                if (!lastMonth) break;
                futureMonths.push(lastMonth);
            }

            var labels = historyMonths.concat(futureMonths);
            var datasets = [];
            var colorIndex = 0;

            Object.keys(monthlyByAccount).forEach(function(accountId){
                var accountData = monthlyByAccount[accountId];
                var historicalSeries = historyMonths.map(function(m){
                    return parseFloat((accountData.monthly[m] || 0).toFixed(2));
                });

                var forecastValues = linearRegressionForecast(historicalSeries, futureMonths.length).map(function(v){
                    return parseFloat(v.toFixed(2));
                });

                var lineColor = colorByIndex(colorIndex, 1);
                var fillColor = colorByIndex(colorIndex, 0.15);
                colorIndex += 1;

                datasets.push({
                    label: accountData.name + ' (Actual)',
                    data: historicalSeries.concat(Array(futureMonths.length).fill(null)),
                    borderColor: lineColor,
                    backgroundColor: fillColor,
                    borderWidth: 2,
                    tension: 0.25,
                    spanGaps: false,
                    pointRadius: 3
                });

                var projectionData = Array(Math.max(historyMonths.length - 1, 0)).fill(null);
                projectionData.push(historicalSeries[historicalSeries.length - 1]);
                projectionData = projectionData.concat(forecastValues);

                datasets.push({
                    label: accountData.name + ' (Projected)',
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

            statusEl.textContent = 'Loaded ' + successful + ' of ' + accounts.length + ' accounts. Forecast horizon: ' + futureMonths.length + ' month(s).';
        })
        .catch(function(err){
            console.error(err);
            statusEl.textContent = 'Failed to load forecast data.';
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