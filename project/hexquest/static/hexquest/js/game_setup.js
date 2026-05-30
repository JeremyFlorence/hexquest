// Configuration will be provided by inline script in the template
// const gameId = ...;
// const currentUsername = ...;
// let lastChatId = ...;

document.addEventListener('DOMContentLoaded', () => {
    const chatMessages = document.getElementById('chat-messages');
    const nationList = document.getElementById('nation-list');
    const chatForm = document.getElementById('chat-form');
    const chatInput = document.getElementById('chat-input');

    // Apply colors to swatches
    function applyColors() {
        document.querySelectorAll('.color-swatch[data-color]').forEach(el => {
            el.style.backgroundColor = el.getAttribute('data-color');
        });
    }
    applyColors();

    // Scroll chat to bottom
    if (chatMessages) {
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }

    // Handle chat submission via AJAX to avoid page reload
    if (chatForm) {
        chatForm.onsubmit = async (e) => {
            e.preventDefault();
            const text = chatInput.value;
            if (!text) return;

            const formData = new FormData(chatForm);
            chatInput.value = '';

            try {
                await fetch("", {
                    method: 'POST',
                    body: formData,
                    headers: {
                        'X-Requested-With': 'XMLHttpRequest'
                    }
                });
                // Update will pick up the new message
                fetchUpdates();
            } catch (err) {
                console.error("Failed to send message", err);
            }
        };
    }

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
