const size = 18;
const offsetX = 80;
const offsetY = 80;

let scale = 1.0;
const minScale = 0.5;
const maxScale = 3.0;
const zoomSpeed = 0.1;

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
        const settlementName = group.dataset.settlement;

        const position = axialToPixel(q, r);

        const polygon = document.createElementNS(
            "http://www.w3.org/2000/svg",
            "polygon"
        );

        polygon.setAttribute("class", "hex");
        polygon.setAttribute("points", hexPoints(position.x, position.y));
        polygon.setAttribute("fill", terrainColors[terrain] || "#64748b");

        if (ownerColor) {
            polygon.style.setProperty("--owner-color", ownerColor);
            polygon.style.setProperty("--owner-stroke-width", "3");
        }

        const title = document.createElementNS(
            "http://www.w3.org/2000/svg",
            "title"
        );

        title.textContent = owner
            ? `(${q}, ${r}) ${terrain} - ${owner}${settlementName ? ' (' + settlementName + ')' : ''}`
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
        circle.style.pointerEvents = "visiblePainted";

        circle.addEventListener("click", (e) => {
            e.stopPropagation();
            selectUnit(group);
        });

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

function renderSettlements() {
    const svg = document.getElementById("map");
    const groups = document.querySelectorAll(".settlement-group");

    groups.forEach((group) => {
        const q = Number(group.dataset.q);
        const r = Number(group.dataset.r);
        const color = group.dataset.color;
        const name = group.dataset.name;
        const tier = group.dataset.tier;
        const population = group.dataset.population;

        const position = axialToPixel(q, r);
        let icon;

        if (tier === "village") {
            // Circle icon
            icon = document.createElementNS("http://www.w3.org/2000/svg", "circle");
            icon.setAttribute("cx", position.x);
            icon.setAttribute("cy", position.y);
            icon.setAttribute("r", "7");
        } else if (tier === "town") {
            // Square icon
            icon = document.createElementNS("http://www.w3.org/2000/svg", "rect");
            icon.setAttribute("x", position.x - 7);
            icon.setAttribute("y", position.y - 7);
            icon.setAttribute("width", "14");
            icon.setAttribute("height", "14");
        } else if (tier === "city") {
            // Star icon
            icon = document.createElementNS("http://www.w3.org/2000/svg", "path");
            // A simple 5-pointed star
            const points = [];
            for (let i = 0; i < 10; i++) {
                const angle = (Math.PI / 5) * i - Math.PI / 2;
                const radius = i % 2 === 0 ? 10 : 4;
                points.push(`${position.x + radius * Math.cos(angle)},${position.y + radius * Math.sin(angle)}`);
            }
            icon.setAttribute("d", `M ${points.join(" L ")} Z`);
        }

        icon.setAttribute("class", "settlement");
        icon.setAttribute("fill", color || "#ffffff");
        icon.setAttribute("stroke", "#020617");
        icon.setAttribute("stroke-width", "2");
        icon.style.cursor = "pointer";

        icon.addEventListener("click", (e) => {
            e.stopPropagation();
            selectSettlement(group);
        });

        const title = document.createElementNS(
            "http://www.w3.org/2000/svg",
            "title"
        );
        title.textContent = `${name} (${tier}, Pop: ${population})`;
        icon.appendChild(title);

        group.appendChild(icon);
        svg.appendChild(group);
    });
}

function closeActionMenu() {
    const actionMenu = document.getElementById("action-menu");
    selectedUnit = null;
    actionMenu.style.display = "none";
    clearHighlights();
}

