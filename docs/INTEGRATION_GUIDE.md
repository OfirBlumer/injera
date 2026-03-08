# Integration Guide: Adding AI Players to injera_game.html

This guide shows you exactly how to modify your `injera_game.html` file to work with the AI server.

## Overview

We need to make these changes to `injera_game.html`:

1. Add player type selection (Human vs AI)
2. Store AI level for each player
3. Detect when it's an AI player's turn
4. Call the AI server and execute the returned action
5. Handle AI sub-decisions (discard cards, hot handling)

## Step-by-Step Integration

### Step 1: Add AI player configuration to playersData

In the JavaScript section where `playersData` is initialized, add `isAI` and `aiLevel` fields:

```javascript
// FIND THIS (around line 42):
let playersData = [{"name": "Player 1", ...}, {"name": "Player 2", ...}];

// ADD these fields to each player:
let playersData = [
    {
        "name": "Player 1", 
        "isAI": false,      // <-- ADD THIS
        "aiLevel": null,    // <-- ADD THIS
        // ... rest of player data
    },
    {
        "name": "Player 2 (AI)",
        "isAI": true,       // <-- ADD THIS
        "aiLevel": "beginner",  // <-- ADD THIS
        // ... rest of player data
    }
];
```

### Step 2: Add AI move function

Add this function after the `nextTurn()` function (around line 650):

```javascript
async function handleAITurn() {
    const currentPlayer = playersData[currentPlayerIdx];
    
    if (!currentPlayer.isAI) {
        return; // Not an AI player
    }
    
    console.log(`AI (${currentPlayer.aiLevel}) is thinking...`);
    
    // Show thinking message
    const statusDiv = document.getElementById('gameStatus');
    const originalHTML = statusDiv.innerHTML;
    statusDiv.innerHTML = `<div style="color: #667eea; font-weight: bold;">🤖 ${currentPlayer.name} is thinking...</div>`;
    
    try {
        // Prepare game state
        const gameState = {
            num_players: numPlayers,
            current_player_idx: currentPlayerIdx,
            board: boardData,
            players: playersData,
            deck: deckData,
            reachable_by_player: reachableByPlayer,
            final_round_active: finalRoundActive,
            final_round_start_player: finalRoundStartPlayer,
            game_over: false
        };
        
        // Call AI server
        const response = await fetch('http://localhost:5000/ai_move', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                game_state: gameState,
                ai_level: currentPlayer.aiLevel
            })
        });
        
        if (!response.ok) {
            throw new Error(`AI server error: ${response.statusText}`);
        }
        
        const data = await response.json();
        const action = data.action;
        
        console.log('AI chose action:', action);
        console.log('AI message:', data.message);
        
        // Execute the action
        await executeAIAction(action);
        
        // Show what AI did
        alert(data.message);
        
        // Restore status
        statusDiv.innerHTML = originalHTML;
        
        // Auto-advance to next turn after a brief delay
        setTimeout(() => {
            nextTurn();
        }, 1000);
        
    } catch (error) {
        console.error('AI move failed:', error);
        statusDiv.innerHTML = originalHTML;
        alert(`AI Error: ${error.message}\n\nMake sure the AI server is running:\npython server.py`);
    }
}
```

### Step 3: Add AI action executor

Add this function after `handleAITurn()`:

