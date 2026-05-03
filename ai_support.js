/**
 * AI Integration for Injera Board Game
 * 
 * INSTRUCTIONS:
 * 1. Add this script to your injera_game.html BEFORE the closing </body> tag:
 *    <script src="ai_support.js"></script>
 * 
 * 2. In your playersData initialization, add these fields to each player:
 *    "isAI": false,  (or true for AI players)
 *    "aiLevel": null  (or "neural" for Neural AI)
 * 
 * 3. Modify nextTurn() to call handleAITurnIfNeeded() at the end
 * 
 * 4. Change Key Sir scoring to 3 points (search for "Key Sir" in testEat function)
 */

// ==================== AI CONFIGURATION ====================

const AI_CONFIG = {
    serverUrl: 'http://localhost:5000',
    enabled: true,
    autoPlay: true,  // Automatically play AI moves
    thinkingDelay: 800  // Delay in ms before AI makes move (for visualization)
};

// State tracking
let aiProcessing = false;
let aiTurnGeneration = 0; // Incremented on undo; AI aborts if generation changes mid-flight

// ==================== AI TURN HANDLING ====================

async function handleAITurnIfNeeded() {
    const currentPlayer = playersData[currentPlayerIdx];
    
    if (!currentPlayer.isAI || !AI_CONFIG.enabled || !AI_CONFIG.autoPlay) {
        return false;  // Not an AI turn
    }
    
    if (aiProcessing) {
        return false;  // Already processing
    }
    
    console.log(`[AI] Turn: ${currentPlayer.name} (${currentPlayer.aiLevel})`);
    
    // Wait a bit for visual effect
    await new Promise(resolve => setTimeout(resolve, AI_CONFIG.thinkingDelay));
    
    await handleAITurn();
    return true;
}

async function handleAITurn() {
    const currentPlayer = playersData[currentPlayerIdx];
    const myGeneration = aiTurnGeneration; // snapshot; undo increments this
    aiProcessing = true;
    
    // Show thinking indicator as a temporary overlay
    let thinkingEl = document.createElement('div');
    thinkingEl.className = 'ai-thinking';
    thinkingEl.style.cssText = 'position:fixed;top:10px;right:10px;background:#fff;padding:8px 14px;border-radius:8px;box-shadow:0 2px 8px rgba(0,0,0,0.3);z-index:9999;';
    thinkingEl.textContent = `[AI] ${currentPlayer.name} is thinking…`;
    document.body.appendChild(thinkingEl);

    try {
        // Prepare game state for AI
        const gameState = {
            num_players: numPlayers,
            current_player_idx: currentPlayerIdx,
            board: boardData,
            players: playersData.map((p, i) => ({
                ...p,
                waterRefilledThisTurn: waterRefilledThisTurn[i]
            })),
            deck: deckData,
            reachable_by_player: reachableByPlayer,
            final_round_active: finalRoundActive,
            final_round_start_player: finalRoundStartPlayer,
            game_over: false,
            // Supply consecutive_no_eat_turns so the server can apply the critical-eating constraint
            consecutive_no_eat_turns: (typeof noEatStreakTurns !== 'undefined') ? noEatStreakTurns : 0
        };
        
        // Call AI server
        const response = await fetch(`${AI_CONFIG.serverUrl}/ai_move`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                game_state: gameState,
                ai_level: currentPlayer.aiLevel || 'neural',
                total_dishes_at_start: (typeof totalDishesAtStart !== 'undefined') ? totalDishesAtStart : 0
            })
        });
        
        if (!response.ok) {
            throw new Error(`AI server returned ${response.status}: ${response.statusText}`);
        }

        const data = await response.json();
        const action = data.action;
        
        console.log('AI chose:', action);
        console.log('AI message:', data.message);
        
        // DEBUG: Log action statistics
        if (data.debug) {
            console.log('=== AI TURN DEBUG ===');
            console.log('Player:', data.debug.player_name);
            console.log('Hand size:', data.debug.hand_size);
            console.log('Hand cards:', data.debug.hand_cards);
            console.log('Total legal actions:', data.debug.total_legal_actions);
            console.log('Actions by type:', data.debug.actions_by_type);
            console.log('Chosen action:', data.debug.chosen_action);
            if (data.debug.top_actions) {
                console.log('Top actions:', data.debug.top_actions);
            }
            console.log('===================');
        }
        
        // Abort if undo happened while the server request was in flight
        if (aiTurnGeneration !== myGeneration) { aiProcessing = false; return; }

        // Execute the AI's action
        await executeAIAction(action);

        // Redraw the board immediately so the visual state reflects the action
        // before the message panel appears (otherwise tiles appear unchanged).
        if (typeof drawBoard === 'function') drawBoard();
        if (typeof updatePlayersPanel === 'function') updatePlayersPanel();

        // Check if turn should end due to Coffee/Beer finished
        const shouldEndDueToDrinkFinished = window.aiShouldEndTurnAfterAction;
        if (shouldEndDueToDrinkFinished) {
            window.aiShouldEndTurnAfterAction = false;
        }

        const isTurnOver = action.action_type === 'end_turn' || shouldEndDueToDrinkFinished;

        // Abort if undo happened during executeAIAction
        if (aiTurnGeneration !== myGeneration) { aiProcessing = false; return; }

        // Show AI action message and wait for user to click Continue
        await new Promise(resolve => {
            const panel = document.getElementById('aiMessagePanel');
            if (!panel) { resolve(); return; }
            const label = isTurnOver ? ' [turn ended]' : '';
            // In clean mode show only the action description (first line); strip probabilities and plan
            const displayMsg = window.cleanMode ? data.message.split('\n')[0] : data.message;
            panel.innerHTML =
                `<strong>[AI] ${playersData[currentPlayerIdx].name}${label}</strong>\n${displayMsg}\n` +
                `<button style="margin-top:8px;padding:5px 14px;background:#667eea;color:#fff;border:none;border-radius:6px;cursor:pointer;font-size:13px;">Continue ▶</button>`;
            panel.style.display = 'block';
            panel.querySelector('button').addEventListener('click', resolve, {once: true});
        });

        // Restore status
        thinkingEl.remove();
        updateGameStatus();

        if (isTurnOver) {
            setTimeout(() => {
                aiProcessing = false;
                nextTurn();
            }, 300);
        } else {
            // AI wants to keep playing - take another action
            setTimeout(() => {
                aiProcessing = false;
                handleAITurn();
            }, 300);
        }
        
    } catch (error) {
        console.error('AI Error:', error);
        thinkingEl.remove();
        alert(`[ERROR] AI Error: ${error.message}\n\nMake sure the AI server is running:\n  python server.py\n\nThen try again or play manually.`);
        aiProcessing = false;
    }
}

