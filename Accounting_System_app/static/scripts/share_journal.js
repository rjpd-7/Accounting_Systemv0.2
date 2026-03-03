function fullName(collab) {
    const combined = `${collab.first_name || ''} ${collab.last_name || ''}`.trim();
    return combined || collab.username;
}

function renderCollaboratorCheckboxes(container, collaborators, prefix) {
    container.innerHTML = '';

    if (!collaborators.length) {
        container.innerHTML = '<div class="text-muted">No students available in your section.</div>';
        return;
    }

    collaborators.forEach((collab, index) => {
        const wrapper = document.createElement('div');
        wrapper.className = 'form-check mb-1';

        const input = document.createElement('input');
        input.className = 'form-check-input';
        input.type = 'checkbox';
        input.value = collab.id;
        input.id = `${prefix}_collab_${collab.id}_${index}`;

        const label = document.createElement('label');
        label.className = 'form-check-label';
        label.setAttribute('for', input.id);
        label.textContent = fullName(collab);

        wrapper.appendChild(input);
        wrapper.appendChild(label);
        container.appendChild(wrapper);
    });
}

function getSelectedCollaboratorIds(container) {
    return Array.from(container.querySelectorAll('input.form-check-input:checked')).map(el => el.value);
}

function setAllCollaborators(container, checked) {
    container.querySelectorAll('input.form-check-input').forEach(el => {
        el.checked = checked;
    });
}

function loadCollaboratorsForModal(config) {
    console.log('Loading collaborators for journal:', config.journalId, 'isDraft:', config.isDraft);
    fetch(`/get_available_collaborators/${config.journalId}/${config.isDraft}/`)
        .then(response => response.json())
        .then(data => {
            console.log('API Response:', data);
            const collaborators = data.collaborators || [];
            const sectionName = data.sharer_section_name || 'Not assigned';
            const sectionId = data.sharer_section_id;

            console.log('Section ID:', sectionId, 'Section Name:', sectionName, 'Collaborators count:', collaborators.length);

            config.sectionText.textContent = sectionName || '(No section assigned)';
            renderCollaboratorCheckboxes(config.listContainer, collaborators, config.idPrefix);
            config.shareButton.setAttribute('data-journal-id', config.journalId);
        })
        .catch(error => {
            console.error('Error fetching collaborators:', error);
            config.sectionText.textContent = 'Error loading section';
            config.listContainer.innerHTML = '<div class="alert alert-danger">Error loading collaborators: ' + error.message + '</div>';
        });
}

function submitCollaborators(endpoint, journalId, listContainer) {
    const selectedIds = getSelectedCollaboratorIds(listContainer);

    if (!selectedIds.length) {
        alert('Please select at least one collaborator.');
        return;
    }

    fetch(endpoint.replace('__ID__', journalId), {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': document.querySelector('form input[name="csrfmiddlewaretoken"]').value || getCookie('csrftoken')
        },
        body: JSON.stringify({ collaborator_ids: selectedIds })
    })
    .then(response => {
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        return response.json();
    })
    .then(data => {
        if (data.success) {
            alert(data.message || 'Collaborators added successfully.');
            location.reload();
        } else {
            alert(data.message || 'Error adding collaborators');
        }
    })
    .catch(error => {
        console.error('Error:', error);
        alert('Error adding collaborators: ' + error.message);
    });
}

// Handle Share Draft Modal
document.getElementById('ShareDraftModal').addEventListener('show.bs.modal', function(event) {
    const button = event.relatedTarget;
    const journalId = button.getAttribute('data-id');
    const isDraft = button.getAttribute('data-is-draft');
    const sectionText = document.getElementById('share_draft_section_text');
    const listContainer = document.getElementById('share_draft_collaborator_list');
    const shareButton = document.getElementById('share_draft_btn');

    loadCollaboratorsForModal({
        journalId,
        isDraft,
        sectionText,
        listContainer,
        shareButton,
        idPrefix: 'draft'
    });
});

document.getElementById('select_all_draft_collaborators').addEventListener('click', function() {
    setAllCollaborators(document.getElementById('share_draft_collaborator_list'), true);
});

document.getElementById('clear_all_draft_collaborators').addEventListener('click', function() {
    setAllCollaborators(document.getElementById('share_draft_collaborator_list'), false);
});

// Handle Share Button Click for Draft Journal
document.getElementById('share_draft_btn').addEventListener('click', function() {
    const journalId = this.getAttribute('data-journal-id');
    const listContainer = document.getElementById('share_draft_collaborator_list');
    submitCollaborators('/add_collaborator_draft/__ID__/', journalId, listContainer);
});

// Handle Share Modal
document.getElementById('ShareModal').addEventListener('show.bs.modal', function(event) {
    const button = event.relatedTarget;
    const journalId = button.getAttribute('data-id');
    const isDraft = button.getAttribute('data-is-draft');
    const sectionText = document.getElementById('share_section_text');
    const listContainer = document.getElementById('share_collaborator_list');
    const shareButton = document.getElementById('share_btn');

    loadCollaboratorsForModal({
        journalId,
        isDraft,
        sectionText,
        listContainer,
        shareButton,
        idPrefix: 'approved'
    });
});

document.getElementById('select_all_collaborators').addEventListener('click', function() {
    setAllCollaborators(document.getElementById('share_collaborator_list'), true);
});

document.getElementById('clear_all_collaborators').addEventListener('click', function() {
    setAllCollaborators(document.getElementById('share_collaborator_list'), false);
});

// Handle Share Button Click for Approved Journal
document.getElementById('share_btn').addEventListener('click', function() {
    const journalId = this.getAttribute('data-journal-id');
    const listContainer = document.getElementById('share_collaborator_list');
    submitCollaborators('/add_collaborator/__ID__/', journalId, listContainer);
});

// Utility function to get CSRF token
function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}