```javascript
async function executeAIAction(action) {
    const currentPlayer = playersData[currentPlayerIdx];
    
    switch(action.action_type) {
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
            
        case 'end_turn':
            // Do nothing, will advance naturally
            break;
            
        default:
            console.warn('Unknown action type:', action.action_type);
    }
    
    updatePlayersPanel();
    updateGameStatus();
    drawBoard();
}

async function executeAIEatDish(action) {
    const currentPlayer = playersData[currentPlayerIdx];
    const tile = boardData.find(t => t.q === action.tile_coord[0] && t.r === action.tile_coord[1]);
    
    if (!tile) return;
    
    // Discard a random card
    const availableToDiscard = currentPlayer.hand.filter(c => {
        if (action.resource_type === 'card') {
            // If using injera, can't discard the last injera
            const injeraCount = currentPlayer.hand.filter(card => card.type === 'Clean Injera').length;
            if (c.type === 'Clean Injera' && injeraCount === 1) {
                return false;
            }
        }
        return true;
    });
    
    if (availableToDiscard.length > 0) {
        const discardIdx = Math.floor(Math.random() * availableToDiscard.length);
        const cardToDiscard = availableToDiscard[discardIdx];
        const actualIdx = currentPlayer.hand.indexOf(cardToDiscard);
        currentPlayer.hand.splice(actualIdx, 1);
    }
    
    // Calculate points
    const dishName = tile.dish;
    let dishValue = 0;
    if (dishName === 'Gomen' || dishName === 'Misir Wot' || dishName === 'Shiro') {
        dishValue = 1;
    } else if (dishName === 'Kik Alicha' || dishName === 'Azifa' || dishName === 'Tikel Gomen') {
        dishValue = 2;
    } else if (dishName === 'Berbere Misir') {
        dishValue = 3;  // Flat 3 points
    }
    
    const tahiniValue = tile.tahini || 0;
    currentPlayer.score += dishValue + tahiniValue;
    
    // Track eating
    currentPlayer.eaten.push(dishName);
    if (!currentPlayer.dishCounts) currentPlayer.dishCounts = {};
    currentPlayer.dishCounts[dishName] = (currentPlayer.dishCounts[dishName] || 0) + 1;
    
    // Handle hot if needed
    const wasHot = tile.hot;
    if (tile.hot || tile.hotToken) {
        await handleAIHotDish(tile);
    }
    
    // Consume resource
    if (action.resource_type === 'card') {
        // Remove injera card
        const injeraIdx = currentPlayer.hand.findIndex(c => c.type === 'Clean Injera');
        if (injeraIdx >= 0) {
            currentPlayer.hand.splice(injeraIdx, 1);
        }
    } else {
        // Remove empty tile
        const emptyTile = boardData.find(t => 
            t.q === action.resource_tile_coord[0] && t.r === action.resource_tile_coord[1]
        );
        if (emptyTile) {
            emptyTile.removed = true;
        }
    }
    
    // Mark tile as empty
    tile.empty = true;
    tile.dish = null;
    tile.tahini = 0;
    
    if (wasHot) {
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

async function handleAIHotDish(tile) {
    const currentPlayer = playersData[currentPlayerIdx];
    const isBerbere = tile.dish === 'Berbere Misir' || 
                     (Math.abs(tile.q) <= 1 && Math.abs(tile.r) <= 1 && Math.abs(tile.q + tile.r) <= 1);
    const hotLevel = isBerbere ? 2 : 1;
    
    for (let i = 0; i < hotLevel; i++) {
        // Try to use drink first
        const activeDrink = currentPlayer.drinks.find(d => d.tokens > 0);
        if (activeDrink) {
            activeDrink.tokens--;
            
            let points = 0;
            if (activeDrink.type === 'Coffee') points = 1;
            else if (activeDrink.type === 'Beer') points = 3;
            currentPlayer.score += points;
            
            if (activeDrink.tokens === 0) {
                if (activeDrink.type === 'Coffee') {
                    currentPlayer.handSizeModifier++;
                    currentPlayer.maxHandSize = currentPlayer.baseHandSize + currentPlayer.handSizeModifier;
                } else if (activeDrink.type === 'Beer') {
                    currentPlayer.handSizeModifier--;
                    currentPlayer.maxHandSize = currentPlayer.baseHandSize + currentPlayer.handSizeModifier;
                } else if (activeDrink.type === 'Water') {
                    const needed = currentPlayer.maxHandSize - currentPlayer.hand.length;
                    drawCards(currentPlayer, needed);
                }
                currentPlayer.drinks = currentPlayer.drinks.filter(d => d.tokens > 0);
            }
        } else {
            // Use injera
            const injeraIdx = currentPlayer.hand.findIndex(c => c.type === 'Clean Injera');
            if (injeraIdx >= 0) {
                currentPlayer.hand.splice(injeraIdx, 1);
            }
        }
    }
}

async function executeAIEatEmptyTile(action) {
    const currentPlayer = playersData[currentPlayerIdx];
    const tile = boardData.find(t => t.q === action.tile_coord[0] && t.r === action.tile_coord[1]);
    
    if (!tile) return;
    
    // Discard a card
    if (currentPlayer.hand.length > 0) {
        const idx = Math.floor(Math.random() * currentPlayer.hand.length);
        currentPlayer.hand.splice(idx, 1);
    }
    
    // Handle hot if needed
    if (tile.hotToken) {
        await handleAIHotDish(tile);
    }
    
    // Award tahini points
    currentPlayer.score += (tile.tahini || 0);
    
    // Remove tile
    tile.removed = true;
    updateCanEatEmpty();
}

function executeAIPlayDrink(action) {
    const currentPlayer = playersData[currentPlayerIdx];
    const card = currentPlayer.hand[action.card_index];
    
    if (!card) return;
    
    currentPlayer.hand.splice(action.card_index, 1);
    
    const drinkType = card.name.replace('Order ', '');
    currentPlayer.drinks.push({
        type: drinkType,
        tokens: 3
    });
}

function executeAIDrinkToken(action) {
    const currentPlayer = playersData[currentPlayerIdx];
    const drink = currentPlayer.drinks[action.drink_index];
    
    if (!drink) return;
    
    drink.tokens--;
    
    let points = 0;
    if (drink.type === 'Coffee') points = 1;
    else if (drink.type === 'Beer') points = 3;
    currentPlayer.score += points;
    
    if (drink.tokens === 0) {
        if (drink.type === 'Coffee') {
            currentPlayer.handSizeModifier++;
            currentPlayer.maxHandSize = currentPlayer.baseHandSize + currentPlayer.handSizeModifier;
        } else if (drink.type === 'Beer') {
            currentPlayer.handSizeModifier--;
            currentPlayer.maxHandSize = currentPlayer.baseHandSize + currentPlayer.handSizeModifier;
        } else if (drink.type === 'Water') {
            const needed = currentPlayer.maxHandSize - currentPlayer.hand.length;
            drawCards(currentPlayer, needed);
        }
        currentPlayer.drinks.splice(action.drink_index, 1);
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
}

function executeAITahini(action) {
    const currentPlayer = playersData[currentPlayerIdx];
    currentPlayer.hand.splice(action.card_index, 1);
    
    const tile = boardData.find(t => t.q === action.tile_coord[0] && t.r === action.tile_coord[1]);
    if (!tile) return;
    
    // Find the triangle and add tahini
    const triangles = getTrianglesContaining(tile.q, tile.r);
    
    // Add tahini to all tiles in a random valid triangle
    if (triangles.length > 0) {
        const triangle = triangles[0];
        triangle.forEach(t => {
            if (!t.removed) {
                t.tahini = (t.tahini || 0) + 1;
            }
        });
    }
}
```

