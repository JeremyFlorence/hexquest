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
                    fetchUpdates();
                } else {
                    const data = await response.json();
                    if (data.message) alert(data.message);
                }
            } catch (err) {
                console.error("Form submission failed", err);
            }
        };
    }

    handleFormSubmit(chatForm, (form) => {
        chatInput.value = '';
    });
    handleFormSubmit(settingsForm);
    handleFormSubmit(inviteForm);
    handleFormSubmit(nationSettingsForm);

    // Scroll chat to bottom

    async function fetchUpdates() {
        try {
            const response = await fetch(`updates/?last_chat_id=${lastChatId}`);
            if (response.status === 404) {
                window.location.href = "/?abandoned=1";
                return;
            }
            const data = await response.json();

            if (data.game_active) {
                window.location.href = gameMapUrl;
                return;
            }

            // Update nations
            if (data.nations && nationList) {
                const currentUserId = document.querySelector('input[name="action"][value="update_nation"]')?.form ? true : false;
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
                    const nameInput = settingsForm.querySelector('#name');
                    if (nameInput && !modifiedInputs.has('name')) nameInput.value = data.settings.name;
                    
                    const widthInput = settingsForm.querySelector('#width');
                    if (widthInput && !modifiedInputs.has('width')) widthInput.value = data.settings.width;
                    
                    const heightInput = settingsForm.querySelector('#height');
                    if (heightInput && !modifiedInputs.has('height')) heightInput.value = data.settings.height;
                    
                    const seedInput = settingsForm.querySelector('#seed');
                    if (seedInput && !modifiedInputs.has('seed')) seedInput.value = data.settings.seed;
                    
                    const timerInput = settingsForm.querySelector('#turn_timer');
                    if (timerInput && !modifiedInputs.has('turn_timer')) timerInput.value = data.settings.turn_timer;
                    
                    const goldInput = settingsForm.querySelector('#starting_gold');
                    if (goldInput && !modifiedInputs.has('starting_gold')) goldInput.value = data.settings.starting_gold;
                    
                    const foodInput = settingsForm.querySelector('#starting_food');
                    if (foodInput && !modifiedInputs.has('starting_food')) foodInput.value = data.settings.starting_food;
                    
                    const settlersInput = settingsForm.querySelector('#starting_settlers');
                    if (settlersInput && !modifiedInputs.has('starting_settlers')) settlersInput.value = data.settings.starting_settlers;
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

            // Update chat
            if (data.messages && data.messages.length > 0 && chatMessages) {
                data.messages.forEach(msg => {
                    const msgDiv = document.createElement('div');
                    msgDiv.className = `chat-message ${msg.user === currentUsername ? 'own' : ''}`;
                    msgDiv.innerHTML = `
                        <div class="chat-user">${msg.user}<span class="chat-time">${msg.created_at}</span></div>
                        <div class="chat-text">${msg.text}</div>
                    `;
                    chatMessages.appendChild(msgDiv);
                    lastChatId = Math.max(lastChatId, msg.id);
                });
                chatMessages.scrollTop = chatMessages.scrollHeight;
            }
        } catch (err) {
            console.error("Failed to fetch updates", err);
        }
    }

    // Poll for updates every 3 seconds
    setInterval(fetchUpdates, 3000);
});