// ==================== AI ACTION EXECUTOR ====================

async function executeAIAction(action) {
    console.log('Executing AI action:', action.action_type);
    
    switch (action.action_type) {
        case 'eat_dish':
            await executeAIEatDish(action);
            break;
        case 'eat_empty_tile':
            await executeAIEatEmptyTile(action);
            break;
        case 'play_drink':
            executeAIPlayDrink(action);
            break;
        case 'drink_token':
            executeAIDrinkToken(action);
            break;
        case 'play_rotate':
            executeAIRotate(action);
            break;
        case 'add_tahini':
            executeAITahini(action);
            break;
        case 'add_awaze':
            executeAIAwaze(action);
            break;
        case 'discard_redraw':
            executeAIDiscardRedraw(action);
            break;
        case 'end_turn':
            // Just end turn
            break;
        default:
            console.warn('Unknown AI action type:', action.action_type);
    }
    
    updatePlayersPanel();
    updateGameStatus();
    drawBoard();
}

// ==================== HELPERS ====================

function findCardIndexByType(hand, discardType) {
    /**
     * Find the index of a card in hand matching the given discard type.
     * discardType: 'Clean Injera', 'Rotate', 'Tahini', 'Awaze', 'Coffee', 'Beer', or 'Water'
     */
    for (let i = 0; i < hand.length; i++) {
        const c = hand[i];
        if (discardType === 'Clean Injera' && c.type === 'Clean Injera') return i;
        if (discardType === 'Rotate' && c.type === 'Rotate') return i;
        if (discardType === 'Tahini' && c.type === 'Tahini') return i;
        if (['Awaze', 'Add Awaze'].includes(discardType) && c.type === 'Awaze') return i;
        if (['Coffee', 'Beer', 'Water'].includes(discardType) && c.type === 'Drink') {
            const drinkName = (c.name || '').replace('Order ', '');
            if (drinkName === discardType) return i;
        }
    }
    return -1;
}

function countCardsByDiscardType(hand) {
    /**
     * Count cards by discard-type (drink cards split by drink name, others by card type).
     * Returns e.g. { 'Clean Injera': 2, 'Coffee': 1, 'Rotate': 1 }
     */
    const counts = {};
    for (const c of hand) {
        let key;
        if (c.type === 'Drink') {
            key = (c.name || '').replace('Order ', '');
        } else {
            key = c.type;
        }
        counts[key] = (counts[key] || 0) + 1;
    }
    return counts;
}

// ==================== SPECIFIC ACTION EXECUTORS ====================

