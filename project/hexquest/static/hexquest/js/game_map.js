const size = 18;
const offsetX = 80;
const offsetY = 80;

let scale = 1.0;
const minScale = 0.5;
const maxScale = 3.0;
const zoomSpeed = 0.1;

function formatBuildingLabel(buildingType) {
    return buildingType
        .split("_")
        .map((word) => word[0].toUpperCase() + word.slice(1))
        .join(" ");
}

const terrainColors = {
    water: "#2563eb",
    plains: "#84cc16",
    forest: "#15803d",
    hill: "#a16207",
    mountain: "#78716c",
    desert: "#facc15"
};

function axialToPixel(q, r) {
    q = Number(q) || 0;
    r = Number(r) || 0;
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

// A hex tile can hold at most 2 units, or 1 unit alongside a building/settlement.
// Icon shapes are drawn in local coordinates centered on (0, 0); relayoutHex
// positions/scales each occupant's group via an SVG transform so a shared hex
// never renders overlapping icons.
const SHARED_HEX_SLOT_DX = 7;
const SHARED_HEX_SCALE = 0.65;

function showDamageText(q, r, damage) {
    const svg = document.getElementById("map");
    if (!svg) return;
    const pos = axialToPixel(q, r);

    const text = document.createElementNS("http://www.w3.org/2000/svg", "text");
    text.setAttribute("class", "damage-text");
    // Small random offset so simultaneous hits on the same hex don't overlap exactly.
    text.setAttribute("x", pos.x + (Math.random() - 0.5) * 6);
    text.setAttribute("y", pos.y - 12);
    text.textContent = `-${damage}`;
    svg.appendChild(text);

    const remove = () => text.remove();
    text.addEventListener("animationend", remove);
    setTimeout(remove, 1500); // fallback in case animationend never fires
}

function relayoutHex(q, r) {
    q = Number(q);
    r = Number(r);
    const center = axialToPixel(q, r);
    const hexGroup = document.querySelector(`.hex-group[data-q="${q}"][data-r="${r}"]`);

    const settlementGroup = document.querySelector(`.settlement-group[data-q="${q}"][data-r="${r}"]`);
    const buildingIcon = hexGroup ? hexGroup.querySelector(".building") : null;
    const structureEl = settlementGroup || buildingIcon;

    const unitGroups = Array.from(
        document.querySelectorAll(`.unit-group[data-q="${q}"][data-r="${r}"]`)
    ).sort((a, b) => Number(a.dataset.id) - Number(b.dataset.id));

    const occupants = structureEl ? [structureEl, ...unitGroups] : unitGroups;
    if (occupants.length === 0) return;

    if (occupants.length === 1) {
        occupants[0].setAttribute("transform", `translate(${center.x}, ${center.y}) scale(1)`);
        return;
    }

    // 2 occupants share the hex (a structure + 1 unit, or 2 units): fan them out
    // side by side so they don't overlap. Any extra occupants beyond the
    // expected max of 2 are nudged further out as a defensive fallback.
    occupants.forEach((el, i) => {
        const dx = i === 0 ? -SHARED_HEX_SLOT_DX : SHARED_HEX_SLOT_DX;
        const dy = i <= 1 ? 0 : (i - 1) * 6;
        el.setAttribute("transform", `translate(${center.x + dx}, ${center.y + dy}) scale(${SHARED_HEX_SCALE})`);
    });
}

function renderBuildings() {
    const groups = document.querySelectorAll(".hex-group");
    groups.forEach((group) => {
        renderSingleBuilding(group);
    });
}

function renderSingleBuilding(group) {
    if (!group) return;

    const q = group.dataset.q;
    const r = group.dataset.r;
    if (q === undefined || r === undefined) return;

    const buildingType = group.dataset.building;
    let icon = group.querySelector(".building");

    if (!buildingType) {
        if (icon) icon.remove();
        relayoutHex(q, r);
        return;
    }

    if (!icon) {
        icon = document.createElementNS("http://www.w3.org/2000/svg", "g");
        icon.setAttribute("class", "building");
        group.appendChild(icon);
    }
    icon.innerHTML = '';

    // Icon is drawn in local coordinates centered on (0, 0); relayoutHex
    // applies the actual hex position (and scale, if the hex is shared).
    if (buildingType === "wheat_farm") {
        // Stem
        const stem = document.createElementNS("http://www.w3.org/2000/svg", "line");
        stem.setAttribute("x1", 0);
        stem.setAttribute("y1", 8);
        stem.setAttribute("x2", 0);
        stem.setAttribute("y2", -8);
        stem.setAttribute("stroke", "#8b7355");
        stem.setAttribute("stroke-width", "2");
        stem.setAttribute("stroke-linecap", "round");
        icon.appendChild(stem);

        // Left stalk
        const leftStalk = document.createElementNS("http://www.w3.org/2000/svg", "line");
        leftStalk.setAttribute("x1", -4);
        leftStalk.setAttribute("y1", 8);
        leftStalk.setAttribute("x2", -6);
        leftStalk.setAttribute("y2", -4);
        leftStalk.setAttribute("stroke", "#8b7355");
        leftStalk.setAttribute("stroke-width", "1.5");
        leftStalk.setAttribute("stroke-linecap", "round");
        icon.appendChild(leftStalk);

        // Right stalk
        const rightStalk = document.createElementNS("http://www.w3.org/2000/svg", "line");
        rightStalk.setAttribute("x1", 4);
        rightStalk.setAttribute("y1", 8);
        rightStalk.setAttribute("x2", 6);
        rightStalk.setAttribute("y2", -4);
        rightStalk.setAttribute("stroke", "#8b7355");
        rightStalk.setAttribute("stroke-width", "1.5");
        rightStalk.setAttribute("stroke-linecap", "round");
        icon.appendChild(rightStalk);

        // Grain heads
        [[0, -9], [-6, -5], [6, -5]].forEach(([cx, cy]) => {
            const grain = document.createElementNS("http://www.w3.org/2000/svg", "circle");
            grain.setAttribute("cx", cx);
            grain.setAttribute("cy", cy);
            grain.setAttribute("r", "2.5");
            grain.setAttribute("fill", "#eab308");
            grain.setAttribute("stroke", "#713f12");
            grain.setAttribute("stroke-width", "0.5");
            icon.appendChild(grain);
        });
    } else if (buildingType === "barracks") {
        // Larger invisible hit target so the small icon stays easy to click.
        const hitArea = document.createElementNS("http://www.w3.org/2000/svg", "circle");
        hitArea.setAttribute("cx", 0);
        hitArea.setAttribute("cy", 0);
        hitArea.setAttribute("r", "9");
        hitArea.setAttribute("fill", "transparent");
        hitArea.style.cursor = "pointer";
        hitArea.style.pointerEvents = "auto";
        hitArea.addEventListener("click", (e) => {
            e.stopPropagation();
            selectBuilding(group);
        });
        icon.appendChild(hitArea);

        // Shield
        const shield = document.createElementNS("http://www.w3.org/2000/svg", "path");
        shield.setAttribute("d", "M 0,-9 L 6,-6 L 6,2 Q 6,8 0,10 Q -6,8 -6,2 L -6,-6 Z");
        shield.setAttribute("fill", "#78716c");
        shield.setAttribute("stroke", "#292524");
        shield.setAttribute("stroke-width", "1");
        shield.style.pointerEvents = "none";
        icon.appendChild(shield);

        // Crossed spear + sword
        const cross1 = document.createElementNS("http://www.w3.org/2000/svg", "line");
        cross1.setAttribute("x1", -4);
        cross1.setAttribute("y1", -5);
        cross1.setAttribute("x2", 4);
        cross1.setAttribute("y2", 5);
        cross1.setAttribute("stroke", "#eab308");
        cross1.setAttribute("stroke-width", "1.5");
        cross1.setAttribute("stroke-linecap", "round");
        cross1.style.pointerEvents = "none";
        icon.appendChild(cross1);

        const cross2 = document.createElementNS("http://www.w3.org/2000/svg", "line");
        cross2.setAttribute("x1", 4);
        cross2.setAttribute("y1", -5);
        cross2.setAttribute("x2", -4);
        cross2.setAttribute("y2", 5);
        cross2.setAttribute("stroke", "#e2e8f0");
        cross2.setAttribute("stroke-width", "1.5");
        cross2.setAttribute("stroke-linecap", "round");
        cross2.style.pointerEvents = "none";
        icon.appendChild(cross2);
    }

    const title = document.createElementNS("http://www.w3.org/2000/svg", "title");
    title.textContent = formatBuildingLabel(buildingType);
    icon.appendChild(title);

    relayoutHex(q, r);
}

function renderUnits() {
    const groups = document.querySelectorAll(".unit-group");
    groups.forEach((group) => {
        renderSingleUnit(group);
    });
}

function renderSingleUnit(group) {
    if (!group) return;
    const svg = document.getElementById("map");
    if (!svg) return;

    const q = group.dataset.q;
    const r = group.dataset.r;
    if (q === undefined || r === undefined) return;

    const color = group.dataset.color;
    const label = group.dataset.label || "?";
    const unitType = group.dataset.type;

    // Shapes are drawn in local coordinates centered on (0, 0); relayoutHex
    // applies the actual hex position (and scale, if the hex is shared).
    if (unitType === "builder") {
        // Clear non-builder elements if they exist
        if (group.querySelector("circle")) {
            group.innerHTML = '';
        }

        // Hammer head (rectangle)
        let hammerHead = group.querySelector("rect.unit");
        if (!hammerHead) {
            hammerHead = document.createElementNS("http://www.w3.org/2000/svg", "rect");
            hammerHead.setAttribute("class", "unit");
            hammerHead.style.cursor = "pointer";
            hammerHead.addEventListener("click", (e) => {
                e.stopPropagation();
                handleUnitClick(group);
            });
            group.appendChild(hammerHead);
        }
        hammerHead.setAttribute("x", -6);
        hammerHead.setAttribute("y", -8);
        hammerHead.setAttribute("width", "12");
        hammerHead.setAttribute("height", "8");
        hammerHead.setAttribute("fill", color || "#ffffff");
        hammerHead.setAttribute("stroke", "#020617");
        hammerHead.setAttribute("stroke-width", "2");
        hammerHead.setAttribute("rx", "1");

        // Hammer handle (line)
        let hammerHandle = group.querySelector("line");
        if (!hammerHandle) {
            hammerHandle = document.createElementNS("http://www.w3.org/2000/svg", "line");
            hammerHandle.style.pointerEvents = "none";
            group.appendChild(hammerHandle);
        }
        hammerHandle.setAttribute("x1", 0);
        hammerHandle.setAttribute("y1", 0);
        hammerHandle.setAttribute("x2", 0);
        hammerHandle.setAttribute("y2", 8);
        hammerHandle.setAttribute("stroke", "#8b7355");
        hammerHandle.setAttribute("stroke-width", "2");
        hammerHandle.setAttribute("stroke-linecap", "round");
    } else if (unitType === "spearman" || unitType === "swordsman") {
        // Clear builder/label elements if they exist
        if (group.querySelector("rect.unit") || group.querySelector("text.unit-label")) {
            group.innerHTML = '';
        }

        // Background circle (also the click target)
        let circle = group.querySelector("circle.unit");
        if (!circle) {
            circle = document.createElementNS("http://www.w3.org/2000/svg", "circle");
            circle.setAttribute("class", "unit");
            circle.style.pointerEvents = "visiblePainted";
            circle.addEventListener("click", (e) => {
                e.stopPropagation();
                handleUnitClick(group);
            });
            group.appendChild(circle);
        }
        circle.setAttribute("cx", 0);
        circle.setAttribute("cy", 0);
        circle.setAttribute("r", "8");
        circle.setAttribute("fill", color || "#ffffff");
        circle.setAttribute("stroke", "#020617");
        circle.setAttribute("stroke-width", "2");

        if (unitType === "spearman") {
            // Spear: vertical shaft with a triangular tip
            let shaft = group.querySelector("line.icon-shaft");
            if (!shaft) {
                shaft = document.createElementNS("http://www.w3.org/2000/svg", "line");
                shaft.setAttribute("class", "icon-shaft");
                shaft.style.pointerEvents = "none";
                group.appendChild(shaft);
            }
            shaft.setAttribute("x1", 0);
            shaft.setAttribute("y1", 5);
            shaft.setAttribute("x2", 0);
            shaft.setAttribute("y2", -5);
            shaft.setAttribute("stroke", "#020617");
            shaft.setAttribute("stroke-width", "1.5");

            let tip = group.querySelector("polygon.icon-tip");
            if (!tip) {
                tip = document.createElementNS("http://www.w3.org/2000/svg", "polygon");
                tip.setAttribute("class", "icon-tip");
                tip.style.pointerEvents = "none";
                group.appendChild(tip);
            }
            tip.setAttribute("points", "0,-7 -2.5,-3.5 2.5,-3.5");
            tip.setAttribute("fill", "#020617");
        } else {
            // Sword: upright blade with a crossguard, grip, and pommel
            let blade = group.querySelector("polygon.icon-blade");
            if (!blade) {
                blade = document.createElementNS("http://www.w3.org/2000/svg", "polygon");
                blade.setAttribute("class", "icon-blade");
                blade.style.pointerEvents = "none";
                group.appendChild(blade);
            }
            blade.setAttribute("points", "0,-7 1.3,-4 1.3,1 -1.3,1 -1.3,-4");
            blade.setAttribute("fill", "#e2e8f0");
            blade.setAttribute("stroke", "#020617");
            blade.setAttribute("stroke-width", "0.75");

            let guard = group.querySelector("line.icon-guard");
            if (!guard) {
                guard = document.createElementNS("http://www.w3.org/2000/svg", "line");
                guard.setAttribute("class", "icon-guard");
                guard.style.pointerEvents = "none";
                group.appendChild(guard);
            }
            guard.setAttribute("x1", -4);
            guard.setAttribute("y1", 1);
            guard.setAttribute("x2", 4);
            guard.setAttribute("y2", 1);
            guard.setAttribute("stroke", "#eab308");
            guard.setAttribute("stroke-width", "1.5");
            guard.setAttribute("stroke-linecap", "round");

            let grip = group.querySelector("line.icon-grip");
            if (!grip) {
                grip = document.createElementNS("http://www.w3.org/2000/svg", "line");
                grip.setAttribute("class", "icon-grip");
                grip.style.pointerEvents = "none";
                group.appendChild(grip);
            }
            grip.setAttribute("x1", 0);
            grip.setAttribute("y1", 1);
            grip.setAttribute("x2", 0);
            grip.setAttribute("y2", 4.5);
            grip.setAttribute("stroke", "#8b7355");
            grip.setAttribute("stroke-width", "1.5");
            grip.setAttribute("stroke-linecap", "round");

            let pommel = group.querySelector("circle.icon-pommel");
            if (!pommel) {
                pommel = document.createElementNS("http://www.w3.org/2000/svg", "circle");
                pommel.setAttribute("class", "icon-pommel");
                pommel.style.pointerEvents = "none";
                group.appendChild(pommel);
            }
            pommel.setAttribute("cx", 0);
            pommel.setAttribute("cy", 5);
            pommel.setAttribute("r", "1");
            pommel.setAttribute("fill", "#eab308");
            pommel.setAttribute("stroke", "#713f12");
            pommel.setAttribute("stroke-width", "0.5");
        }
    } else {
        // Clear builder/icon elements if they exist
        if (group.querySelector("rect.unit") || group.querySelector(".icon-shaft, .icon-blade")) {
            group.innerHTML = '';
        }

        // Render standard unit circle
        let circle = group.querySelector("circle.unit");
        if (!circle) {
            circle = document.createElementNS("http://www.w3.org/2000/svg", "circle");
            circle.setAttribute("class", "unit");
            circle.style.pointerEvents = "visiblePainted";
            circle.addEventListener("click", (e) => {
                e.stopPropagation();
                handleUnitClick(group);
            });
            group.appendChild(circle);
        }
        circle.setAttribute("cx", 0);
        circle.setAttribute("cy", 0);
        circle.setAttribute("r", "8");
        circle.setAttribute("fill", color || "#ffffff");
        circle.setAttribute("stroke", "#020617");
        circle.setAttribute("stroke-width", "2");

        let text = group.querySelector("text.unit-label");
        if (!text) {
            text = document.createElementNS("http://www.w3.org/2000/svg", "text");
            text.setAttribute("class", "unit-label");
            group.appendChild(text);
        }
        text.setAttribute("x", 0);
        text.setAttribute("y", 1);
        text.textContent = label;
    }

    // Ensure unit groups are placed on top of hexes/settlements
    svg.appendChild(group);
    relayoutHex(q, r);
}

function renderSettlements() {
    const groups = document.querySelectorAll(".settlement-group");
    groups.forEach((group) => {
        renderSingleSettlement(group);
    });
}

function renderSingleSettlement(group) {
    const svg = document.getElementById("map");
    const q = Number(group.dataset.q);
    const r = Number(group.dataset.r);
    const color = group.dataset.color;
    const name = group.dataset.name;
    const tier = group.dataset.tier;
    const population = group.dataset.population;

    // Shapes are drawn in local coordinates centered on (0, 0); relayoutHex
    // applies the actual hex position (and scale, if the hex is shared).
    let icon = group.querySelector(".settlement");
    let needsNewIcon = false;

    if (!icon) {
        needsNewIcon = true;
    } else {
        // Check if tier changed, requiring a different shape
        const currentTier = icon.tagName.toLowerCase();
        if (tier === "village" && currentTier !== "circle") needsNewIcon = true;
        else if (tier === "town" && currentTier !== "rect") needsNewIcon = true;
        else if (tier === "city" && currentTier !== "path") needsNewIcon = true;
    }

    if (needsNewIcon) {
        group.innerHTML = '';
        if (tier === "village") {
            icon = document.createElementNS("http://www.w3.org/2000/svg", "circle");
            icon.setAttribute("r", "7");
        } else if (tier === "town") {
            icon = document.createElementNS("http://www.w3.org/2000/svg", "rect");
            icon.setAttribute("width", "14");
            icon.setAttribute("height", "14");
        } else if (tier === "city") {
            icon = document.createElementNS("http://www.w3.org/2000/svg", "path");
        }
        icon.setAttribute("class", "settlement");
        icon.style.cursor = "pointer";
        icon.addEventListener("click", (e) => {
            e.stopPropagation();
            selectSettlement(group);
        });
        group.appendChild(icon);
    }

    if (tier === "village") {
        icon.setAttribute("cx", 0);
        icon.setAttribute("cy", 0);
    } else if (tier === "town") {
        icon.setAttribute("x", -7);
        icon.setAttribute("y", -7);
    } else if (tier === "city") {
        const points = [];
        for (let i = 0; i < 10; i++) {
            const angle = (Math.PI / 5) * i - Math.PI / 2;
            const radius = i % 2 === 0 ? 10 : 4;
            points.push(`${radius * Math.cos(angle)},${radius * Math.sin(angle)}`);
        }
        icon.setAttribute("d", `M ${points.join(" L ")} Z`);
    }

    icon.setAttribute("fill", color || "#ffffff");
    icon.setAttribute("stroke", "#020617");
    icon.setAttribute("stroke-width", "2");

    let title = icon.querySelector("title");
    if (!title) {
        title = document.createElementNS("http://www.w3.org/2000/svg", "title");
        icon.appendChild(title);
    }
    title.textContent = `${name} (${tier}, Pop: ${population})`;

    svg.appendChild(group);
    relayoutHex(q, r);
}

function closeActionMenu() {
    const actionMenu = document.getElementById("action-menu");
    selectedUnit = null;
    isMenuDragged = false;
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
    const ownerName = group.dataset.ownerName;
    const ownerNation = group.dataset.ownerNation;
    const lastActionTurn = Number(group.dataset.lastActionTurn);
    const isQueued = group.dataset.queuedAction === "true";

    unitInfo.textContent = ownerId === currentUserId
        ? `${name} (${tier})`
        : `${name} (${tier}) — ${ownerNation} (${ownerName})`;
    actionButtons.innerHTML = "";

    if (ownerId === currentUserId && isMyTurn) {
        if (isQueued) {
            const msg = document.createElement("p");
            msg.textContent = "Action queued for end of turn.";
            msg.style.color = "#8b5cf6";
            msg.style.fontSize = "0.875rem";
            actionButtons.appendChild(msg);
        } else {
            showSettlementActions(id, tier, population, ownerId, actionButtons);
        }

        // Rename Action (Rename is usually not considered an 'action' that exhausts turn)
        const renameBtn = document.createElement("button");
        renameBtn.textContent = "Rename Settlement";
        renameBtn.onclick = () => showNamingModal("Rename Settlement", name, (newName) => performRename(id, newName));
        actionButtons.appendChild(renameBtn);
    }

    const pos = axialToPixel(q, r);
    actionMenu.style.display = "block";
    
    if (!isMenuDragged) {
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
}

function showSettlementActions(id, tier, population, ownerId, container) {
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
        container.appendChild(upgradeBtn);
    }

    // Expand Action (cost scales with the nation's total owned tile count,
    // mirroring the server-side formula in expand_settlement/process_turn_end)
    const ownedTilesCount = document.querySelectorAll(`.hex-group[data-owner-id="${ownerId}"]`).length;
    const expandCost = 10 + (ownedTilesCount * 5);
    const expandBtn = document.createElement("button");
    expandBtn.textContent = `Expand Territory 💰${expandCost}`;
    expandBtn.onclick = () => showExpandTargets(selectedUnit);
    container.appendChild(expandBtn);
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
        if (data.status === "ok" || data.status === "queued") {
            closeActionMenu();
        } else {
            alert(data.error);
        }
    } catch (err) {
        console.error(err);
    }
}