function selectSettlement(group) {
    const actionMenu = document.getElementById("action-menu");
    const unitInfo = document.getElementById("unit-info");
    const actionButtons = document.getElementById("action-buttons");

    // Reuse selectUnit logic for clearing
    if (selectedUnit === group) {
        closeActionMenu();
        return;
    }

    selectedUnit = group;
    clearHighlights();

    const id = group.dataset.id;
    const q = Number(group.dataset.q);
    const r = Number(group.dataset.r);
    const name = group.dataset.name;
    const tier = group.dataset.tier;
    const population = Number(group.dataset.population);
    const ownerId = Number(group.dataset.ownerId);

    unitInfo.textContent = `${name} (${tier})`;
    actionButtons.innerHTML = "";

    if (ownerId === currentUserId && !hasEndedTurn) {
        let upgradeReq = 0;
        let nextTier = "";

        if (tier === "village") {
            upgradeReq = 5;
            nextTier = "Town";
        } else if (tier === "town") {
            upgradeReq = 15;
            nextTier = "City";
        }

        if (nextTier) {
            const upgradeBtn = document.createElement("button");
            upgradeBtn.textContent = `Upgrade to ${nextTier} (Req: ${upgradeReq} Pop)`;
            if (population < upgradeReq) {
                upgradeBtn.disabled = true;
                upgradeBtn.title = `Need ${upgradeReq} population`;
            }
            upgradeBtn.onclick = () => upgradeSettlement(id);
            actionButtons.appendChild(upgradeBtn);
        }

        // Expand Action
        const expandBtn = document.createElement("button");
        expandBtn.textContent = "Expand Territory";
        expandBtn.onclick = () => showExpandTargets(group);
        actionButtons.appendChild(expandBtn);

        // Rename Action
        const renameBtn = document.createElement("button");
        renameBtn.textContent = "Rename Settlement";
        renameBtn.onclick = () => showNamingModal("Rename Settlement", name, (newName) => performRename(id, newName));
        actionButtons.appendChild(renameBtn);
    }

    const pos = axialToPixel(q, r);
    actionMenu.style.display = "block";
    
    // Position menu and ensure it's within map bounds
    const menuWidth = actionMenu.offsetWidth || 200;
    const menuHeight = actionMenu.offsetHeight || 100;
    
    let left = (pos.x * scale) + 20;
    let top = (pos.y * scale) - 20;
    
    // Basic bounds check against SVG size
    const svg = document.getElementById('map');
    const svgWidth = svg.width.baseVal.value * scale;
    const svgHeight = svg.height.baseVal.value * scale;
    
    if (left + menuWidth > svgWidth) left = (pos.x * scale) - menuWidth - 20;
    if (top + menuHeight > svgHeight) top = svgHeight - menuHeight - 10;
    if (top < 0) top = 10;
    if (left < 0) left = 10;

    actionMenu.style.left = `${left}px`;
    actionMenu.style.top = `${top}px`;
}

async function upgradeSettlement(settlementId) {
    const formData = new FormData();
    formData.append("csrfmiddlewaretoken", csrfToken);

    try {
        const response = await fetch(`/games/${gameId}/settlement/${settlementId}/upgrade/`, {
            method: "POST",
            body: formData
        });
        const data = await response.json();
        if (data.status === "ok") {
            window.location.reload();
        } else {
            alert(data.error);
        }
    } catch (err) {
        console.error(err);
    }
}

let selectedUnit = null;

function selectUnit(unitGroup) {
    const actionMenu = document.getElementById("action-menu");
    const unitInfo = document.getElementById("unit-info");
    const actionButtons = document.getElementById("action-buttons");

    if (selectedUnit === unitGroup) {
        closeActionMenu();
        return;
    }

    selectedUnit = unitGroup;
    clearHighlights();

    const id = unitGroup.dataset.id;
    const type = unitGroup.dataset.type;
    const q = Number(unitGroup.dataset.q);
    const r = Number(unitGroup.dataset.r);
    const ownerId = Number(unitGroup.dataset.ownerId);

    unitInfo.textContent = type;
    actionButtons.innerHTML = "";

    if (ownerId === currentUserId && !hasEndedTurn) {
        // Move Action
        const moveBtn = document.createElement("button");
        moveBtn.textContent = "Move";
        moveBtn.onclick = () => showMoveTargets(unitGroup);
        actionButtons.appendChild(moveBtn);

        // Settle Action
        if (type === "settler") {
            const settleBtn = document.createElement("button");
            settleBtn.textContent = "Build Settlement";
            settleBtn.onclick = () => showNamingModal("Name Your Settlement", "New Settlement", (name) => performSettle(id, name));
            actionButtons.appendChild(settleBtn);
        }
    }

    const pos = axialToPixel(q, r);
    actionMenu.style.display = "block";

    // Position menu and ensure it's within map bounds
    const menuWidth = actionMenu.offsetWidth || 200;
    const menuHeight = actionMenu.offsetHeight || 100;
    
    let left = (pos.x * scale) + 20;
    let top = (pos.y * scale) - 20;
    
    // Basic bounds check against SVG size
    const svg = document.getElementById('map');
    const svgWidth = svg.width.baseVal.value * scale;
    const svgHeight = svg.height.baseVal.value * scale;
    
    if (left + menuWidth > svgWidth) left = (pos.x * scale) - menuWidth - 20;
    if (top + menuHeight > svgHeight) top = svgHeight - menuHeight - 10;
    if (top < 0) top = 10;
    if (left < 0) left = 10;

    actionMenu.style.left = `${left}px`;
    actionMenu.style.top = `${top}px`;
}