async function executeAIEatDish(action) {
    const currentPlayer = playersData[currentPlayerIdx];
    const tile = boardData.find(t => t.q === action.tile_coord[0] && t.r === action.tile_coord[1]);

    if (!tile) {
        console.error('Tile not found:', action.tile_coord);
        return;
    }

    // 1. Discard the specified card type
    if (action.discard_card_type && currentPlayer.hand.length > 0) {
        const discardIdx = findCardIndexByType(currentPlayer.hand, action.discard_card_type);
        if (discardIdx >= 0) {
            currentPlayer.hand.splice(discardIdx, 1);
            console.log(`AI discarded ${action.discard_card_type}, hand now:`, currentPlayer.hand.length);
        }
    }

    // 2. Calculate and award points
    const dishName = tile.dish;
    let dishValue = 0;
    if (['Gomen', 'Azifa', 'Shiro'].includes(dishName)) dishValue = 1;
    else if (['Kik Alicha', 'Misir Wot', 'Tikel Gomen'].includes(dishName)) dishValue = 2;
    else if (dishName === 'Key Sir') dishValue = 3;

    const tahiniValue = tile.tahini || 0;
    currentPlayer.score += dishValue + tahiniValue;

    // 3. Track eating
    currentPlayer.eaten.push(dishName);
    if (!currentPlayer.dishCounts) currentPlayer.dishCounts = {};
    currentPlayer.dishCounts[dishName] = (currentPlayer.dishCounts[dishName] || 0) + 1;
    dishEatenThisTurn = true; // Reset stalemate counter in nextTurn()

    // Track tahini consumed
    if (tahiniValue > 0) {
        currentPlayer.tahiniConsumed = (currentPlayer.tahiniConsumed || 0) + tahiniValue;
    }

    // 4. Handle hot using the exact recipe from the action
    const wasHot = tile.hot;
    const isBerbere = dishName === 'Key Sir';

    // Track super-hot count (Key Sir only, mirroring human testEat)
    if (isBerbere) {
        currentPlayer.superHotCount = (currentPlayer.superHotCount || 0) + 1;
    }

    // Track hot/non-hot dish counts for special cards — exact mirror of HTML testEat logic
    const isBerbereDish = isBerbere;
    const dishInherentlyHot = (dishName === 'Kik Alicha' || dishName === 'Misir Wot' || dishName === 'Tikel Gomen' || isBerbereDish);
    const dishCountsAsHot = dishInherentlyHot || (tile.awaze || 0) > 0;
    if (dishCountsAsHot && !isBerbereDish) {
        currentPlayer.hotDishesEaten = (currentPlayer.hotDishesEaten || 0) + 1;
        currentPlayer.totalHotEaten = (currentPlayer.totalHotEaten || 0) + 1;
    } else if (isBerbereDish) {
        currentPlayer.totalHotEaten = (currentPlayer.totalHotEaten || 0) + 1;
    } else {
        currentPlayer.nonHotDishesEaten = (currentPlayer.nonHotDishesEaten || 0) + 1;
    }
    const dishFullHeat = (isBerbere ? 2 : (tile.hot ? 1 : 0)) + (tile.awaze || 0);
    const dishTahini = tile.tahini || 0;
    const hotDishLevel = Math.max(0, dishFullHeat - dishTahini);
    const excessDishTahini = Math.max(0, dishTahini - dishFullHeat);

    let hotTileLevel = 0;
    let excessTileTahini = 0;
    if (action.resource_type === 'tile' && action.resource_tile_coord) {
        const emptyTile = boardData.find(t =>
            t.q === action.resource_tile_coord[0] && t.r === action.resource_tile_coord[1]);
        if (emptyTile && emptyTile.hotToken) {
            const isCenter = Math.abs(emptyTile.q) <= 1 && Math.abs(emptyTile.r) <= 1 &&
                            Math.abs(emptyTile.q + emptyTile.r) <= 1;
            const rawTileHeat = isCenter ? 2 : 1;
            const tileTahini = emptyTile.tahini || 0;
            const tileFullHeat = rawTileHeat + (emptyTile.awaze || 0);
            hotTileLevel = Math.max(0, tileFullHeat - tileTahini);
            excessTileTahini = Math.max(0, tileTahini - tileFullHeat);
        }
    }

    // Cross-reduction: excess tahini from one tile cools the other's remaining heat
    const adjDishHot = Math.max(0, hotDishLevel - excessTileTahini);
    const adjTileHot = Math.max(0, hotTileLevel - excessDishTahini);
    const totalHot = adjDishHot + adjTileHot;
    if (totalHot > 0) {
        handleAIHotByRecipe(currentPlayer, action.num_drink_tokens_for_hot || 0, totalHot);
    }

    // 5. Consume resource (AFTER hot handling!)
    if (action.resource_type === 'card') {
        const injeraIdx = currentPlayer.hand.findIndex(c => c.type === 'Clean Injera');
        if (injeraIdx >= 0) {
            currentPlayer.hand.splice(injeraIdx, 1);
            console.log('AI used injera card');
        }
    } else if (action.resource_type === 'tile') {
        const emptyTile = boardData.find(t =>
            t.q === action.resource_tile_coord[0] && t.r === action.resource_tile_coord[1]);
        if (emptyTile) {
            const emptyTileTahini = emptyTile.tahini || 0;
            currentPlayer.score += emptyTileTahini;
            if (emptyTileTahini > 0) {
                currentPlayer.tahiniConsumed = (currentPlayer.tahiniConsumed || 0) + emptyTileTahini;
            }
            emptyTile.removed = true;
            console.log('AI used empty tile');
        }
    }

    // 6. Mark tile as empty
    tile.empty = true;
    tile.dish = null;
    tile.tahini = 0;
    tile.awaze = 0;

    if (wasHot || dishName === 'Key Sir') {
        tile.hotToken = true;
        tile.hot = false;
    }

    updateCanEatEmpty();

    // Check if last dish
    const dishesRemaining = boardData.filter(t => !t.empty && !t.removed).length;
    if (dishesRemaining === 0 && !finalRoundActive) {
        finalRoundActive = true;
        finalRoundStartPlayer = currentPlayerIdx;
    }
}

