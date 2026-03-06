document.addEventListener('DOMContentLoaded', function () {
    const messageModalElement = document.getElementById('messageCollaboratorModal');
    const messageForm = document.getElementById('journal_collaborator_message_form');
    const collaboratorIdInput = document.getElementById('message_collaborator_id');
    const collaboratorNameElement = document.getElementById('message_collaborator_name');
    const subjectInput = document.getElementById('message_collaborator_subject');
    const contentInput = document.getElementById('message_collaborator_content');
    const feedbackContainer = document.getElementById('message_collaborator_feedback');
    const sendButton = document.getElementById('send_collaborator_message_btn');

    if (!messageModalElement || !messageForm) {
        return;
    }

    const messageModal = new bootstrap.Modal(messageModalElement);

    function showFeedback(message, type) {
        if (!feedbackContainer) return;
        feedbackContainer.innerHTML = '<div class="alert alert-' + type + ' py-2 mb-0">' + message + '</div>';
    }

    function clearFeedback() {
        if (!feedbackContainer) return;
        feedbackContainer.innerHTML = '';
    }

    document.addEventListener('click', function (event) {
        const trigger = event.target.closest('.collaborator-message-trigger');
        if (!trigger) return;

        const collaboratorId = trigger.getAttribute('data-collaborator-id');
        const collaboratorName = trigger.getAttribute('data-collaborator-name') || 'Collaborator';
        const journalCode = trigger.getAttribute('data-journal-code') || '';

        collaboratorIdInput.value = collaboratorId || '';
        collaboratorNameElement.textContent = collaboratorName;
        subjectInput.value = journalCode ? 'Journal ' + journalCode + ' Collaboration' : '';
        contentInput.value = '';
        clearFeedback();

        messageModal.show();
    });

    messageForm.addEventListener('submit', function (event) {
        event.preventDefault();

        const recipientId = collaboratorIdInput.value;
        const content = (contentInput.value || '').trim();
        if (!recipientId) {
            showFeedback('No collaborator selected.', 'warning');
            return;
        }
        if (!content) {
            showFeedback('Please enter a message.', 'warning');
            return;
        }

        const formData = new FormData();
        formData.append('recipients', recipientId);
        formData.append('subject', subjectInput.value || '');
        formData.append('content', content);

        const csrfToken = messageForm.querySelector('[name="csrfmiddlewaretoken"]')?.value || '';

        sendButton.disabled = true;
        const previousLabel = sendButton.textContent;
        sendButton.textContent = 'Sending...';

        fetch(window.journalMessagingApiUrls.sendMessage, {
            method: 'POST',
            body: formData,
            headers: {
                'X-Requested-With': 'XMLHttpRequest',
                'X-CSRFToken': csrfToken
            }
        })
            .then(async function (response) {
                let data = {};
                try {
                    data = await response.json();
                } catch (error) {
                    data = { error: 'Unexpected server response.' };
                }

                if (!response.ok) {
                    throw new Error(data.error || data.message || 'Unable to send message.');
                }

                return data;
            })
            .then(function (data) {
                showFeedback(data.message || 'Message sent successfully.', 'success');

                setTimeout(function () {
                    messageModal.hide();
                    clearFeedback();
                    messageForm.reset();
                    collaboratorIdInput.value = '';
                    collaboratorNameElement.textContent = '';
                }, 700);
            })
            .catch(function (error) {
                showFeedback(error.message || 'Error sending message.', 'danger');
            })
            .finally(function () {
                sendButton.disabled = false;
                sendButton.textContent = previousLabel;
            });
    });

    messageModalElement.addEventListener('hidden.bs.modal', function () {
        clearFeedback();
        messageForm.reset();
        collaboratorIdInput.value = '';
        collaboratorNameElement.textContent = '';
    });
});