### Step 4: Modify nextTurn() to check for AI players

Find the `nextTurn()` function and modify it to call `handleAITurn()`:

```javascript
function nextTurn() {
    const dishesRemaining = boardData.filter(t => !t.empty && !t.removed).length;
    
    // Move to next player
    currentPlayerIdx = (currentPlayerIdx + 1) % playersData.length;
    const currentPlayer = playersData[currentPlayerIdx];
    
    // ... (keep existing final round check code) ...
    
    // Always draw cards (deck reshuffles when empty)
    const drawn = drawCards(currentPlayer);
    
    // ... (keep existing alert code) ...
    
    updatePlayersPanel();
    updateGameStatus();
    drawBoard();
    
    // CHECK IF AI PLAYER - ADD THIS AT THE END:
    if (currentPlayer.isAI) {
        // Small delay before AI moves
        setTimeout(() => {
            handleAITurn();
        }, 500);
    }
}
```

### Step 5: Add setup screen (OPTIONAL but recommended)

Before the game starts, let users choose AI opponents:

```html
<!-- Add this before the game container -->
<div id="setupScreen" style="display: flex; justify-content: center; align-items: center; min-height: 100vh;">
    <div style="background: white; padding: 40px; border-radius: 20px; max-width: 500px;">
        <h1 style="text-align: center; margin-bottom: 30px;">🍽️ Injera Board Game</h1>
        
        <div style="margin-bottom: 20px;">
            <label>Player 1:</label>
            <select id="player1Type" class="btn" style="width: 100%;">
                <option value="human">Human</option>
                <option value="beginner">Beginner AI</option>
            </select>
        </div>
        
        <div style="margin-bottom: 20px;">
            <label>Player 2:</label>
            <select id="player2Type" class="btn" style="width: 100%;">
                <option value="human">Human</option>
                <option value="beginner" selected>Beginner AI</option>
            </select>
        </div>
        
        <button class="btn" onclick="startGameWithSettings()" style="background: #4CAF50; font-size: 20px; padding: 15px;">
            Start Game
        </button>
    </div>
</div>

<div id="gameContainer" class="container" style="display: none;">
    <!-- Your existing game HTML -->
</div>

<script>
function startGameWithSettings() {
    const p1Type = document.getElementById('player1Type').value;
    const p2Type = document.getElementById('player2Type').value;
    
    // Update players
    playersData[0].isAI = p1Type !== 'human';
    playersData[0].aiLevel = p1Type !== 'human' ? p1Type : null;
    playersData[0].name = p1Type === 'human' ? 'Player 1' : `Player 1 (${p1Type} AI)`;
    
    playersData[1].isAI = p2Type !== 'human';
    playersData[1].aiLevel = p2Type !== 'human' ? p2Type : null;
    playersData[1].name = p2Type === 'human' ? 'Player 2' : `Player 2 (${p2Type} AI)`;
    
    // Hide setup, show game
    document.getElementById('setupScreen').style.display = 'none';
    document.getElementById('gameContainer').style.display = 'flex';
    
    // Initialize game
    randomizeInitialState();
    updateCanEatEmpty();
    drawBoard();
    updatePlayersPanel();
    updateGameStatus();
    
    // If player 1 is AI, start their turn
    if (playersData[0].isAI) {
        setTimeout(() => handleAITurn(), 1000);
    }
}
</script>
```

## That's It!

Now you can:

1. Start the AI server: `python server.py`
2. Open `injera_game.html` in your browser
3. Play against the AI!

The AI will automatically take its turn and you'll see what it does.

## Testing

To test quickly:
1. In web_gui.py, set one player to AI:
   ```python
   players[1].is_ai = True
   players[1].ai_level = 'beginner'
   ```
2. Regenerate the HTML: `python web_gui.py`
3. Start server: `python server.py`
4. Open the HTML and play!