function handleAIHotByRecipe(currentPlayer, numDrinkTokens, totalHot) {
    /**
     * Handle hot using the exact recipe specified by the action.
     * Uses numDrinkTokens drink tokens first, then injera for the rest.
     * Hand refills (Coffee/Water) are deferred until after injera discards.
     */
    let deferredDrawTarget = null;

    // 1. Use the specified number of drink tokens
    for (let i = 0; i < numDrinkTokens; i++) {
        const activeDrink = currentPlayer.drinks.find(d => d.tokens > 0);
        if (activeDrink) {
            activeDrink.tokens--;

            if (activeDrink.tokens === 0) {
                const drinkIdx = currentPlayer.drinks.indexOf(activeDrink);
                const result = handleDrinkFinished(currentPlayer, activeDrink.type, true);
                currentPlayer.drinks.splice(drinkIdx, 1);
                console.log('AI finished drink:', activeDrink.type, result.message);
                if (result.shouldEndTurn) {
                    window.aiShouldEndTurnAfterAction = true;
                }
                if (result.deferredDrawTarget != null) {
                    deferredDrawTarget = Math.max(deferredDrawTarget ?? 0, result.deferredDrawTarget);
                }
            }
        }
    }

    // 2. Use injera cards for the rest
    const injeraForHot = totalHot - numDrinkTokens;
    for (let i = 0; i < injeraForHot; i++) {
        const injeraIdx = currentPlayer.hand.findIndex(c => c.type === 'Clean Injera');
        if (injeraIdx >= 0) {
            currentPlayer.hand.splice(injeraIdx, 1);
            console.log('AI used injera for hot handling');
        }
    }

    // 3. Apply deferred hand refill AFTER injera discards
    if (deferredDrawTarget !== null && !finalRoundActive) {
        const toDraw = deferredDrawTarget - currentPlayer.hand.length;
        if (toDraw > 0) drawCards(currentPlayer, toDraw);
    }
}

async function executeAIEatEmptyTile(action) {
    const currentPlayer = playersData[currentPlayerIdx];
    const tile = boardData.find(t => t.q === action.tile_coord[0] && t.r === action.tile_coord[1]);

    if (!tile) return;

    // 1. Discard the specified card type
    if (action.discard_card_type && currentPlayer.hand.length > 0) {
        const discardIdx = findCardIndexByType(currentPlayer.hand, action.discard_card_type);
        if (discardIdx >= 0) {
            currentPlayer.hand.splice(discardIdx, 1);
            console.log(`AI discarded ${action.discard_card_type} for eating empty tile, hand now:`, currentPlayer.hand.length);
        }
    }

    // 2. Handle hot using the exact recipe from the action
    {
        const tileAwaze = tile.awaze || 0;
        const tileTahini = tile.tahini || 0;
        let rawHot = 0;
        if (tile.hotToken) {
            const isBerbereToken = Math.abs(tile.q) <= 1 && Math.abs(tile.r) <= 1 &&
                                  Math.abs(tile.q + tile.r) <= 1;
            rawHot = isBerbereToken ? 2 : 1;
        }
        const hotLevel = Math.max(0, rawHot + tileAwaze - tileTahini);
        if (hotLevel > 0) handleAIHotByRecipe(currentPlayer, action.num_drink_tokens_for_hot || 0, hotLevel);
    }

    // 3. Award tahini points
    const emptyTileTahini = tile.tahini || 0;
    currentPlayer.score += emptyTileTahini;
    if (emptyTileTahini > 0) {
        currentPlayer.tahiniConsumed = (currentPlayer.tahiniConsumed || 0) + emptyTileTahini;
    }

    // 4. Remove tile (EAT_EMPTY_TILE does NOT count as eating a dish —
    //    the stalemate counter is not reset here)
    tile.removed = true;
    updateCanEatEmpty();
}

function executeAIPlayDrink(action) {
    const currentPlayer = playersData[currentPlayerIdx];

    // Find card by drink type (not by index)
    const drinkType = action.drink_card_type;
    if (!drinkType) return;

    const cardIdx = findCardIndexByType(currentPlayer.hand, drinkType);
    if (cardIdx < 0) return;

    currentPlayer.hand.splice(cardIdx, 1);
    currentPlayer.drinks.push({ type: drinkType, tokens: 3 });
}