function showMoveTargets(unitGroup) {
    clearHighlights();
    const q = Number(unitGroup.dataset.q);
    const r = Number(unitGroup.dataset.r);

    const neighbors = [
        [1, 0], [1, -1], [0, -1], [-1, 0], [-1, 1], [0, 1]
    ];

    neighbors.forEach(([dq, dr]) => {
        const targetQ = q + dq;
        const targetR = r + dr;
        const hex = document.querySelector(`.hex-group[data-q="${targetQ}"][data-r="${targetR}"] .hex`);
        if (hex) {
            const terrain = hex.parentElement.dataset.terrain;
            if (terrain !== "water") {
                hex.classList.add("highlight-move");
                hex.onclick = () => performMove(unitGroup.dataset.id, targetQ, targetR);
            }
        }
    });
}

function showExpandTargets(settlementGroup) {
    clearHighlights();
    const q = Number(settlementGroup.dataset.q);
    const r = Number(settlementGroup.dataset.r);
    const settlementId = settlementGroup.dataset.id;

    const neighbors = [
        [1, 0], [1, -1], [0, -1], [-1, 0], [-1, 1], [0, 1]
    ];

    neighbors.forEach(([dq, dr]) => {
        const targetQ = q + dq;
        const targetR = r + dr;
        const hex = document.querySelector(`.hex-group[data-q="${targetQ}"][data-r="${targetR}"] .hex`);
        if (hex) {
            const group = hex.parentElement;
            const terrain = group.dataset.terrain;
            const ownerId = group.dataset.ownerId;
            
            if (terrain !== "water" && !ownerId) {
                hex.classList.add("highlight-move"); // Reuse highlight-move class for simplicity
                hex.onclick = () => performExpand(settlementId, targetQ, targetR);
            }
        }
    });
}

async function performExpand(settlementId, q, r) {
    const formData = new FormData();
    formData.append("q", q);
    formData.append("r", r);
    formData.append("csrfmiddlewaretoken", csrfToken);

    try {
        const response = await fetch(`/games/${gameId}/settlement/${settlementId}/expand/`, {
            method: "POST",
            body: formData
        });
        const data = await response.json();
        if (data.status === "ok") {
            window.location.reload();
        } else {
            alert(data.error);
        }
    } catch (err) {
        console.error(err);
    }
}

function clearHighlights() {
    document.querySelectorAll(".hex.highlight-move").forEach(hex => {
        hex.classList.remove("highlight-move");
        hex.onclick = null;
    });
}

async function performMove(unitId, q, r) {
    const formData = new FormData();
    formData.append("q", q);
    formData.append("r", r);
    formData.append("csrfmiddlewaretoken", csrfToken);

    try {
        const response = await fetch(`/games/${gameId}/unit/${unitId}/move/`, {
            method: "POST",
            body: formData
        });
        const data = await response.json();
        if (data.status === "ok") {
            window.location.reload();
        } else {
            alert(data.error);
        }
    } catch (err) {
        console.error(err);
    }
}

async function performSettle(unitId, name) {
    const formData = new FormData();
    formData.append("csrfmiddlewaretoken", csrfToken);
    formData.append("name", name);

    try {
        const response = await fetch(`/games/${gameId}/unit/${unitId}/settle/`, {
            method: "POST",
            body: formData
        });
        const data = await response.json();
        if (data.status === "ok") {
            window.location.reload();
        } else {
            alert(data.error);
        }
    } catch (err) {
        console.error(err);
    }
}

