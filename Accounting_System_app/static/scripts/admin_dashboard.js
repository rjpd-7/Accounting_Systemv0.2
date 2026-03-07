/**
 * Admin Dashboard
 * Handles section filtering and student search functionality
 */

/**
 * Apply Section and Student Search Filters
 */
function applySectionFilter() {
    const sectionFilter = document.getElementById('section_filter');
    const studentRows = document.querySelectorAll('tr[data-section-id]');
    const noFilterMatchRow = document.getElementById('noFilterMatchRow');
    
    if (!sectionFilter || studentRows.length === 0) return;

    const selectedValue = sectionFilter.value;
    const searchTerm = (document.getElementById('student_search')?.value || '').toLowerCase().trim();
    let visibleCount = 0;

    studentRows.forEach(row => {
        const rowSection = row.getAttribute('data-section-id');
        const studentName = row.getAttribute('data-student-name') || '';
        const username = row.getAttribute('data-username') || '';

        // Check section filter
        const sectionMatch = !selectedValue || rowSection === selectedValue;
        
        // Check search filter
        const searchMatch = !searchTerm || 
                           studentName.includes(searchTerm) || 
                           username.includes(searchTerm);

        // Show row only if both filters match
        const isMatch = sectionMatch && searchMatch;
        row.style.display = isMatch ? '' : 'none';
        if (isMatch) visibleCount += 1;
    });

    if (noFilterMatchRow) {
        noFilterMatchRow.style.display = visibleCount === 0 ? '' : 'none';
    }
}

/**
 * Initialize Section Filter
 */
function initSectionFilter() {
    const sectionFilter = document.getElementById('section_filter');
    if (sectionFilter) {
        sectionFilter.addEventListener('change', applySectionFilter);
        applySectionFilter(); // Apply on page load
    }
}

/**
 * Initialize Student Search
 */
function initStudentSearch() {
    const studentSearchInput = document.getElementById('student_search');
    if (studentSearchInput) {
        studentSearchInput.addEventListener('input', applySectionFilter);
    }
}

// Initialize all dashboard functionality when DOM is ready
document.addEventListener('DOMContentLoaded', function() {
    initSectionFilter();
    initStudentSearch();
});