function executeAIDrinkToken(action) {
    const currentPlayer = playersData[currentPlayerIdx];
    const drink = currentPlayer.drinks[action.drink_index];
    
    if (!drink) return;
    
    drink.tokens--;
    // No points per voluntary token — finish bonus is awarded by handleDrinkFinished
    const points = 0;
    currentPlayer.score += points;
    
    if (drink.tokens === 0) {
        const result = handleDrinkFinished(currentPlayer, drink.type);
        currentPlayer.drinks.splice(action.drink_index, 1);
        console.log('AI finished drink:', drink.type, result.message);

        // If Coffee/Beer finished (or 2nd Water), set flag to end turn
        if (result.shouldEndTurn) {
            window.aiShouldEndTurnAfterAction = true;
        }
    }
}

function executeAIRotate(action) {
    const currentPlayer = playersData[currentPlayerIdx];
    currentPlayer.hand.splice(action.card_index, 1);
    
    const clockwise = action.rotation_direction === 'clockwise';
    
    boardData.forEach(tile => {
        const oldQ = tile.q;
        const oldR = tile.r;
        
        if (clockwise) {
            tile.q = -oldR;
            tile.r = oldQ + oldR;
        } else {
            tile.q = oldQ + oldR;
            tile.r = -oldQ;
        }
    });
    
    updateCanEatEmpty();
    calculateReachableTiles();
}

function executeAITahini(action) {
    const currentPlayer = playersData[currentPlayerIdx];

    const cardIdx = currentPlayer.hand.findIndex(c => c.name === 'Tahini');
    if (cardIdx < 0) { console.error('AI has no Tahini card'); return; }
    currentPlayer.hand.splice(cardIdx, 1);

    const tile = boardData.find(t => t.q === action.tile_coord[0] && t.r === action.tile_coord[1]);
    if (!tile) return;

    const allTriangles = getTrianglesContaining(tile.q, tile.r);
    const orientation = action.triangle_orientation; // 'left' or 'right'

    let chosen = null;
    for (const tri of allTriangles) {
        const sorted = [...tri].sort((a, b) => a.r !== b.r ? a.r - b.r : a.q - b.q);
        const top = sorted[0];
        if (top.q !== tile.q || top.r !== tile.r) continue;
        const avgQ = (sorted[1].q + sorted[2].q) / 2;
        const isLeft = avgQ < top.q;
        if ((orientation === 'left' && isLeft) || (orientation === 'right' && !isLeft)) {
            chosen = tri;
            break;
        }
    }

    if (!chosen) {
        chosen = allTriangles[0];
        console.warn('AI tahini: triangle orientation not found, using first available');
    }

    if (chosen) {
        chosen.forEach(t => {
            if (!t.removed) t.tahini = (t.tahini || 0) + 1;
        });
    }
}

function executeAIAwaze(action) {
    const currentPlayer = playersData[currentPlayerIdx];

    // Remove the Awaze card from hand
    const cardIdx = currentPlayer.hand.findIndex(c => c.name === 'Add Awaze');
    if (cardIdx < 0) {
        console.error('AI has no Add Awaze card');
        return;
    }
    currentPlayer.hand.splice(cardIdx, 1);

    const tile = boardData.find(t => t.q === action.tile_coord[0] && t.r === action.tile_coord[1]);
    if (!tile) return;

    // Find all triangles with this tile as the top (smallest r)
    const allTriangles = getTrianglesContaining(tile.q, tile.r);
    const orientation = action.triangle_orientation; // 'left' or 'right'

    let chosen = null;
    for (const tri of allTriangles) {
        const sorted = [...tri].sort((a, b) => a.r !== b.r ? a.r - b.r : a.q - b.q);
        const top = sorted[0];
        if (top.q !== tile.q || top.r !== tile.r) continue;
        const avgQ = (sorted[1].q + sorted[2].q) / 2;
        const isLeft = avgQ < top.q;
        if ((orientation === 'left' && isLeft) || (orientation === 'right' && !isLeft)) {
            chosen = tri;
            break;
        }
    }

    if (!chosen) {
        // Fallback: use first available triangle
        chosen = allTriangles[0];
        console.warn('AI awaze: triangle orientation not found, using first available');
    }

    if (chosen) {
        chosen.forEach(t => {
            if (!t.removed) {
                t.awaze = (t.awaze || 0) + 1;
            }
        });
    }

}

function executeAIDiscardRedraw(action) {
    const currentPlayer = playersData[currentPlayerIdx];
    const n = currentPlayer.hand.length;
    if (n === 0) {
        console.warn('AI discard_redraw: hand is empty');
        return;
    }
    currentPlayer.hand = [];
    if (n - 1 > 0) drawCards(currentPlayer, n - 1);
}

// ==================== HELPER: Update Player Panel to Show AI ====================

const originalUpdatePlayersPanel = window.updatePlayersPanel;
window.updatePlayersPanel = function() {
    if (originalUpdatePlayersPanel) {
        originalUpdatePlayersPanel();
    }
    
    // Add AI indicator to player cards
    document.querySelectorAll('.player-card').forEach((card, idx) => {
        if (playersData[idx] && playersData[idx].isAI) {
            card.classList.add('ai');
            const h2 = card.querySelector('h2');
            if (h2 && !h2.textContent.includes('[AI]')) {
                h2.textContent = h2.textContent.replace(playersData[idx].name, 
                    `[AI] ${playersData[idx].name} (${playersData[idx].aiLevel || 'AI'})`);
            }
        }
    });
};