function showNamingModal(title, defaultValue, onConfirm) {
    const modal = document.getElementById("naming-modal");
    const titleEl = document.getElementById("modal-title");
    const input = document.getElementById("settlement-name-input");
    const confirmBtn = document.getElementById("modal-confirm-btn");
    const cancelBtn = document.getElementById("modal-cancel-btn");

    titleEl.textContent = title;
    input.value = defaultValue;
    modal.style.display = "flex";
    input.focus();
    input.select();

    const handleConfirm = () => {
        const name = input.value.trim();
        if (name) {
            modal.style.display = "none";
            onConfirm(name);
            cleanup();
        }
    };

    const handleCancel = () => {
        modal.style.display = "none";
        cleanup();
    };

    const handleKeydown = (e) => {
        if (e.key === "Enter") handleConfirm();
        if (e.key === "Escape") handleCancel();
    };

    const cleanup = () => {
        confirmBtn.removeEventListener("click", handleConfirm);
        cancelBtn.removeEventListener("click", handleCancel);
        input.removeEventListener("keydown", handleKeydown);
    };

    confirmBtn.addEventListener("click", handleConfirm);
    cancelBtn.addEventListener("click", handleCancel);
    input.addEventListener("keydown", handleKeydown);
}

async function performRename(settlementId, newName) {
    const formData = new FormData();
    formData.append("csrfmiddlewaretoken", csrfToken);
    formData.append("name", newName);

    try {
        const response = await fetch(`/games/${gameId}/settlement/${settlementId}/rename/`, {
            method: "POST",
            body: formData
        });
        const data = await response.json();
        if (data.status === "ok") {
            window.location.reload();
        } else {
            alert(data.error);
        }
    } catch (err) {
        console.error(err);
    }
}

document.addEventListener('DOMContentLoaded', () => {
    renderHexes();
    renderUnits();
    renderSettlements();

    const timerDisplay = document.getElementById('timer-display');
    const turnDisplay = document.getElementById('turn-display');
    const endTurnBtn = document.getElementById('end-turn-btn');
    const goldDisplay = document.getElementById('gold-display');
    const foodDisplay = document.getElementById('food-display');
    const unitsDisplay = document.getElementById('units-display');

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

            // Update resources
            if (goldDisplay) goldDisplay.textContent = data.gold;
            if (foodDisplay) foodDisplay.textContent = data.food;
            if (unitsDisplay) unitsDisplay.textContent = data.unit_count;
        } catch (err) {
            console.error("Failed to fetch updates", err);
        }
    }

    // Poll for updates every 2 seconds
    setInterval(fetchUpdates, 2000);

    // Escape key to close action menu
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            closeActionMenu();
        }
    });

    // Zoom functionality
    const mapSvg = document.getElementById('map');
    const mapWrap = document.querySelector('.map-wrap');
    mapSvg.style.transformOrigin = '0 0';

    window.addEventListener('wheel', (e) => {
        if (e.ctrlKey || e.metaKey) {
            e.preventDefault();

            // Get mouse position relative to map-wrap
            const rect = mapWrap.getBoundingClientRect();
            const mouseX = e.clientX - rect.left;
            const mouseY = e.clientY - rect.top;

            // Get mouse position relative to map content (taking current scale and scroll into account)
            const contentX = (mouseX + mapWrap.scrollLeft) / scale;
            const contentY = (mouseY + mapWrap.scrollTop) / scale;

            const delta = e.deltaY > 0 ? -zoomSpeed : zoomSpeed;
            const oldScale = scale;
            scale = Math.min(Math.max(scale + delta, minScale), maxScale);

            if (oldScale !== scale) {
                mapSvg.style.transform = `scale(${scale})`;

                // Adjust scroll to keep contentX, contentY under the mouse
                mapWrap.scrollLeft = contentX * scale - mouseX;
                mapWrap.scrollTop = contentY * scale - mouseY;
                
                // If action menu is open, reposition it
                const actionMenu = document.getElementById('action-menu');
                if (actionMenu.style.display === 'block' && selectedUnit) {
                    const q = Number(selectedUnit.dataset.q);
                    const r = Number(selectedUnit.dataset.r);
                    const pos = axialToPixel(q, r);
                    
                    const menuWidth = actionMenu.offsetWidth || 200;
                    const menuHeight = actionMenu.offsetHeight || 100;
                    
                    let left = (pos.x * scale) + 20;
                    let top = (pos.y * scale) - 20;
                    
                    const svgWidth = mapSvg.width.baseVal.value * scale;
                    const svgHeight = mapSvg.height.baseVal.value * scale;
                    
                    if (left + menuWidth > svgWidth) left = (pos.x * scale) - menuWidth - 20;
                    if (top + menuHeight > svgHeight) top = svgHeight - menuHeight - 10;
                    if (top < 0) top = 10;
                    if (left < 0) left = 10;

                    actionMenu.style.left = `${left}px`;
                    actionMenu.style.top = `${top}px`;
                }
            }
        }
    }, { passive: false });
});