function selectBuilding(hexGroup) {
    const actionMenu = document.getElementById("action-menu");
    const unitInfo = document.getElementById("unit-info");
    const actionButtons = document.getElementById("action-buttons");

    if (selectedUnit === hexGroup) {
        closeActionMenu();
        return;
    }

    selectedUnit = hexGroup;
    clearHighlights();

    const buildingId = hexGroup.dataset.buildingId;
    const buildingType = hexGroup.dataset.building;
    const q = Number(hexGroup.dataset.q);
    const r = Number(hexGroup.dataset.r);
    const ownerId = Number(hexGroup.dataset.ownerId);
    const isQueued = hexGroup.dataset.buildingQueued === "true";

    unitInfo.textContent = formatBuildingLabel(buildingType);
    actionButtons.innerHTML = "";

    if (ownerId === currentUserId && isMyTurn) {
        if (isQueued) {
            const msg = document.createElement("p");
            msg.textContent = "Action queued for end of turn.";
            msg.style.color = "#8b5cf6";
            msg.style.fontSize = "0.875rem";
            actionButtons.appendChild(msg);
        } else if (buildingType === "barracks") {
            Object.keys(unitRecruitCosts).forEach((unitType) => {
                const cost = unitRecruitCosts[unitType];
                const recruitBtn = document.createElement("button");
                recruitBtn.textContent = `Recruit ${formatBuildingLabel(unitType)} 💰${cost}`;
                recruitBtn.onclick = () => performRecruit(buildingId, unitType);
                actionButtons.appendChild(recruitBtn);
            });
        }
    }

    const pos = axialToPixel(q, r);
    actionMenu.style.display = "block";

    if (!isMenuDragged) {
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
}

async function performRecruit(buildingId, unitType) {
    const formData = new FormData();
    formData.append("unit_type", unitType);
    formData.append("csrfmiddlewaretoken", csrfToken);

    try {
        const response = await fetch(`/games/${gameId}/building/${buildingId}/recruit/`, {
            method: "POST",
            body: formData
        });
        const data = await response.json();
        if (data.status === "ok" || data.status === "queued") {
            closeActionMenu();
        } else {
            alert(data.error);
        }
    } catch (err) {
        console.error(err);
    }
}

let selectedUnit = null;
let isMenuDragged = false;

// While an Attack order is being targeted, clicking a highlighted enemy
// unit's icon should queue the attack instead of selecting that unit (its
// icon renders on top of the hex and would otherwise intercept the click).
let activeAttackSourceId = null;
let activeAttackTargetIds = new Set();

function handleUnitClick(group) {
    if (activeAttackSourceId && activeAttackTargetIds.has(group.dataset.id)) {
        performAttack(activeAttackSourceId, group.dataset.id);
        return;
    }
    selectUnit(group);
}

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
    const ownerName = unitGroup.dataset.ownerName;
    const ownerNation = unitGroup.dataset.ownerNation;
    const lastActionTurn = Number(unitGroup.dataset.lastActionTurn);
    const isQueued = unitGroup.dataset.queuedAction === "true";
    const hitpoints = unitGroup.dataset.hitpoints;
    const maxHitpoints = unitGroup.dataset.maxHitpoints;
    const attack = unitGroup.dataset.attack;
    const defense = unitGroup.dataset.defense;

    const statsText = `${hitpoints}/${maxHitpoints} HP ⚔${attack} 🛡${defense}`;
    unitInfo.textContent = ownerId === currentUserId
        ? `${type} — ${statsText}`
        : `${type} — ${ownerNation} (${ownerName}) — ${statsText}`;
    actionButtons.innerHTML = "";

    if (ownerId === currentUserId && isMyTurn) {
        if (isQueued) {
            const msg = document.createElement("p");
            msg.textContent = "Action queued for end of turn.";
            msg.style.color = "#8b5cf6";
            msg.style.fontSize = "0.875rem";
            actionButtons.appendChild(msg);
        } else {
            showUnitActions(id, type, actionButtons);
        }
    }

    const pos = axialToPixel(q, r);
    actionMenu.style.display = "block";

    if (!isMenuDragged) {
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
}

function showUnitActions(id, type, container) {
    // Move Action
    const moveBtn = document.createElement("button");
    moveBtn.textContent = "Move";
    moveBtn.onclick = () => showMoveTargets(selectedUnit);
    container.appendChild(moveBtn);

    // Settle Action
    if (type === "settler") {
        const settleBtn = document.createElement("button");
        settleBtn.textContent = "Build Settlement";
        settleBtn.onclick = () => showNamingModal("Name Your Settlement", "New Settlement", (name) => performSettle(id, name));
        container.appendChild(settleBtn);
    }

    // Build Actions (one button per building type, showing its gold cost)
    if (type === "builder") {
        Object.keys(buildingCosts).forEach((buildingType) => {
            const cost = buildingCosts[buildingType];
            const buildBtn = document.createElement("button");
            buildBtn.textContent = `Build ${formatBuildingLabel(buildingType)} 💰${cost}`;
            buildBtn.onclick = () => performBuild(id, buildingType);
            container.appendChild(buildBtn);
        });
    }

    // Attack Action
    if (type === "spearman" || type === "swordsman") {
        const attackBtn = document.createElement("button");
        attackBtn.textContent = "Attack";
        attackBtn.onclick = () => showAttackTargets(selectedUnit);
        container.appendChild(attackBtn);
    }
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

function showAttackTargets(unitGroup) {
    clearHighlights();
    const q = Number(unitGroup.dataset.q);
    const r = Number(unitGroup.dataset.r);
    const unitId = unitGroup.dataset.id;

    const neighbors = [
        [1, 0], [1, -1], [0, -1], [-1, 0], [-1, 1], [0, 1]
    ];

    neighbors.forEach(([dq, dr]) => {
        const targetQ = q + dq;
        const targetR = r + dr;
        const hex = document.querySelector(`.hex-group[data-q="${targetQ}"][data-r="${targetR}"] .hex`);
        if (!hex) return;

        const enemyUnit = document.querySelector(
            `.unit-group[data-q="${targetQ}"][data-r="${targetR}"]:not([data-owner-id="${currentUserId}"])`
        );
        if (enemyUnit) {
            // The enemy unit's own icon renders on top of the hex, so it
            // intercepts clicks before the hex's own onclick ever fires.
            // Track it as a valid attack target so handleUnitClick can
            // redirect the click into an attack instead of a selection.
            hex.classList.add("highlight-attack");
            hex.onclick = () => performAttack(unitId, enemyUnit.dataset.id);
            activeAttackTargetIds.add(enemyUnit.dataset.id);
        }
    });

    activeAttackSourceId = activeAttackTargetIds.size > 0 ? unitId : null;
}

function showExpandTargets(settlementGroup) {
    clearHighlights();
    const settlementId = settlementGroup.dataset.id;

    // Find all hexes belonging to this settlement
    const ownedHexes = document.querySelectorAll(`.hex-group[data-settlement-id="${settlementId}"]`);
    
    const neighbors = [
        [1, 0], [1, -1], [0, -1], [-1, 0], [-1, 1], [0, 1]
    ];

    const targets = new Set();

    ownedHexes.forEach(ownedGroup => {
        const q = Number(ownedGroup.dataset.q);
        const r = Number(ownedGroup.dataset.r);

        neighbors.forEach(([dq, dr]) => {
            const targetQ = q + dq;
            const targetR = r + dr;
            const targetKey = `${targetQ},${targetR}`;
            
            if (!targets.has(targetKey)) {
                const hex = document.querySelector(`.hex-group[data-q="${targetQ}"][data-r="${targetR}"] .hex`);
                if (hex) {
                    const group = hex.parentElement;
                    const terrain = group.dataset.terrain;
                    const ownerId = group.dataset.ownerId;
                    
                    if (terrain !== "water" && !ownerId) {
                        hex.classList.add("highlight-move");
                        hex.onclick = () => performExpand(settlementId, targetQ, targetR);
                        targets.add(targetKey);
                    }
                }
            }
        });
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
        if (data.status === "ok" || data.status === "queued") {
            closeActionMenu();
        } else {
            alert(data.error);
        }
    } catch (err) {
        console.error(err);
    }
}

function clearHighlights() {
    document.querySelectorAll(".hex.highlight-move, .hex.highlight-attack").forEach(hex => {
        hex.classList.remove("highlight-move", "highlight-attack");
        hex.onclick = null;
    });
    activeAttackSourceId = null;
    activeAttackTargetIds = new Set();
}

async function performAttack(unitId, targetId) {
    const formData = new FormData();
    formData.append("target_id", targetId);
    formData.append("csrfmiddlewaretoken", csrfToken);

    try {
        const response = await fetch(`/games/${gameId}/unit/${unitId}/attack/`, {
            method: "POST",
            body: formData
        });
        const data = await response.json();
        if (data.status === "ok" || data.status === "queued") {
            closeActionMenu();
        } else {
            alert(data.error);
        }
    } catch (err) {
        console.error(err);
    }
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
        if (data.status === "ok" || data.status === "queued") {
            closeActionMenu();
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
        if (data.status === "ok" || data.status === "queued") {
            closeActionMenu();
        } else {
            alert(data.error);
        }
    } catch (err) {
        console.error(err);
    }
}

async function performBuild(unitId, buildingType) {
    const formData = new FormData();
    formData.append("csrfmiddlewaretoken", csrfToken);
    formData.append("type", buildingType);

    try {
        const response = await fetch(`/games/${gameId}/unit/${unitId}/build/`, {
            method: "POST",
            body: formData
        });
        const data = await response.json();
        if (data.status === "ok" || data.status === "queued") {
            closeActionMenu();
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
        if (data.status === "ok" || data.status === "queued") {
            closeActionMenu();
        } else {
            alert(data.error);
        }
    } catch (err) {
        console.error(err);
    }
}

document.addEventListener('DOMContentLoaded', () => {
    renderHexes();
    renderBuildings();
    renderUnits();
    renderSettlements();

    if (currentTurn === 1) {
        centerOnPlayer();
    }

    const timerDisplay = document.getElementById('timer-display');
    const turnDisplay = document.getElementById('turn-display');
    const endTurnBtn = document.getElementById('end-turn-btn');
    const goldDisplay = document.getElementById('gold-display');
    const foodDisplay = document.getElementById('food-display');
    const unitsDisplay = document.getElementById('units-display');

    let gameSocket = null;

    function updateUnits(units) {
        const svg = document.getElementById("map");
        const existingGroups = new Map();
        document.querySelectorAll(".unit-group").forEach(g => {
            existingGroups.set(String(g.dataset.id), g);
        });

        const currentIds = new Set(units.map(u => String(u.id)));

        // Track hexes whose occupants changed so we can relayout them even if
        // no entity remains there to trigger relayoutHex itself (e.g. a unit
        // that moved away or was removed).
        const affectedHexes = new Set();

        // Remove units that no longer exist
        existingGroups.forEach((group, id) => {
            if (!currentIds.has(id)) {
                affectedHexes.add(`${group.dataset.q},${group.dataset.r}`);
                group.remove();
            }
        });

        // Add or update units
        units.forEach(u => {
            let group = existingGroups.get(String(u.id));
            const oldKey = group ? `${group.dataset.q},${group.dataset.r}` : null;
            if (!group) {
                group = document.createElementNS("http://www.w3.org/2000/svg", "g");
                group.setAttribute("class", "unit-group");
                group.setAttribute("id", `unit-${u.id}`);
                // Will be appended in renderSingleUnit
            }

            // Update dataset
            group.dataset.id = u.id;
            group.dataset.type = u.type;
            group.dataset.q = u.q;
            group.dataset.r = u.r;
            group.dataset.color = u.color;
            group.dataset.ownerId = u.owner_id;
            group.dataset.ownerName = u.owner_name;
            group.dataset.ownerNation = u.owner_nation;
            group.dataset.label = u.label;
            group.dataset.lastActionTurn = u.last_action_turn;
            group.dataset.queuedAction = u.queued_action;
            group.dataset.hitpoints = u.hitpoints;
            group.dataset.maxHitpoints = u.max_hitpoints;
            group.dataset.attack = u.attack;
            group.dataset.defense = u.defense;

            const newKey = `${u.q},${u.r}`;
            if (oldKey && oldKey !== newKey) affectedHexes.add(oldKey);
            affectedHexes.add(newKey);

            // Re-render the individual unit (also relayouts its new hex)
            renderSingleUnit(group);
        });

        // Relayout any hex left behind by a removed or moved-away unit.
        affectedHexes.forEach(key => {
            const [hq, hr] = key.split(",");
            relayoutHex(hq, hr);
        });
    }

    function updateSettlements(settlements) {
        const svg = document.getElementById("map");
        const existingGroups = new Map();
        document.querySelectorAll(".settlement-group").forEach(g => {
            existingGroups.set(String(g.dataset.id), g);
        });

        // Add or update settlements
        settlements.forEach(s => {
            let group = existingGroups.get(String(s.id));
            if (!group) {
                group = document.createElementNS("http://www.w3.org/2000/svg", "g");
                group.setAttribute("class", "settlement-group");
                group.setAttribute("id", `settlement-${s.id}`);
                // Will be appended in renderSingleSettlement
            }

            // Update dataset
            group.dataset.id = s.id;
            group.dataset.q = s.q;
            group.dataset.r = s.r;
            group.dataset.color = s.color;
            group.dataset.name = s.name;
            group.dataset.tier = s.tier;
            group.dataset.population = s.population;
            group.dataset.ownerId = s.owner_id;
            group.dataset.ownerName = s.owner_name;
            group.dataset.ownerNation = s.owner_nation;
            group.dataset.lastActionTurn = s.last_action_turn;
            group.dataset.queuedAction = s.queued_action;

            // Re-render the individual settlement
            renderSingleSettlement(group);
        });
    }

    function updateHexes(hexes) {
        hexes.forEach(h => {
            const group = document.querySelector(`.hex-group[data-q="${h.q}"][data-r="${h.r}"]`);
            if (group) {
                group.dataset.owner = h.owner || "";
                group.dataset.ownerId = h.owner_id || "";
                group.dataset.ownerColor = h.owner_color || "";
                group.dataset.settlement = h.settlement || "";
                group.dataset.settlementId = h.settlement_id || "";
                group.dataset.building = h.building || "";
                group.dataset.buildingId = h.building_id || "";
                group.dataset.buildingQueued = h.building_queued ? "true" : "false";
                renderSingleBuilding(group);

                // Update the polygon stroke
                const polygon = group.querySelector("polygon");
                if (polygon) {
                    if (h.owner_color) {
                        polygon.style.setProperty("--owner-color", h.owner_color);
                        polygon.style.setProperty("--owner-stroke-width", "3");
                    } else {
                        polygon.style.removeProperty("--owner-color");
                        polygon.style.removeProperty("--owner-stroke-width");
                    }
                    
                    // Update title
                    const title = polygon.querySelector("title");
                    if (title) {
                        title.textContent = h.owner
                            ? `(${h.q}, ${h.r}) ${group.dataset.terrain} - ${h.owner}${h.settlement ? ' (' + h.settlement + ')' : ''}`
                            : `(${h.q}, ${h.r}) ${group.dataset.terrain}`;
                    }
                }
            }
        });
    }

    function applyGameUpdate(data) {
        if (data.is_finished) {
            window.location.href = gameHistoryUrl;
            return;
        }
        const timerDisplay = document.getElementById('timer-display');
        const turnDisplay = document.getElementById('turn-display');

        // Update remaining time if it's significantly different
        if (Math.abs(data.remaining_time - remainingTime) > 5) {
            remainingTime = data.remaining_time;
            if (timerDisplay) timerDisplay.textContent = remainingTime;
        }

        // Check if turn advanced
        if (data.current_turn > currentTurn) {
            currentTurn = data.current_turn;
            if (turnDisplay) turnDisplay.textContent = currentTurn;
        }

        // Update button state (handled by HTMX now)
        if (data.is_my_turn !== isMyTurn) {
            isMyTurn = data.is_my_turn;
            closeActionMenu(); // Close menu whenever active player changes
        }

        // Update resources (handled by HTMX now)

        // Surgical updates for units, settlements, and hexes
        if (data.hexes) updateHexes(data.hexes);
        if (data.settlements) updateSettlements(data.settlements);
        if (data.units) updateUnits(data.units);

        // Floating damage numbers for any combat resolved this turn
        if (data.combat_events) {
            data.combat_events.forEach(ev => showDamageText(ev.q, ev.r, ev.damage));
        }

        // Update queued actions list (handled by HTMX now)
    }

    function connectGameSocket() {
        if (typeof gameWsUrl === 'undefined') return;
        gameSocket = new WebSocket(gameWsUrl);

        gameSocket.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                if (data.type === 'game_update' && data.payload) {
                    applyGameUpdate(data.payload);
                    // Trigger HTMX to update resource bar and end-turn button
                    document.body.dispatchEvent(new CustomEvent('game-updated', { detail: data.payload }));
                } else if (data.type === 'game_refresh') {
                    console.log('Game refresh requested');
                    document.body.dispatchEvent(new CustomEvent('game-updated'));
                } else if (data.type === 'timer_tick') {
                    remainingTime = data.remaining_time;
                    const timerDisplay = document.getElementById('timer-display');
                    if (timerDisplay) timerDisplay.textContent = remainingTime;
                    
                    if (remainingTime === 0) {
                        document.body.dispatchEvent(new CustomEvent('game-updated'));
                    }
                }
            } catch (err) {
                console.error('Failed to parse game update', err);
            }
        };

        gameSocket.onclose = () => {
            setTimeout(connectGameSocket, 2000);
        };

        gameSocket.onerror = (err) => {
            console.error('Game socket error', err);
            gameSocket.close();
        };
    }

    // Timer countdown
    // Dictated by server ticks via WebSocket (timer_tick message)
    /*
    setInterval(() => {
        if (remainingTime > 0) {
            remainingTime -= 1;
            const timerDisplay = document.getElementById('timer-display');
            if (timerDisplay) timerDisplay.textContent = remainingTime;

            if (remainingTime === 0) {
                // Trigger turn end check by dispatching event that HTMX listens to
                document.body.dispatchEvent(new CustomEvent('game-updated'));
            }
        }
    }, 1000);
    */

    // Connect to WebSocket for updates
    connectGameSocket();

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

    // --- Real-time chat via WebSocket (Django Channels) ---
    const chatOverlay = document.getElementById('chat-overlay');
    const chatMessages = document.getElementById('chat-messages');
    const chatForm = document.getElementById('chat-form');
    const chatInput = document.getElementById('chat-input');
    const toggleChatBtn = document.getElementById('toggle-chat-btn');
    const closeChatBtn = document.getElementById('close-chat-btn');
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

        // Show notification dot if chat is closed and it's not our own message
        if (chatOverlay.style.display === 'none' && msg.user !== currentUsername) {
            const dot = document.getElementById('chat-notification-dot');
            if (dot) dot.style.display = 'block';
        }
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

    if (toggleChatBtn) {
        toggleChatBtn.addEventListener('click', () => {
            const isHidden = chatOverlay.style.display === 'none';
            chatOverlay.style.display = isHidden ? 'block' : 'none';
            if (isHidden) {
                chatMessages.scrollTop = chatMessages.scrollHeight;
                chatInput.focus();
                
                // Hide notification dot when opening chat
                const dot = document.getElementById('chat-notification-dot');
                if (dot) dot.style.display = 'none';
            }
        });
    }

    if (closeChatBtn) {
        closeChatBtn.addEventListener('click', () => {
            chatOverlay.style.display = 'none';
        });
    }

    if (chatMessages) {
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }

    // Draggable action menu
    const actionMenu = document.getElementById('action-menu');
    const dragHandle = document.getElementById('action-menu-handle');
    let isDragging = false;
    let dragStartX, dragStartY;
    let menuStartX, menuStartY;

    dragHandle.addEventListener('mousedown', (e) => {
        isDragging = true;
        isMenuDragged = true;
        dragStartX = e.clientX;
        dragStartY = e.clientY;
        menuStartX = parseInt(actionMenu.style.left) || 0;
        menuStartY = parseInt(actionMenu.style.top) || 0;
        e.preventDefault();
    });

    document.addEventListener('mousemove', (e) => {
        if (!isDragging) return;
        
        const dx = e.clientX - dragStartX;
        const dy = e.clientY - dragStartY;
        
        actionMenu.style.left = `${menuStartX + dx}px`;
        actionMenu.style.top = `${menuStartY + dy}px`;
    });

    function centerOnHex(q, r) {
        const mapWrap = document.querySelector('.map-wrap');
        if (!mapWrap) return;
    
        const pos = axialToPixel(q, r);
    
        // We want to center the point (pos.x * scale, pos.y * scale) in the viewport
        mapWrap.scrollLeft = (pos.x * scale) - (mapWrap.clientWidth / 2);
        mapWrap.scrollTop = (pos.y * scale) - (mapWrap.clientHeight / 2);
    }

    function centerOnPlayer() {
        const playerSettlement = document.querySelector(`.settlement-group[data-owner-id="${currentUserId}"]`);
        const playerUnit = document.querySelector(`.unit-group[data-owner-id="${currentUserId}"]`);
    
        const target = playerSettlement || playerUnit;
        if (target) {
            const q = Number(target.dataset.q);
            const r = Number(target.dataset.r);
            centerOnHex(q, r);
        }
    }

    document.addEventListener('mouseup', () => {
        isDragging = false;
    });

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
                if (actionMenu.style.display === 'block' && selectedUnit && !isMenuDragged) {
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