// ==================== GAME RECORDING ====================
// Records human player actions for behavioral cloning training
// Usage: Call recordingStart() at game start, recordingStop() at game end
// Each human action is automatically captured via recordHumanAction()

let recordingActive = false;

function getGameStateSnapshot() {
    // Deep copy to capture state BEFORE action modifies it
    return JSON.parse(JSON.stringify({
        num_players: numPlayers,
        current_player_idx: currentPlayerIdx,
        board: boardData,
        players: playersData,
        deck: deckData,
        reachable_by_player: reachableByPlayer,
        final_round_active: finalRoundActive,
        final_round_start_player: finalRoundStartPlayer,
        game_over: false
    }));
}

async function recordingStart() {
    try {
        // Identify which players are human
        const humanIds = playersData
            .map((p, i) => (!p.isAI ? i : -1))
            .filter(i => i >= 0);

        const response = await fetch(`${AI_CONFIG.serverUrl}/start_recording`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                num_players: numPlayers,
                human_player_ids: humanIds
            })
        });
        const data = await response.json();
        recordingActive = true;
        console.log('[REC] Recording started:', data.game_id);
    } catch (e) {
        console.warn('[REC] Recording unavailable (server not running). Game will not be recorded.');
    }
}

async function recordingStop() {
    if (!recordingActive) return;
    try {
        // Use calculateFinalScores() to include variety and completion bonuses
        const results = (typeof calculateFinalScores === 'function') ? calculateFinalScores() : null;
        let finalScores, winner, bonusDetails;

        if (results) {
            finalScores = results.map(r => r.finalScore);
            winner = results.reduce((best, r, i) =>
                r.finalScore > (results[best] || {finalScore: -1}).finalScore ? i : best, 0);
            bonusDetails = results.map(r => ({
                base_score: r.score,
                variety_bonus: r.varietyBonus,
                completion_bonus: r.completionBonus,
                completion_details: r.completionDetails,
                dish_types: r.dishTypes
            }));
        } else {
            // Fallback: base scores only
            finalScores = playersData.map(p => p.score);
            winner = playersData.reduce((best, p, i) =>
                p.score > (playersData[best] || {score: -1}).score ? i : best, 0);
            bonusDetails = null;
        }

        const response = await fetch(`${AI_CONFIG.serverUrl}/stop_recording`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                final_scores: finalScores,
                winner: winner,
                bonus_details: bonusDetails
            })
        });
        const data = await response.json();
        recordingActive = false;
        console.log(`[REC] Recording saved: ${data.file} (${data.total_steps} steps)`);
    } catch (e) {
        console.error('[REC] Failed to stop recording:', e);
    }
}

async function recordingAutoStop() {
    await recordingStop();
}

async function recordHumanAction(action) {
    // Only record if recording is active and current player is human
    if (!recordingActive) return;
    const currentPlayer = playersData[currentPlayerIdx];
    if (currentPlayer.isAI) return;

    try {
        await fetch(`${AI_CONFIG.serverUrl}/record_action`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                game_state: window._preActionState,
                action: action,
                player_id: currentPlayerIdx
            })
        });
    } catch (e) {
        console.error('[REC] Failed to record action:', e);
    }
}

