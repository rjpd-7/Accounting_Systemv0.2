document.addEventListener('DOMContentLoaded', function () {
  const ledgerFilter = document.getElementById('ledgerGroupFilter');
  const ledgerBody = document.querySelectorAll('.ledger-row'); // NodeList of rows

  function filterLedger(groupId) {
    ledgerBody.forEach(row => {
      const rowGroup = row.dataset.groupId;
      if (!groupId || rowGroup === groupId || rowGroup === 'null') {
        row.style.display = '';
      } else {
        row.style.display = 'none';
      }
    });
  }

  if (ledgerFilter) {
    ledgerFilter.addEventListener('change', function () {
      filterLedger(this.value);
    });
    // optional: apply initial filter
    filterLedger(ledgerFilter.value || '');
  }
});