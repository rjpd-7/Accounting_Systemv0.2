// Handle Share Draft Modal
document.getElementById('ShareDraftModal').addEventListener('show.bs.modal', function(event) {
    const button = event.relatedTarget;
    const journalId = button.getAttribute('data-id');
    const isDraft = button.getAttribute('data-is-draft');
    
    // Fetch available collaborators
    fetch(`/get_available_collaborators/${journalId}/${isDraft}/`)
        .then(response => response.json())
        .then(data => {
            const select = document.getElementById('share_draft_collaborator');
            select.innerHTML = '<option value="">-- Select a student --</option>';
            
            data.collaborators.forEach(collab => {
                const option = document.createElement('option');
                option.value = collab.id;
                option.textContent = collab.first_name + ' ' + collab.last_name;
                select.appendChild(option);
            });
            
            // Store journal ID for use in Share button
            document.getElementById('share_draft_btn').setAttribute('data-journal-id', journalId);
        })
        .catch(error => console.error('Error fetching collaborators:', error));
});

// Handle Share Button Click for Draft Journal
document.getElementById('share_draft_btn').addEventListener('click', function() {
    const journalId = this.getAttribute('data-journal-id');
    const collaboratorId = document.getElementById('share_draft_collaborator').value;
    
    if (!collaboratorId) {
        alert('Please select a collaborator');
        return;
    }
    
    // Send request to add collaborator
    fetch(`/add_collaborator_draft/${journalId}/`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': document.querySelector('form input[name="csrfmiddlewaretoken"]').value || getCookie('csrftoken')
        },
        body: JSON.stringify({ collaborator_id: collaboratorId })
    })
    .then(response => {
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        return response.json();
    })
    .then(data => {
        if (data.success) {
            alert('Collaborator added successfully');
            // Close modal and refresh page
            const modal = bootstrap.Modal.getInstance(document.getElementById('ShareDraftModal'));
            modal.hide();
            location.reload();
        } else {
            alert(data.message || 'Error adding collaborator');
        }
    })
    .catch(error => {
        console.error('Error:', error);
        alert('Error adding collaborator: ' + error.message);
    });
});

// Handle Share Modal
document.getElementById('ShareModal').addEventListener('show.bs.modal', function(event) {
    const button = event.relatedTarget;
    const journalId = button.getAttribute('data-id');
    const isDraft = button.getAttribute('data-is-draft');
    
    // Fetch available collaborators
    fetch(`/get_available_collaborators/${journalId}/${isDraft}/`)
        .then(response => response.json())
        .then(data => {
            const select = document.getElementById('share_collaborator');
            select.innerHTML = '<option value="">-- Select a student --</option>';
            
            data.collaborators.forEach(collab => {
                const option = document.createElement('option');
                option.value = collab.id;
                option.textContent = collab.first_name + ' ' + collab.last_name;
                select.appendChild(option);
            });
            
            // Store journal ID for use in Share button
            document.getElementById('share_btn').setAttribute('data-journal-id', journalId);
        })
        .catch(error => console.error('Error fetching collaborators:', error));
});

// Handle Share Button Click for Approved Journal
document.getElementById('share_btn').addEventListener('click', function() {
    const journalId = this.getAttribute('data-journal-id');
    const collaboratorId = document.getElementById('share_collaborator').value;
    
    if (!collaboratorId) {
        alert('Please select a collaborator');
        return;
    }
    
    // Send request to add collaborator
    fetch(`/add_collaborator/${journalId}/`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': document.querySelector('form input[name="csrfmiddlewaretoken"]').value || getCookie('csrftoken')
        },
        body: JSON.stringify({ collaborator_id: collaboratorId })
    })
    .then(response => {
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        return response.json();
    })
    .then(data => {
        if (data.success) {
            alert('Collaborator added successfully');
            // Close modal and refresh page
            const modal = bootstrap.Modal.getInstance(document.getElementById('ShareModal'));
            modal.hide();
            location.reload();
        } else {
            alert(data.message || 'Error adding collaborator');
        }
    })
    .catch(error => {
        console.error('Error:', error);
        alert('Error adding collaborator: ' + error.message);
    });
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