// Infer what action was taken by comparing pre/post game states
// Produces type-based actions with discard_card_type, num_drink_tokens_for_hot, drink_card_type
function inferAction(preState, postState, playerId) {
    const pre = preState;
    const post = postState;
    const prePlayer = pre.players[playerId];
    const postPlayer = post.players[playerId];

    // Helper: compute drink tokens consumed (pre total - post total)
    function getDrinkTokensConsumed() {
        const preTotal = (prePlayer.drinks || []).reduce((sum, d) => sum + d.tokens, 0);
        const postTotal = (postPlayer.drinks || []).reduce((sum, d) => sum + d.tokens, 0);
        return Math.max(0, preTotal - postTotal);
    }

    // Helper: determine which card TYPE was discarded, given how many injera
    // were used for eating resource + hot handling
    function inferDiscardCardType(totalInjeraUsed) {
        const preCounts = countCardsByDiscardType(prePlayer.hand);
        const postCounts = countCardsByDiscardType(postPlayer.hand);

        // Compute deltas (pre - post) for each type
        const allTypes = new Set([...Object.keys(preCounts), ...Object.keys(postCounts)]);
        const deltas = {};
        for (const type of allTypes) {
            const delta = (preCounts[type] || 0) - (postCounts[type] || 0);
            if (delta > 0) deltas[type] = delta;
        }

        // Injera delta includes: injera for eating + injera for hot + maybe discard
        const injDelta = deltas['Clean Injera'] || 0;
        if (injDelta > totalInjeraUsed) {
            // Discard was an injera card
            return 'Clean Injera';
        }

        // Look for a non-injera card that was removed
        for (const [type, delta] of Object.entries(deltas)) {
            if (type !== 'Clean Injera' && delta > 0) {
                return type;
            }
        }

        // Fallback: if we can't determine, return null
        return null;
    }

    // Check for eaten dish: a tile that had a dish now is empty
    for (let i = 0; i < pre.board.length; i++) {
        const preTile = pre.board[i];
        const postTile = post.board[i];
        if (preTile.dish && !postTile.dish && postTile.empty) {
            const tileCoord = [preTile.q, preTile.r];

            // Determine resource type: did an empty tile get removed?
            let resourceType = 'card';
            let resourceTileCoord = null;
            for (let j = 0; j < pre.board.length; j++) {
                const preT = pre.board[j];
                const postT = post.board[j];
                if (preT.empty && !preT.removed && postT.removed && j !== i) {
                    resourceType = 'tile';
                    resourceTileCoord = [preT.q, preT.r];
                    break;
                }
            }

            // Compute hot level
            const isBerbere = preTile.dish === 'Key Sir';
            const hotDishLevel = isBerbere ? 2 : (preTile.hot ? 1 : 0);
            let hotTileLevel = 0;
            if (resourceType === 'tile' && resourceTileCoord) {
                const emptyTile = pre.board.find(t =>
                    t.q === resourceTileCoord[0] && t.r === resourceTileCoord[1]);
                if (emptyTile && emptyTile.hotToken) {
                    const isCenter = Math.abs(emptyTile.q) <= 1 &&
                                    Math.abs(emptyTile.r) <= 1 &&
                                    Math.abs(emptyTile.q + emptyTile.r) <= 1;
                    hotTileLevel = isCenter ? 2 : 1;
                }
            }
            const totalHot = hotDishLevel + hotTileLevel;

            // Drink tokens consumed for hot handling
            const drinkTokensConsumed = getDrinkTokensConsumed();
            const numDrinkTokensForHot = Math.min(drinkTokensConsumed, totalHot);

            // Injera used: for eating resource + for hot
            const injeraForEating = resourceType === 'card' ? 1 : 0;
            const injeraForHot = totalHot - numDrinkTokensForHot;
            const totalInjeraUsed = injeraForEating + injeraForHot;

            // Determine discarded card type
            const discardCardType = inferDiscardCardType(totalInjeraUsed);

            return {
                action_type: 'eat_dish',
                player_id: playerId,
                tile_coord: tileCoord,
                resource_type: resourceType,
                resource_tile_coord: resourceTileCoord,
                discard_card_type: discardCardType,
                num_drink_tokens_for_hot: numDrinkTokensForHot
            };
        }
    }

    // Check for eaten empty tile: an empty tile that was NOT removed is now removed
    for (let i = 0; i < pre.board.length; i++) {
        const preTile = pre.board[i];
        const postTile = post.board[i];
        if (preTile.empty && !preTile.removed && postTile.removed) {
            // Compute hot level from hot token
            let hotLevel = 0;
            if (preTile.hotToken) {
                const isCenter = Math.abs(preTile.q) <= 1 && Math.abs(preTile.r) <= 1 &&
                                Math.abs(preTile.q + preTile.r) <= 1;
                hotLevel = isCenter ? 2 : 1;
            }

            const drinkTokensConsumed = getDrinkTokensConsumed();
            const numDrinkTokensForHot = Math.min(drinkTokensConsumed, hotLevel);
            const injeraForHot = hotLevel - numDrinkTokensForHot;
            const discardCardType = inferDiscardCardType(injeraForHot);

            return {
                action_type: 'eat_empty_tile',
                player_id: playerId,
                tile_coord: [preTile.q, preTile.r],
                discard_card_type: discardCardType,
                num_drink_tokens_for_hot: numDrinkTokensForHot
            };
        }
    }

    // Check for new drink ordered (type-based, not index-based)
    if (postPlayer.drinks.length > prePlayer.drinks.length) {
        const newDrink = postPlayer.drinks[postPlayer.drinks.length - 1];
        return {
            action_type: 'play_drink',
            player_id: playerId,
            drink_card_type: newDrink.type  // 'Coffee', 'Beer', or 'Water'
        };
    }

    // Check for drink token consumed
    if (prePlayer.drinks.length > 0) {
        for (let i = 0; i < prePlayer.drinks.length; i++) {
            const preDrink = prePlayer.drinks[i];
            const postDrink = postPlayer.drinks.find(d => d.type === preDrink.type);
            if (!postDrink || postDrink.tokens < preDrink.tokens) {
                return {
                    action_type: 'drink_token',
                    player_id: playerId,
                    drink_index: i
                };
            }
        }
    }

    // Check for board rotation (tile coordinates changed)
    if (pre.board.length > 0 && post.board.length > 0) {
        const preFirst = pre.board[0];
        const postFirst = post.board[0];
        if (preFirst.q !== postFirst.q || preFirst.r !== postFirst.r) {
            const expectedCW_q = -preFirst.r;
            const expectedCW_r = preFirst.q + preFirst.r;
            const direction = (postFirst.q === expectedCW_q && postFirst.r === expectedCW_r)
                ? 'clockwise' : 'counterclockwise';
            const cardIndex = prePlayer.hand.findIndex(c =>
                (c.name || c.type || '').includes('Rotate'));
            return {
                action_type: 'play_rotate',
                player_id: playerId,
                rotation_direction: direction,
                card_index: cardIndex >= 0 ? cardIndex : 0
            };
        }
    }

    // Check for tahini added (tahini value increased on some tiles)
    for (let i = 0; i < pre.board.length; i++) {
        const preTile = pre.board[i];
        const postTile = post.board[i];
        if ((postTile.tahini || 0) > (preTile.tahini || 0)) {
            return {
                action_type: 'add_tahini',
                player_id: playerId,
                tile_coord: [preTile.q, preTile.r]
            };
        }
    }

    // Check for end turn (player index changed)
    if (pre.current_player_idx !== post.current_player_idx) {
        return {
            action_type: 'end_turn',
            player_id: playerId
        };
    }

    return null;
}

