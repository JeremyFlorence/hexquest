const size = 18;
const offsetX = 80;
const offsetY = 80;

const terrainColors = {
    water: "#2563eb",
    plains: "#84cc16",
    forest: "#15803d",
    hill: "#a16207",
    mountain: "#78716c",
    desert: "#facc15"
};

function axialToPixel(q, r) {
    const x = size * Math.sqrt(3) * (q + r / 2);
    const y = size * 1.5 * r;

    return {
        x: x + offsetX,
        y: y + offsetY
    };
}

function hexCorner(centerX, centerY, i) {
    const angleDeg = 60 * i - 30;
    const angleRad = Math.PI / 180 * angleDeg;

    return {
        x: centerX + size * Math.cos(angleRad),
        y: centerY + size * Math.sin(angleRad)
    };
}

function hexPoints(centerX, centerY) {
    const points = [];

    for (let i = 0; i < 6; i += 1) {
        const corner = hexCorner(centerX, centerY, i);
        points.push(`${corner.x},${corner.y}`);
    }

    return points.join(" ");
}

function renderHexes() {
    const svg = document.getElementById("map");
    const groups = document.querySelectorAll(".hex-group");

    groups.forEach((group) => {
        const q = Number(group.dataset.q);
        const r = Number(group.dataset.r);
        const terrain = group.dataset.terrain;
        const owner = group.dataset.owner;
        const ownerColor = group.dataset.ownerColor;

        const position = axialToPixel(q, r);

        const polygon = document.createElementNS(
            "http://www.w3.org/2000/svg",
            "polygon"
        );

        polygon.setAttribute("class", "hex");
        polygon.setAttribute("points", hexPoints(position.x, position.y));
        polygon.setAttribute("fill", terrainColors[terrain] || "#64748b");

        if (ownerColor) {
            polygon.setAttribute("stroke", ownerColor);
            polygon.setAttribute("stroke-width", "3");
        }

        const title = document.createElementNS(
            "http://www.w3.org/2000/svg",
            "title"
        );

        title.textContent = owner
            ? `(${q}, ${r}) ${terrain} - ${owner}`
            : `(${q}, ${r}) ${terrain}`;

        polygon.appendChild(title);
        group.appendChild(polygon);
        svg.appendChild(group);
    });
}

function renderUnits() {
    const svg = document.getElementById("map");
    const groups = document.querySelectorAll(".unit-group");

    groups.forEach((group) => {
        const q = Number(group.dataset.q);
        const r = Number(group.dataset.r);
        const color = group.dataset.color;
        const label = group.dataset.label;

        const position = axialToPixel(q, r);

        const circle = document.createElementNS(
            "http://www.w3.org/2000/svg",
            "circle"
        );

        circle.setAttribute("class", "unit");
        circle.setAttribute("cx", position.x);
        circle.setAttribute("cy", position.y);
        circle.setAttribute("r", "8");
        circle.setAttribute("fill", color || "#ffffff");
        circle.setAttribute("stroke", "#020617");
        circle.setAttribute("stroke-width", "2");

        const text = document.createElementNS(
            "http://www.w3.org/2000/svg",
            "text"
        );

        text.setAttribute("class", "unit-label");
        text.setAttribute("x", position.x);
        text.setAttribute("y", position.y + 1);
        text.textContent = label;

        group.appendChild(circle);
        group.appendChild(text);
        svg.appendChild(group);
    });
}

document.addEventListener('DOMContentLoaded', () => {
    renderHexes();
    renderUnits();

    const timerDisplay = document.getElementById('timer-display');
    const turnDisplay = document.getElementById('turn-display');
    const endTurnBtn = document.getElementById('end-turn-btn');

    // Timer countdown
    setInterval(() => {
        if (remainingTime > 0) {
            remainingTime -= 1;
            timerDisplay.textContent = remainingTime;
        } else {
            // Timer reached zero, turn should advance automatically
            // We poll frequently so it will catch up
        }
    }, 1000);

    async function fetchUpdates() {
        try {
            const response = await fetch(gameUpdatesUrl);
            const data = await response.json();

            // Update remaining time if it's significantly different
            if (Math.abs(data.remaining_time - remainingTime) > 5) {
                remainingTime = data.remaining_time;
                timerDisplay.textContent = remainingTime;
            }

            // Check if turn advanced
            if (data.current_turn > currentTurn) {
                window.location.reload(); // Simplest way to refresh entire state
                return;
            }

            // Update button state
            if (data.has_ended_turn !== hasEndedTurn) {
                hasEndedTurn = data.has_ended_turn;
                if (hasEndedTurn) {
                    endTurnBtn.disabled = true;
                    endTurnBtn.textContent = 'Waiting...';
                } else {
                    endTurnBtn.disabled = false;
                    endTurnBtn.textContent = 'End Turn';
                }
            }
        } catch (err) {
            console.error("Failed to fetch updates", err);
        }
    }

    // Poll for updates every 2 seconds
    setInterval(fetchUpdates, 2000);
});
