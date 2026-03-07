document.addEventListener('DOMContentLoaded', function () {
  const ledgerFilter = document.getElementById('ledgerGroupFilter');
  const ledgerGroupSections = document.querySelectorAll('.ledger-group-section');
  const grandTotalSection = document.getElementById('ledger-grand-total');

  function filterLedger(groupId) {
    ledgerGroupSections.forEach(section => {
      const sectionGroupId = section.dataset.groupId;
      if (!groupId || sectionGroupId === groupId || sectionGroupId === 'null' || sectionGroupId === 'None') {
        section.style.display = '';
      } else {
        section.style.display = 'none';
      }
    });

    // Hide Grand Total when filtering by specific group, show when viewing all groups
    if (grandTotalSection) {
      if (groupId) {
        grandTotalSection.style.display = 'none';
      } else {
        grandTotalSection.style.display = '';
      }
    }
  }

  if (ledgerFilter) {
    ledgerFilter.addEventListener('change', function () {
      filterLedger(this.value);
    });
    // Apply initial filter to show all groups
    filterLedger(ledgerFilter.value || '');
  }
});