// Wrap a game function to automatically record the action
function wrapForRecording(originalFn, fnName) {
    return async function(...args) {
        const preState = recordingActive ? getGameStateSnapshot() : null;
        const prePlayerIdx = typeof currentPlayerIdx !== 'undefined' ? currentPlayerIdx : 0;
        const isHuman = preState && playersData[prePlayerIdx] && !playersData[prePlayerIdx].isAI;

        // Call the original function
        await originalFn.apply(this, args);

        // Record if applicable
        if (preState && isHuman) {
            const postState = getGameStateSnapshot();
            const action = inferAction(preState, postState, prePlayerIdx);
            if (action) {
                try {
                    await fetch(`${AI_CONFIG.serverUrl}/record_action`, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            game_state: preState,
                            action: action,
                            player_id: prePlayerIdx
                        })
                    });
                    console.log(`[REC] Recorded ${fnName}: ${action.action_type}`);
                } catch (e) {
                    console.error(`[REC] Failed to record ${fnName}:`, e);
                }
            }
        }
    };
}

// Auto-wrap game functions when they become available
// ai_support.js loads after the game script, so functions should already exist
setTimeout(() => {
    if (typeof testEat === 'function') {
        const origTestEat = testEat;
        window.testEat = wrapForRecording(origTestEat, 'testEat');
    }
    if (typeof eatEmptyTile === 'function') {
        const origEatEmptyTile = eatEmptyTile;
        window.eatEmptyTile = wrapForRecording(origEatEmptyTile, 'eatEmptyTile');
    }
    if (typeof playDrinkCard === 'function') {
        const origPlayDrinkCard = playDrinkCard;
        window.playDrinkCard = wrapForRecording(origPlayDrinkCard, 'playDrinkCard');
    }
    if (typeof playRotateCard === 'function') {
        const origPlayRotateCard = playRotateCard;
        window.playRotateCard = wrapForRecording(origPlayRotateCard, 'playRotateCard');
    }
    if (typeof drinkToken === 'function') {
        const origDrinkToken = drinkToken;
        window.drinkToken = wrapForRecording(origDrinkToken, 'drinkToken');
    }
    if (typeof addTahini === 'function') {
        const origAddTahini = addTahini;
        window.addTahini = wrapForRecording(origAddTahini, 'addTahini');
    }
    if (typeof nextTurn === 'function') {
        const origNextTurn = nextTurn;
        window.nextTurn = function() {
            const preState = recordingActive ? getGameStateSnapshot() : null;
            const prePlayerIdx = typeof currentPlayerIdx !== 'undefined' ? currentPlayerIdx : 0;
            const isHuman = preState && playersData[prePlayerIdx] && !playersData[prePlayerIdx].isAI;

            origNextTurn.apply(this, arguments);

            if (preState && isHuman) {
                const action = { action_type: 'end_turn', player_id: prePlayerIdx };
                fetch(`${AI_CONFIG.serverUrl}/record_action`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        game_state: preState,
                        action: action,
                        player_id: prePlayerIdx
                    })
                }).then(() => {
                    console.log('[REC] Recorded end_turn');
                }).catch(e => {
                    console.error('[REC] Failed to record end_turn:', e);
                });
            }
        };
    }
    console.log('[REC] Game functions wrapped for recording');
}, 100);

// Expose globally
window.recordingStart = recordingStart;
window.recordingStop = recordingStop;
window.recordingAutoStop = recordingAutoStop;

console.log('[OK] AI Support Loaded! AI server should be running at:', AI_CONFIG.serverUrl);
console.log('   Start server with: python server.py');

// Auto-start recording for every game
recordingStart();

// Tell the server to reset its per-session move counter (for temperature schedule)
fetch(`${AI_CONFIG.serverUrl}/reset_session`, { method: 'POST' }).catch(() => {});

// Cache dish count at game start for adaptive sim scaling (used in handleAITurn)
if (typeof boardData !== 'undefined') {
    window.totalDishesAtStart = boardData.filter(t => !t.empty && !t.removed).length;
}