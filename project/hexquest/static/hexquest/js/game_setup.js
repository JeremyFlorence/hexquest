// Configuration will be provided by inline script in the template
// const gameId = ...;
// const currentUsername = ...;
// let lastChatId = ...;

document.addEventListener('DOMContentLoaded', () => {
    const chatMessages = document.getElementById('chat-messages');
    const nationList = document.getElementById('nation-list');
    const chatForm = document.getElementById('chat-form');
    const chatInput = document.getElementById('chat-input');
    const settingsForm = document.querySelector('form[action="update_settings"]') || document.querySelector('input[name="action"][value="update_settings"]')?.form;
    const inviteForm = document.querySelector('.invite-form');
    const nationSettingsForm = document.querySelector('input[name="action"][value="update_nation"]')?.form;
    const gameNameDisplay = document.querySelector('h1');
    const settingsReadonly = document.querySelector('.settings-readonly');

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
            try {
                const response = await fetch("", {
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
                    if (data.message) alert(data.message);
                }
            } catch (err) {
                console.error("Form submission failed", err);
            }
        };
    }

    handleFormSubmit(settingsForm);
    handleFormSubmit(inviteForm);
    handleFormSubmit(nationSettingsForm);

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

        // Update nations
        if (data.nations && nationList) {
            nationList.innerHTML = data.nations.map(n => `
                <li class="nation-item">
                    <div class="color-swatch" data-color="${n.color}"></div>
                    <div>
                        <strong>${n.player}</strong>
                        <span class="muted">(${n.name})</span>
                    </div>
                </li>
            `).join('');
            applyColors();
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
                    if (input && !modifiedInputs.has(field)) input.value = data.settings[field];
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
