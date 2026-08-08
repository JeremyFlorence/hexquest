// Configuration will be provided by inline script in the template
// const gameId = ...;
// const currentUsername = ...;
// let lastChatId = ...;

document.addEventListener('DOMContentLoaded', () => {
    const chatMessages = document.getElementById('chat-messages');
    const nationList = document.getElementById('nation-list');
    const chatForm = document.getElementById('chat-form');
    const chatInput = document.getElementById('chat-input');
    const settingsForm = document.querySelector('input[name="action"][value="update_settings"]')?.form;
    const inviteForm = document.querySelector('input[name="action"][value="invite_player"]')?.form;
    const nationSettingsForm = document.querySelector('input[name="action"][value="update_nation"]')?.form;
    const gameNameDisplay = document.querySelector('h1');
    const settingsReadonly = document.querySelector('.settings-readonly');
    const inviteSelect = document.getElementById('invite-username-select');
    const inviteButton = document.getElementById('invite-button');
    let statusTimeouts = new Map();
    function showStatus(message, form, isError = false) {
        const statusMsg = form.querySelector('.status-message');
        if (!statusMsg) return;

        // Clear existing timeouts for this message element
        if (statusTimeouts.has(statusMsg)) {
            const timeouts = statusTimeouts.get(statusMsg);
            timeouts.forEach(clearTimeout);
        }
        
        statusMsg.textContent = message;
        statusMsg.style.display = statusMsg.classList.contains('block') ? 'block' : 'inline';
        statusMsg.style.opacity = '1';
        statusMsg.style.color = isError ? '#ef4444' : '#10b981';
        
        // Remove any existing fade-out class to reset
        statusMsg.classList.remove('fade-out');
        
        // Trigger reflow to ensure transition can be applied
        void statusMsg.offsetWidth;
        
        const t1 = setTimeout(() => {
            statusMsg.classList.add('fade-out');
            const t2 = setTimeout(() => {
                statusMsg.style.display = 'none';
                statusTimeouts.delete(statusMsg);
            }, 2000); // Wait for fade transition to finish
            statusTimeouts.set(statusMsg, [t1, t2]);
        }, 2000);
        statusTimeouts.set(statusMsg, [t1]);
    }

    // Track modified form inputs to prevent polling from overwriting unsaved changes
    const modifiedInputs = new Set();

    // Apply colors to swatches
    function applyColors() {
        document.querySelectorAll('.color-swatch[data-color]').forEach(el => {
            el.style.backgroundColor = el.getAttribute('data-color');
        });
    }
    applyColors();

    // Track when settings form inputs are modified
    if (settingsForm) {
        const inputs = settingsForm.querySelectorAll('input[type="text"], input[type="number"]');
        inputs.forEach(input => {
            input.addEventListener('input', () => {
                modifiedInputs.add(input.id);
            });
        });
    }

    async function handleFormSubmit(form, onSuccess) {
        if (!form) return;
        form.onsubmit = async (e) => {
            e.preventDefault();
            const formData = new FormData(form);
            const targetUrl = form.getAttribute('action') || window.location.pathname;
            try {
                const response = await fetch(targetUrl, {
                    method: 'POST',
                    body: formData,
                    headers: {
                        'X-Requested-With': 'XMLHttpRequest'
                    }
                });
                if (response.ok) {
                    if (onSuccess) onSuccess(form);
                    // Clear modified inputs after successful save
                    if (form === settingsForm) {
                        modifiedInputs.clear();
                    }
                } else {
                    const data = await response.json();
                    if (data.message) showStatus(data.message, form, true);
                }
            } catch (err) {
                console.error("Form submission failed", err);
                showStatus("An error occurred. Please try again.", form, true);
            }
        };
    }

    handleFormSubmit(settingsForm, (form) => showStatus("Settings saved!", form));
    handleFormSubmit(inviteForm, (form) => {
        const username = form.querySelector('select[name="username"]')?.value;
        showStatus(`Invite sent to ${username}!`, form);
    });
    handleFormSubmit(nationSettingsForm, (form) => showStatus("Nation settings updated!", form));

    function updateInviteButtonState() {
        if (!inviteSelect || !inviteButton) return;
        const selectedOption = inviteSelect.options[inviteSelect.selectedIndex];
        inviteButton.disabled = selectedOption?.disabled || false;
    }

    if (inviteSelect) {
        inviteSelect.addEventListener('change', updateInviteButtonState);
        // Initial state
        updateInviteButtonState();
    }

    // Handle cancel invite buttons
    document.addEventListener('click', async (e) => {
        if (e.target.classList.contains('cancel-invite-btn')) {
            const inviteId = e.target.getAttribute('data-invite-id');
            const url = `/notifications/${inviteId}/cancel/`;
            try {
                const response = await fetch(url, {
                    method: 'POST',
                    headers: {
                        'X-Requested-With': 'XMLHttpRequest',
                        'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value
                    }
                });
                if (response.ok) {
                    // Success handled via WebSocket broadcast
                } else {
                    console.error('Failed to cancel invite');
                }
            } catch (err) {
                console.error('Failed to cancel invite', err);
            }
        }
        if (e.target.classList.contains('kick-player-btn')) {
            const playerId = e.target.getAttribute('data-player-id');
            const url = `/games/${gameId}/kick/${playerId}/`;
            if (!confirm('Are you sure you want to kick this player from the lobby?')) return;
            try {
                const response = await fetch(url, {
                    method: 'POST',
                    headers: {
                        'X-Requested-With': 'XMLHttpRequest',
                        'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value
                    }
                });
                if (response.ok) {
                    // Success handled via WebSocket broadcast
                } else {
                    console.error('Failed to kick player');
                }
            } catch (err) {
                console.error('Failed to kick player', err);
            }
        }
    });

    // --- Real-time chat via WebSocket (Django Channels) ---
    let chatSocket = null;

    function appendChatMessage(msg) {
        if (!chatMessages) return;
        const msgDiv = document.createElement('div');
        msgDiv.className = `chat-message ${msg.user === currentUsername ? 'own' : ''}`;
        msgDiv.innerHTML = `
            <div class="chat-user">${msg.user}<span class="chat-time">${msg.created_at}</span></div>
            <div class="chat-text">${msg.text}</div>
        `;
        chatMessages.appendChild(msgDiv);
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }

    function connectChatSocket() {
        if (typeof chatWsUrl === 'undefined') return;
        chatSocket = new WebSocket(chatWsUrl);

        chatSocket.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                if (data.type === 'chat_message' && data.message) {
                    appendChatMessage(data.message);
                }
            } catch (err) {
                console.error('Failed to parse chat message', err);
            }
        };

        chatSocket.onclose = () => {
            // Attempt to reconnect after a short delay so chat stays live.
            setTimeout(connectChatSocket, 2000);
        };

        chatSocket.onerror = (err) => {
            console.error('Chat socket error', err);
            chatSocket.close();
        };
    }
    connectChatSocket();

    if (chatForm) {
        chatForm.addEventListener('submit', (e) => {
            e.preventDefault();
            const text = chatInput.value.trim();
            if (!text) return;
            if (chatSocket && chatSocket.readyState === WebSocket.OPEN) {
                chatSocket.send(JSON.stringify({ text }));
                chatInput.value = '';
            }
        });
    }

    if (chatMessages) {
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }

    function applySetupUpdate(data) {
        if (!data) return;

        if (data.game_active) {
            window.location.href = gameMapUrl;
            return;
        }

        // Update nations & invitations
        if (nationList) {
            let html = '';
            if (data.nations) {
                html += data.nations.map(n => `
                    <li class="nation-item" data-player-id="${n.player_id}">
                        <div class="color-swatch" data-color="${n.color}"></div>
                        <div style="display: flex; justify-content: space-between; align-items: center; flex: 1;">
                            <div>
                                <strong>${n.player}</strong>
                                <span class="muted">(${n.name})</span>
                            </div>
                            ${data.creator === currentUsername && n.player !== data.creator ? `
                                <button type="button" class="danger small-button kick-player-btn" data-player-id="${n.player_id}">Kick</button>
                            ` : ''}
                        </div>
                    </li>
                `).join('');
            }
            if (data.invitations) {
                html += data.invitations.map(i => `
                    <li class="nation-item invited" data-invite-id="${i.id}">
                        <div class="color-swatch" style="background-color: #475569; border: 1px dashed #94a3b8;"></div>
                        <div style="display: flex; justify-content: space-between; align-items: center; flex: 1;">
                            <div>
                                <strong>${i.player}</strong>
                                <span class="muted">(invited)</span>
                            </div>
                            ${data.creator === currentUsername ? `
                                <button type="button" class="danger small-button cancel-invite-btn" data-invite-id="${i.id}">Cancel Invite</button>
                            ` : ''}
                        </div>
                    </li>
                `).join('');
            }
            nationList.innerHTML = html;
            applyColors();
        }

        // Update invite dropdown
        if (data.unavailable_players && inviteSelect) {
            const unavailable = new Set(data.unavailable_players);
            Array.from(inviteSelect.options).forEach(option => {
                const isUnavailable = unavailable.has(option.value);
                option.disabled = isUnavailable;
                // Add/remove label if not already there
                const baseName = option.value;
                if (isUnavailable) {
                    option.textContent = `${baseName} (already invited/joined)`;
                } else {
                    option.textContent = baseName;
                }
            });
            updateInviteButtonState();
        }

        // Update settings
        if (data.settings) {
            if (gameNameDisplay) {
                gameNameDisplay.textContent = `Game Setup: ${data.settings.name}`;
            }

            if (settingsForm) {
                const fields = ['name', 'width', 'height', 'seed', 'turn_timer',
                                'starting_gold', 'starting_food', 'starting_settlers'];
                fields.forEach(field => {
                    const input = settingsForm.querySelector(`#${field}`);
                    if (input && !modifiedInputs.has(field)) {
                        const newValue = String(data.settings[field]);
                        if (input.value !== newValue) {
                            input.value = newValue;
                        }
                    }
                });
            }

            if (settingsReadonly) {
                settingsReadonly.innerHTML = `
                    <p><strong>Game Name:</strong> ${data.settings.name}</p>
                    <p><strong>Map Size:</strong> ${data.settings.width} x ${data.settings.height}</p>
                    <p><strong>Map Seed:</strong> ${data.settings.seed}</p>
                    <p><strong>Turn Timer:</strong> ${data.settings.turn_timer} seconds</p>
                    <p><strong>Starting Gold:</strong> ${data.settings.starting_gold}</p>
                    <p><strong>Starting Food:</strong> ${data.settings.starting_food}</p>
                    <p><strong>Starting Settlers:</strong> ${data.settings.starting_settlers}</p>
                    <p class="muted">Only the game creator can change settings.</p>
                `;
            }
        }
    }

    // --- Real-time setup lobby via WebSocket (Django Channels) ---
    let setupSocket = null;

    function connectSetupSocket() {
        if (typeof setupWsUrl === 'undefined') return;
        setupSocket = new WebSocket(setupWsUrl);

        setupSocket.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                if (data.type === 'setup_update') {
                    applySetupUpdate(data.payload);
                } else if (data.type === 'setup_abandoned') {
                    window.location.href = '/?abandoned=1';
                } else if (data.type === 'setup_kicked') {
                    if (data.player_id === currentUserId) {
                        window.location.href = '/?kicked=1';
                    }
                }
            } catch (err) {
                console.error('Failed to parse setup update', err);
            }
        };

        setupSocket.onclose = () => {
            // Attempt to reconnect after a short delay so the lobby stays live.
            setTimeout(connectSetupSocket, 2000);
        };

        setupSocket.onerror = (err) => {
            console.error('Setup socket error', err);
            setupSocket.close();
        };
    }
    connectSetupSocket();
});
