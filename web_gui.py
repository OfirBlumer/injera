"""
Injera Board Game - Web GUI Generator
Creates an interactive HTML/JS visualization
"""

from injera_game import *
import json
import math


def generate_web_gui(board: Board, players: List[Player], deck: Deck, num_players: int, output_file: str = "injera_game.html"):
    """Generate a complete HTML file with embedded JavaScript for the game"""
    
    # Convert board state to JSON
    board_data = []
    for coord, tile in board.tiles.items():
        board_data.append({
            'q': coord.q,
            'r': coord.r,
            'dish': tile.dish_type.value if not tile.is_empty and not tile.is_removed else None,
            'hot': tile.is_hot,
            'hotToken': tile.has_hot_token,
            'tahini': tile.tahini_tokens,
            'empty': tile.is_empty,
            'removed': tile.is_removed,
            'canEatEmpty': board.can_eat_empty_tile(coord) if tile.is_empty else False
        })
    
    # Player positions (evenly spaced around board for 2-4 players)
    # Position 0: bottom (south), Position 1: right, Position 2: top, Position 3: left
    player_position_angles = {
        0: 270,  # Bottom (6 o'clock)
        1: 0,    # Right (3 o'clock)
        2: 90,   # Top (12 o'clock)
        3: 180   # Left (9 o'clock)
    }
    
    # Calculate reachable tiles for each player
    reachable_by_player = []
    for player in players:
        reachable_coords = board.get_reachable_tiles(player.position, num_players)
        reachable_by_player.append([{'q': c.q, 'r': c.r} for c in reachable_coords])
    
    # Convert players to JSON
    players_data = []
    for player in players:
        # Count each dish type
        dish_counts = {}
        for dish_type in DishType:
            dish_counts[dish_type.value] = player.count_dish_type(dish_type)
        
        players_data.append({
            'name': player.name,
            'position': player.position,
            'score': player.score,
            'handSizeModifier': player.hand_size_modifier,
            'baseHandSize': player.base_hand_size,
            'maxHandSize': player.max_hand_size,
            'superHotCount': player.super_hot_eaten_count,
            'superHotValue': player.get_super_hot_value(),
            'hand': [{'type': c.card_type.value, 'name': c.name} for c in player.hand],
            'eaten': [d.value for d in player.eaten_dishes],
            'dishCounts': dish_counts,
            'tastedAllTypes': player.has_tasted_all_dish_types(),
            'drinks': [{'type': d.drink_type.value, 'tokens': d.tokens_remaining}
                      for d in player.active_drinks]
        })
    
    # Deck info
    # Count card types in deck
    from collections import Counter
    card_type_counts = Counter()
    for card in deck.cards:
        if isinstance(card, InjeraCard):
            card_type_counts['Injera'] += 1
        elif isinstance(card, DrinkCard):
            card_type_counts[card.drink_type.value] += 1
        elif isinstance(card, TahiniCard):
            card_type_counts['Tahini'] += 1
        elif isinstance(card, RotateCard):
            card_type_counts['Rotate'] += 1
    
    deck_data = {
        'cardsRemaining': deck.cards_remaining(),
        'deckSize': len(deck.cards),
        'discardSize': len(deck.discard),
        'composition': dict(card_type_counts)
    }
    
    # Player positions for visualization
    player_positions = [{'position': i, 'name': f'Player {i+1}'} for i in range(num_players)]
    
    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Injera Board Game</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }}
        
        .container {{
            max-width: 1400px;
            margin: 0 auto;
            display: flex;
            gap: 20px;
        }}
        
        .board-section {{
            flex: 1;
            background: #f5e6d3;
            border-radius: 15px;
            padding: 20px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.3);
        }}
        
        .sidebar {{
            width: 350px;
            display: flex;
            flex-direction: column;
            gap: 15px;
        }}
        
        .panel {{
            background: white;
            border-radius: 10px;
            padding: 15px;
            box-shadow: 0 5px 15px rgba(0,0,0,0.2);
        }}
        
        h1 {{
            text-align: center;
            color: #333;
            margin-bottom: 20px;
            font-size: 28px;
        }}
        
        h2 {{
            color: #667eea;
            margin-bottom: 10px;
            font-size: 18px;
        }}
        
        #gameCanvas {{
            display: block;
            margin: 0 auto;
            background: #fff8dc;
            border-radius: 10px;
            box-shadow: inset 0 0 20px rgba(0,0,0,0.1);
        }}
        
        .player-card {{
            background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
            color: white;
            padding: 15px;
            border-radius: 8px;
            margin-bottom: 10px;
        }}
        
        .player-card.current {{
            background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);
            box-shadow: 0 0 20px rgba(79, 172, 254, 0.5);
        }}
        
        .score {{
            font-size: 24px;
            font-weight: bold;
            margin: 10px 0;
        }}
        
        .card-list {{
            display: flex;
            flex-wrap: wrap;
            gap: 5px;
            margin: 10px 0;
        }}
        
        .card {{
            background: #fff;
            color: #333;
            padding: 5px 10px;
            border-radius: 5px;
            font-size: 12px;
            border: 2px solid #667eea;
        }}
        
        .btn {{
            background: #667eea;
            color: white;
            border: none;
            padding: 12px 20px;
            border-radius: 8px;
            cursor: pointer;
            font-size: 16px;
            width: 100%;
            margin: 5px 0;
            transition: all 0.3s;
        }}
        
        .btn:hover {{
            background: #5568d3;
            transform: translateY(-2px);
            box-shadow: 0 5px 15px rgba(102, 126, 234, 0.4);
        }}
        
        .btn:active {{
            transform: translateY(0);
        }}
        
        .legend {{
            background: #f8f9fa;
            padding: 10px;
            border-radius: 5px;
            margin-top: 10px;
            font-size: 12px;
            line-height: 1.6;
        }}
        
        .dish-count {{
            display: flex;
            justify-content: space-between;
            padding: 5px 0;
            border-bottom: 1px solid #eee;
        }}
        
        .eaten-dishes {{
            font-size: 12px;
            color: #666;
            margin-top: 5px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="board-section">
            <h1>ðŸ½ï¸ Injera Board Game ðŸ½ï¸</h1>
            <canvas id="gameCanvas" width="700" height="700"></canvas>
            <div class="legend">
                <strong>Legend:</strong><br>
                ðŸ”¥ = Hot dish (requires drink or injera) | +N = Tahini<br>
                <strong>Light green glow</strong> = Tiles you can reach<br>
                <strong>Numbered circles</strong> = Player positions<br>
                <strong>Green outline</strong> = Empty tile can be eaten<br>
                <strong>Blue outline</strong> = Can eat without Injera card<br>
                <strong>Dishes:</strong> Non-hot: G=Gomen, M=Misir Wot, S=Shiro<br>
                Medium-hot: K=Kik Alicha, A=Azifa, T=Tikel Gomen | Super-hot: B=Berbere Misir<br>
                <strong>Deck (60 cards):</strong> 35 Injera, 10 Rotate, 6 Tahini, 3 Order Coffee, 3 Order Beer, 3 Order Water<br>
                <strong>Drinks:</strong> Order cards fill your cup with 3 tokens. Coffee=1pt, Beer=3pts, Water=0pts. Water refills hand once per turn; 2nd Water ends turn!<br>
                <em style="font-size: 10px;">Current game: {num_players} players. To change: see injera_game.py for instructions</em>
            </div>
        </div>
        
        <div class="sidebar">
            <div class="panel">
                <h2>ðŸ“Š Game Status</h2>
                <div id="gameStatus"></div>
                <button class="btn" style="background: #d32f2f; font-weight: bold;" onclick="if(confirm('Start a new game with {num_players} players?')) location.reload()">ðŸŽ® New Game</button>
                <button class="btn" onclick="nextTurn()">Next Turn â–¶ï¸</button>
                <button class="btn" style="background: #8b0000; font-weight: bold;" onclick="endGameNow()">â¹ï¸ End Game Now</button>
                <button class="btn" onclick="testEat()">Eat Dish ðŸ´</button>
                <button class="btn" onclick="eatEmptyTile()">Eat Empty Tile ðŸ¥–</button>
                <button class="btn" onclick="playDrinkCard()">Order Drink ðŸ¥¤</button>
                <button class="btn" onclick="playRotateCard()">Play Rotate Card ðŸ”„</button>
                <button class="btn" onclick="drinkToken()">Drink Token ðŸº</button>
                <button class="btn" onclick="addTahini()">Add Tahini ðŸ¥«</button>
            </div>
            
            <div id="playersPanel"></div>
        </div>
    </div>

    <script>
        // Game data
        let boardData = {json.dumps(board_data)};
        let playersData = {json.dumps(players_data)};
        let deckData = {json.dumps(deck_data)};
        let reachableByPlayer = {json.dumps(reachable_by_player)};
        let numPlayers = {num_players};
        let currentPlayerIdx = 0;
        let selectedTile = null;
        let rotationOffset = 0; // Board rotation in degrees (0, 60, 120, 180, 240, 300)
        let finalRoundActive = false; // Track if we're in the final round
        let finalRoundStartPlayer = -1; // Which player ate the last dish
        let waterRefilledThisTurn = new Array(numPlayers).fill(false); // Water refill once per turn
        
        // Player position angles (where they sit around the board)
        const playerPositionAngles = {{
            0: 270,  // Bottom (6 o'clock)
            1: 90,   // Top (12 o'clock) for 2 players
            2: 0,    // Right (3 o'clock) for 3-4 players
            3: 180   // Left (9 o'clock) for 4 players
        }};
        
        const canvas = document.getElementById('gameCanvas');
        const ctx = canvas.getContext('2d');
        const hexSize = 25;
        
        // Dish colors
        const dishColors = {{
            // Non-hot (cooler colors)
            'Gomen': '#90EE90',           // Light green (collard greens)
            'Misir Wot': '#CD5C5C',       // Indian red (red lentils)
            'Shiro': '#FFE4B5',           // Moccasin (chickpea)
            
            // Medium-hot (warm colors)
            'Kik Alicha': '#F0E68C',      // Khaki (yellow split peas)
            'Azifa': '#DDA0DD',           // Plum (lentil salad)
            'Tikel Gomen': '#9ACD32',     // Yellow green (cabbage) - more distinct from Gomen
            
            // Super-hot (intense color)
            'Berbere Misir': '#DC143C'    // Crimson (very spicy!)
        }};
        
        function hexToPixel(q, r) {{
            const x = hexSize * (3/2 * q) + 350;
            const y = hexSize * (Math.sqrt(3)/2 * q + Math.sqrt(3) * r) + 350;
            return {{x, y}};
        }}
        
        function drawHexagon(x, y, size, fillColor, strokeColor = 'black', lineWidth = 2) {{
            ctx.beginPath();
            for (let i = 0; i < 6; i++) {{
                const angle = Math.PI / 3 * i;
                const px = x + size * Math.cos(angle);
                const py = y + size * Math.sin(angle);
                if (i === 0) ctx.moveTo(px, py);
                else ctx.lineTo(px, py);
            }}
            ctx.closePath();
            ctx.fillStyle = fillColor;
            ctx.fill();
            ctx.strokeStyle = strokeColor;
            ctx.lineWidth = lineWidth;
            ctx.stroke();
        }}
        
        function drawBoard() {{
            ctx.clearRect(0, 0, canvas.width, canvas.height);
            
            // Get current player's reachable tiles
            const reachableCoords = reachableByPlayer[currentPlayerIdx];
            const reachableSet = new Set(reachableCoords.map(c => `${{c.q}},${{c.r}}`));
            
            boardData.forEach(tile => {{
                // Skip removed tiles completely
                if (tile.removed) return;
                
                const {{x, y}} = hexToPixel(tile.q, tile.r);
                
                let color = tile.empty ? '#FFFACD' : dishColors[tile.dish] || '#FFFFFF';
                let stroke = tile.hot ? '#8B0000' : '#333';
                let lineWidth = tile.hot ? 3 : 2;
                
                // Check if tile is reachable by current player
                const isReachable = reachableSet.has(`${{tile.q}},${{tile.r}}`);
                
                // Dim unreachable tiles
                if (!isReachable) {{
                    ctx.globalAlpha = 0.3;
                }}
                
                // Highlight selected tile with a gold outer ring
                if (selectedTile && selectedTile.q === tile.q && selectedTile.r === tile.r) {{
                    drawHexagon(x, y, hexSize + 7, '#FFD700', '#FFD700', 6);
                }}
                
                // Draw green outline if empty tile can be eaten
                if (tile.empty && tile.canEatEmpty && isReachable) {{
                    drawHexagon(x, y, hexSize + 5, '', '#00FF00', 3);
                }}
                
                // Draw blue outline if dish has adjacent EATABLE empty tile
                if (!tile.empty && !tile.removed && isReachable) {{
                    const adjacentEatable = getAdjacentEmptyTiles(tile.q, tile.r);
                    if (adjacentEatable.length > 0) {{
                        drawHexagon(x, y, hexSize + 5, '', '#4169E1', 2);
                    }}
                }}
                
                drawHexagon(x, y, hexSize, color, stroke, lineWidth);
                
                // Draw labels
                if (!tile.empty) {{
                    ctx.fillStyle = 'black';
                    ctx.font = 'bold 14px Arial';
                    ctx.textAlign = 'center';
                    ctx.textBaseline = 'middle';
                    
                    let label = tile.dish[0];
                    if (tile.tahini > 0) label += '+' + tile.tahini;
                    ctx.fillText(label, x, y);
                    
                    if (tile.hot) {{
                        ctx.font = '16px Arial';
                        // Berbere is extra hot - show double flames
                        const flames = tile.dish === 'Berbere Misir' ? 'ðŸ”¥ðŸ”¥' : 'ðŸ”¥';
                        ctx.fillText(flames, x, y - 15);
                    }}
                }} else {{
                    // Empty tile
                    ctx.fillStyle = '#999';
                    ctx.font = 'italic 9px Arial';
                    ctx.textAlign = 'center';
                    ctx.textBaseline = 'middle';
                    
                    let emptyLabel = 'empty';
                    if (tile.tahini > 0) {{
                        emptyLabel = `+${{tile.tahini}}`;
                        ctx.fillStyle = '#D2691E';  // Brown for tahini
                        ctx.font = 'bold 12px Arial';
                    }}
                    ctx.fillText(emptyLabel, x, y);
                    
                    // Show hot token if present
                    if (tile.hotToken) {{
                        ctx.font = '14px Arial';
                        // Check if this is a Berbere hot token (center cluster) - show double flames
                        const isBerbereHotToken = Math.abs(tile.q) <= 1 && Math.abs(tile.r) <= 1 && 
                                                 Math.abs(tile.q + tile.r) <= 1;
                        const flames = isBerbereHotToken ? 'ðŸ”¥ðŸ”¥' : 'ðŸ”¥';
                        ctx.fillText(flames, x, y - 12);
                    }}
                }}
                
                ctx.globalAlpha = 1.0; // Reset alpha
            }});
            
            // Draw player position markers
            drawPlayerPositions();
        }}
        
        function getCurrentReachableTiles() {{
            // Get reachable tiles for current player, adjusted for rotation
            // For 2 players: position 0 = index 0, position 1 = index 1
            // Rotation doesn't change the reachable set in the current implementation
            // (rotation would need server-side recalculation in full version)
            const playerPos = playersData[currentPlayerIdx].position;
            console.log('Getting reachable for player', currentPlayerIdx, 'position', playerPos);
            console.log('Reachable array:', reachableByPlayer[playerPos]);
            return reachableByPlayer[playerPos] || [];
        }}
        
        function drawPlayerPositions() {{
            const playerColors = ['#FF6B6B', '#4ECDC4', '#FFE66D', '#95E1D3', '#A78BFA', '#FB923C'];
            const radius = 280; // Distance from center
            
            // Flat-top hexagon vertices at 0Â°, 60Â°, 120Â°, 180Â°, 240Â°, 300Â°
            let playerVertices;
            if (numPlayers === 2) {{
                playerVertices = [300, 120];  // P1: top-right, P2: bottom-left
            }} else if (numPlayers === 3) {{
                playerVertices = [300, 60, 180];  // P1: top-right, P2: bottom-right, P3: left
            }} else if (numPlayers === 4) {{
                playerVertices = [300, 0, 120, 180];  // P1: top-right, P2: right, P3: bottom-left, P4: left (symmetric pairs)
            }} else if (numPlayers === 5) {{
                playerVertices = [300, 0, 60, 120, 240];  // skip left (180)
            }} else if (numPlayers === 6) {{
                playerVertices = [300, 0, 60, 120, 180, 240];  // all vertices
            }}
            
            for (let i = 0; i < numPlayers; i++) {{
                // Convert angle to radians
                const angleDeg = playerVertices[i];
                const angle = angleDeg * Math.PI / 180;
                const px = 350 + radius * Math.cos(angle);
                const py = 350 + radius * Math.sin(angle);
                
                // Draw player marker
                ctx.fillStyle = playerColors[i];
                ctx.strokeStyle = i === currentPlayerIdx ? '#FFD700' : '#333';
                ctx.lineWidth = i === currentPlayerIdx ? 4 : 2;
                
                ctx.beginPath();
                ctx.arc(px, py, 20, 0, 2 * Math.PI);
                ctx.fill();
                ctx.stroke();
                
                // Draw player number
                ctx.fillStyle = 'white';
                ctx.font = 'bold 16px Arial';
                ctx.textAlign = 'center';
                ctx.textBaseline = 'middle';
                ctx.fillText(`P${{i + 1}}`, px, py);
            }}
        }}
        
        function updatePlayersPanel() {{
            const panel = document.getElementById('playersPanel');
            panel.innerHTML = '';
            
            // Show current player first, then others
            const sortedIndices = [currentPlayerIdx];
            for (let i = 0; i < playersData.length; i++) {{
                if (i !== currentPlayerIdx) {{
                    sortedIndices.push(i);
                }}
            }}
            
            sortedIndices.forEach(idx => {{
                const player = playersData[idx];
                const isCurrent = idx === currentPlayerIdx;
                
                // Determine position label based on player count
                const positionLabels = {{
                    2: ['South', 'North'],
                    3: ['South', 'NE', 'NW'],
                    4: ['South', 'East', 'North', 'West'],
                    5: ['South', 'SE', 'NE', 'NW', 'SW'],
                    6: ['South', 'SE', 'NE', 'North', 'NW', 'SW']
                }};
                const labels = positionLabels[numPlayers] || positionLabels[2];
                const positionLabel = labels[player.position] || `P${{player.position}}`;
                
                const cardHTML = `
                    <div class="player-card ${{isCurrent ? 'current' : ''}}">
                        <h2>${{player.name}} (${{positionLabel}}) ${{isCurrent ? 'ðŸ‘ˆ YOUR TURN' : ''}}</h2>
                        <div class="score">Score: ${{player.score}}</div>
                        <div style="font-size: 12px; margin: 5px 0;">
                            Hand: ${{player.hand.length}}/${{player.maxHandSize}} |
                            Berbere eaten: ${{player.superHotCount || 0}}
                            ${{player.tastedAllTypes ? ' | ðŸŽ‰ Tasted all!' : ''}}
                        </div>
                        
                        <strong>Hand:</strong>
                        <div class="card-list">
                            ${{player.hand.map(c => `<span class="card">${{c.name}}</span>`).join('')}}
                        </div>
                        
                        ${{player.drinks.length > 0 ? `
                            <strong>Active Drinks:</strong>
                            <div class="card-list">
                                ${{player.drinks.map(d => `<span class="card">${{d.type}}: ${{d.tokens}}ðŸ¥¤</span>`).join('')}}
                            </div>
                        ` : ''}}
                        
                        <div class="eaten-dishes" style="font-size: 11px;">
                            <strong>Eaten (${{player.eaten.length}}):</strong><br>
                            ${{Object.entries(player.dishCounts || {{}}).map(([dish, count]) => {{
                                // Get abbreviation: first letter, or special cases
                                let abbr = dish.charAt(0); // Default: first letter
                                if (dish === 'Misir Wot') abbr = 'M';
                                else if (dish === 'Kik Alicha') abbr = 'K';
                                else if (dish === 'Tikel Gomen') abbr = 'T';
                                else if (dish === 'Berbere Misir') abbr = 'B';
                                
                                return `${{abbr}}:${{count}}${{count === 7 ? 'âœ“' : ''}}`;
                            }}).join(' ') || 'None'}}
                        </div>
                    </div>
                `;
                panel.innerHTML += cardHTML;
            }});
        }}
        
        function updateGameStatus() {{
            const dishesRemaining = boardData.filter(t => !t.empty).length;
            const status = document.getElementById('gameStatus');
            
            // Build composition: deck + other players' hands (not current player)
            const composition = {{...deckData.composition}};
            
            // Add cards from OTHER players' hands
            playersData.forEach((player, idx) => {{
                if (idx !== currentPlayerIdx) {{
                    player.hand.forEach(card => {{
                        let cardType;
                        if (card.type === 'Clean Injera') cardType = 'Injera';
                        else if (card.name === 'Rotate Injera') cardType = 'Rotate';
                        else if (card.name === 'Tahini') cardType = 'Tahini';
                        else if (card.name === 'Order Coffee') cardType = 'Coffee';
                        else if (card.name === 'Order Beer') cardType = 'Beer';
                        else if (card.name === 'Order Water') cardType = 'Water';
                        
                        composition[cardType] = (composition[cardType] || 0) + 1;
                    }});
                }}
            }});
            
            const compItems = [];
            if (composition.Injera) compItems.push(`${{composition.Injera}}Ã—Injera`);
            if (composition.Rotate) compItems.push(`${{composition.Rotate}}Ã—Rotate`);
            if (composition.Tahini) compItems.push(`${{composition.Tahini}}Ã—Tahini`);
            if (composition.Coffee) compItems.push(`${{composition.Coffee}}Ã—Coffee`);
            if (composition.Beer) compItems.push(`${{composition.Beer}}Ã—Beer`);
            if (composition.Water) compItems.push(`${{composition.Water}}Ã—Water`);
            const compString = compItems.join(', ') || 'Empty';
            
            const totalUnknown = Object.values(composition).reduce((a, b) => a + b, 0);
            
            status.innerHTML = `
                <div class="dish-count">
                    <span>Dishes Remaining:</span>
                    <strong>${{dishesRemaining}}</strong>
                </div>
                <div class="dish-count">
                    <span>Unknown Cards:</span>
                    <strong>${{totalUnknown}} total</strong>
                </div>
                <div class="dish-count" style="font-size: 11px;">
                    <span>Deck + Others:</span>
                    <strong>${{compString}}</strong>
                </div>
                <div class="dish-count">
                    <span>Current Turn:</span>
                    <strong>${{playersData[currentPlayerIdx].name}}</strong>
                </div>
            `;
        }}
        
        function drawCards(player, count = null) {{
            // If count is not specified, draw to fill hand
            const cardsToDraw = count !== null ? count : (player.maxHandSize - player.hand.length);
            
            if (cardsToDraw <= 0) {{
                return 0; // Hand already full or no cards to draw
            }}
            
            let cardsDrawn = 0;
            
            // Draw cards one at a time, reshuffling if needed mid-draw
            for (let i = 0; i < cardsToDraw; i++) {{
                // Calculate total cards available in current composition
                const total = Object.values(deckData.composition).reduce((a, b) => a + b, 0);
                
                // Check if deck needs reshuffling (composition is empty)
                if (total === 0) {{
                    deckData.composition = {{
                        'Injera': 35,
                        'Rotate': 10,
                        'Tahini': 6,
                        'Coffee': 3,
                        'Beer': 3,
                        'Water': 3
                    }};
                    deckData.cardsRemaining = 60;
                    deckData.deckSize = 60;
                    console.log('DECK RESHUFFLED! Starting with fresh 60 cards.');
                }}
                
                // Recalculate total after potential reshuffle
                const totalAfterReshuffle = Object.values(deckData.composition).reduce((a, b) => a + b, 0);
                
                if (totalAfterReshuffle === 0) {{
                    // No cards left even after reshuffle attempt (shouldn't happen with infinite reshuffles)
                    console.log('WARNING: No cards available even after reshuffle!');
                    break;
                }}
                
                // Weighted random based on actual deck composition
                const rand = Math.random() * totalAfterReshuffle;
                let cumulative = 0;
                let drawnType = null;
                
                for (const [cardType, count] of Object.entries(deckData.composition)) {{
                    cumulative += count;
                    if (rand < cumulative) {{
                        drawnType = cardType;
                        break;
                    }}
                }}
                
                // Create card based on type
                let newCard;
                if (drawnType === 'Injera') {{
                    newCard = {{type: 'Clean Injera', name: 'Clean Injera'}};
                }} else if (drawnType === 'Rotate') {{
                    newCard = {{type: 'Rotate', name: 'Rotate Injera'}};
                }} else if (drawnType === 'Tahini') {{
                    newCard = {{type: 'Tahini', name: 'Tahini'}};
                }} else if (drawnType === 'Coffee') {{
                    newCard = {{type: 'Drink', name: 'Order Coffee'}};
                }} else if (drawnType === 'Beer') {{
                    newCard = {{type: 'Drink', name: 'Order Beer'}};
                }} else if (drawnType === 'Water') {{
                    newCard = {{type: 'Drink', name: 'Order Water'}};
                }}
                
                player.hand.push(newCard);
                
                // Update deck composition
                deckData.composition[drawnType]--;
                if (deckData.composition[drawnType] === 0) {{
                    delete deckData.composition[drawnType];
                }}
                deckData.cardsRemaining--;
                deckData.deckSize--;
                cardsDrawn++;
            }}
            
            return cardsDrawn;
        }}
        
        // Shuffle array in place (Fisher-Yates)
        function shuffleArray(array) {{
            for (let i = array.length - 1; i > 0; i--) {{
                const j = Math.floor(Math.random() * (i + 1));
                [array[i], array[j]] = [array[j], array[i]];
            }}
            return array;
        }}
        
        // Randomize initial hands by shuffling a fresh deck
        function randomizeInitialState() {{
            // Create a fresh deck
            const freshDeck = [];
            for (let i = 0; i < 35; i++) freshDeck.push({{type: 'Clean Injera', name: 'Clean Injera'}});
            for (let i = 0; i < 10; i++) freshDeck.push({{type: 'Rotate', name: 'Rotate Injera'}});
            for (let i = 0; i < 6; i++) freshDeck.push({{type: 'Tahini', name: 'Tahini'}});
            for (let i = 0; i < 3; i++) freshDeck.push({{type: 'Drink', name: 'Order Coffee'}});
            for (let i = 0; i < 3; i++) freshDeck.push({{type: 'Drink', name: 'Order Beer'}});
            for (let i = 0; i < 3; i++) freshDeck.push({{type: 'Drink', name: 'Order Water'}});
            
            shuffleArray(freshDeck);
            
            // Deal cards to players
            playersData.forEach(player => {{
                player.hand = [];
                for (let i = 0; i < player.maxHandSize; i++) {{
                    if (freshDeck.length > 0) {{
                        player.hand.push(freshDeck.pop());
                    }}
                }}
            }});
            
            // Update deck composition based on remaining cards
            deckData.composition = {{Injera: 0, Rotate: 0, Tahini: 0, Coffee: 0, Beer: 0, Water: 0}};
            freshDeck.forEach(card => {{
                if (card.type === 'Clean Injera') deckData.composition.Injera++;
                else if (card.name === 'Rotate Injera') deckData.composition.Rotate++;
                else if (card.name === 'Tahini') deckData.composition.Tahini++;
                else if (card.name === 'Order Coffee') deckData.composition.Coffee++;
                else if (card.name === 'Order Beer') deckData.composition.Beer++;
                else if (card.name === 'Order Water') deckData.composition.Water++;
            }});
            deckData.cardsRemaining = freshDeck.length;
            deckData.deckSize = freshDeck.length;
        }}
        
        function calculateFinalScores() {{
            // Calculate variety bonus: 0-4 types = 0, 5 types = 5, 6 types = 12, 7 types = 21
            // Calculate completion bonuses: 5 tiles = +5, 6 tiles = +10, 7 tiles = +15 (for each dish type)
            const results = playersData.map(player => {{
                const uniqueDishTypes = new Set(player.eaten);
                const numTypes = uniqueDishTypes.size;
                let varietyBonus = 0;
                if (numTypes === 5) varietyBonus = 5;
                else if (numTypes === 6) varietyBonus = 12;
                else if (numTypes === 7) varietyBonus = 21;
                
                // Calculate completion bonuses for each dish type
                let completionBonus = 0;
                const completionDetails = [];
                if (player.dishCounts) {{
                    for (const [dishName, count] of Object.entries(player.dishCounts)) {{
                        if (count === 5) {{
                            completionBonus += 5;
                            completionDetails.push(`${{dishName}} (5): +5`);
                        }} else if (count === 6) {{
                            completionBonus += 10;
                            completionDetails.push(`${{dishName}} (6): +10`);
                        }} else if (count === 7) {{
                            completionBonus += 15;
                            completionDetails.push(`${{dishName}} (7): +15`);
                        }}
                    }}
                }}
                
                const finalScore = player.score + varietyBonus + completionBonus;
                return {{
                    name: player.name,
                    score: player.score,
                    varietyBonus: varietyBonus,
                    completionBonus: completionBonus,
                    completionDetails: completionDetails,
                    finalScore: finalScore,
                    dishTypes: uniqueDishTypes.size
                }};
            }});
            
            return results;
        }}
        
        function endGameNow() {{
            if (!confirm('End the game now and calculate final scores?')) {{
                return;
            }}
            
            const results = calculateFinalScores();
            results.sort((a, b) => b.finalScore - a.finalScore);
            
            let message = 'ðŸŽ‰ GAME OVER! ðŸŽ‰\\n\\n';
            message += 'FINAL SCORES:\\n';
            message += 'â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•\\n\\n';
            
            results.forEach((r, idx) => {{
                message += `${{idx + 1}}. ${{r.name}}: ${{r.finalScore}} points\\n`;
                message += `   Base score: ${{r.score}}\\n`;
                message += `   Variety bonus: +${{r.varietyBonus}} (${{r.dishTypes}} unique dish types)\\n`;
                if (r.completionBonus > 0) {{
                    message += `   Completion bonus: +${{r.completionBonus}} (${{r.completionDetails.join(', ')}})\\n`;
                }}
                message += `\\n`;
            }});
            
            alert(message);
        }}
        
        function nextTurn() {{
            const dishesRemaining = boardData.filter(t => !t.empty && !t.removed).length;
            
            // Move to next player
            currentPlayerIdx = (currentPlayerIdx + 1) % playersData.length;
            waterRefilledThisTurn[currentPlayerIdx] = false; // Reset water refill flag
            const currentPlayer = playersData[currentPlayerIdx];

            // Check if we're in final round and have completed it
            if (finalRoundActive && currentPlayerIdx === finalRoundStartPlayer) {{
                // Final round complete - end game
                const results = calculateFinalScores();
                results.sort((a, b) => b.finalScore - a.finalScore);
                
                let message = 'ðŸŽ‰ GAME OVER! Final round complete! ðŸŽ‰\\n\\n';
                message += 'FINAL SCORES:\\n';
                message += 'â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•\\n\\n';
                
                results.forEach((r, idx) => {{
                    message += `${{idx + 1}}. ${{r.name}}: ${{r.finalScore}} points\\n`;
                    message += `   Base score: ${{r.score}}\\n`;
                    message += `   Variety bonus: +${{r.varietyBonus}} (${{r.dishTypes}} unique dish types)\\n`;
                    if (r.completionBonus > 0) {{
                        message += `   Completion bonus: +${{r.completionBonus}} (${{r.completionDetails.join(', ')}})\\n`;
                    }}
                    message += `\\n`;
                }});
                
                alert(message);
                return;
            }}
            
            // Always draw cards (deck reshuffles when empty)
            const drawn = drawCards(currentPlayer);
            
            const finalRoundMsg = finalRoundActive ? ' [FINAL ROUND]' : '';
            if (drawn > 0) {{
                alert(`${{currentPlayer.name}}'s turn!${{finalRoundMsg}}\\nDrew ${{drawn}} cards.`);
            }} else {{
                // Check if hand is actually full or if no cards could be drawn
                if (currentPlayer.hand.length >= currentPlayer.maxHandSize) {{
                    alert(`${{currentPlayer.name}}'s turn!${{finalRoundMsg}}\\nHand already full.`);
                }} else {{
                    alert(`${{currentPlayer.name}}'s turn!${{finalRoundMsg}}\\nNo cards drawn (deck may be empty - check console).`);
                    console.log('WARNING: drawCards returned 0 but hand is not full!', 
                        'Hand size:', currentPlayer.hand.length, 
                        'Max hand size:', currentPlayer.maxHandSize,
                        'Deck composition:', deckData.composition);
                }}
            }}
            
            updatePlayersPanel();
            updateGameStatus();
            drawBoard(); // Redraw to show new player's reachable tiles
        }}
        
        // Custom modal for selecting options
        function showSelectionModal(title, options) {{
            return new Promise((resolve) => {{
                // Create modal overlay
                const overlay = document.createElement('div');
                overlay.style.cssText = `
                    position: fixed;
                    top: 0;
                    left: 0;
                    width: 100%;
                    height: 100%;
                    background: rgba(0,0,0,0.7);
                    display: flex;
                    justify-content: center;
                    align-items: center;
                    z-index: 1000;
                `;
                
                // Create modal box
                const modal = document.createElement('div');
                modal.style.cssText = `
                    background: white;
                    padding: 30px;
                    border-radius: 15px;
                    max-width: 400px;
                    box-shadow: 0 10px 40px rgba(0,0,0,0.5);
                `;
                
                // Title
                const titleEl = document.createElement('h2');
                titleEl.textContent = title;
                titleEl.style.cssText = 'margin: 0 0 20px 0; color: #667eea;';
                modal.appendChild(titleEl);
                
                // Options
                options.forEach((option, idx) => {{
                    const btn = document.createElement('button');
                    btn.textContent = `${{idx + 1}}. ${{option}}`;
                    btn.style.cssText = `
                        display: block;
                        width: 100%;
                        padding: 12px;
                        margin: 8px 0;
                        background: #667eea;
                        color: white;
                        border: none;
                        border-radius: 8px;
                        cursor: pointer;
                        font-size: 14px;
                        text-align: left;
                    `;
                    btn.onmouseover = () => btn.style.background = '#5568d3';
                    btn.onmouseout = () => btn.style.background = '#667eea';
                    btn.onclick = () => {{
                        document.body.removeChild(overlay);
                        resolve(idx);
                    }};
                    modal.appendChild(btn);
                }});
                
                // Cancel button
                const cancelBtn = document.createElement('button');
                cancelBtn.textContent = 'Cancel';
                cancelBtn.style.cssText = `
                    display: block;
                    width: 100%;
                    padding: 12px;
                    margin: 15px 0 0 0;
                    background: #ccc;
                    color: #333;
                    border: none;
                    border-radius: 8px;
                    cursor: pointer;
                    font-size: 14px;
                `;
                cancelBtn.onmouseover = () => cancelBtn.style.background = '#bbb';
                cancelBtn.onmouseout = () => cancelBtn.style.background = '#ccc';
                cancelBtn.onclick = () => {{
                    document.body.removeChild(overlay);
                    resolve(null);
                }};
                modal.appendChild(cancelBtn);
                
                overlay.appendChild(modal);
                document.body.appendChild(overlay);
            }});
        }}
        
        async function testEat() {{
            const currentPlayer = playersData[currentPlayerIdx];
            
            // Check if a tile is selected
            if (!selectedTile) {{
                alert('Please select a tile first by clicking on it!');
                return;
            }}
            
            // Require discarding a card to eat
            if (currentPlayer.hand.length === 0) {{
                alert('You need at least 1 card in hand to eat!');
                return;
            }}
            
            // Check if tile is reachable
            const currentReachable = getCurrentReachableTiles();
            const isReachable = currentReachable.some(c => c.q === selectedTile.q && c.r === selectedTile.r);
            if (!isReachable) {{
                alert('You cannot reach this tile! It is outside your reachable area (shown with light green glow).');
                return;
            }}
            
            // Check if it's removed
            if (selectedTile.removed) {{
                alert('This tile has been removed from the board!');
                return;
            }}
            
            // Check if the selected tile has a dish
            if (selectedTile.empty || !selectedTile.dish) {{
                alert('This tile is empty - use "Eat Empty Tile" to remove it from the board!');
                return;
            }}
            
            // Check if it's a hot dish - need either drink token OR injera card
            if (selectedTile.hot || selectedTile.hotToken) {{
                const activeDrinks = currentPlayer.drinks.filter(d => d.tokens > 0);
                const injeraCards = currentPlayer.hand.filter(c => c.type === 'Clean Injera');
                
                if (activeDrinks.length === 0 && injeraCards.length === 0) {{
                    alert('This is a hot dish! You need either:\\n- An active drink (with tokens), OR\\n- An Injera card');
                    return;
                }}
            }}
            
            // Check if player can eat this dish
            // Need either: (1) Injera card, OR (2) Adjacent empty tile
            const injeraCards = currentPlayer.hand.filter(c => c.type === 'Clean Injera');
            const adjacentEmptyTiles = getAdjacentEmptyTiles(selectedTile.q, selectedTile.r);
            
            console.log('Injera cards:', injeraCards.length);
            console.log('Adjacent eatable empty tiles:', adjacentEmptyTiles.length);
            console.log('Adjacent tiles detail:', adjacentEmptyTiles);
            
            if (injeraCards.length === 0 && adjacentEmptyTiles.length === 0) {{
                alert('Cannot eat this dish! You need either:\\n- An Injera card in your hand, OR\\n- An adjacent eatable empty tile (with green outline)');
                return;
            }}
            
            // Build options list
            let options = [];
            let optionTypes = [];
            
            // Add injera card options
            injeraCards.forEach((card, idx) => {{
                options.push(`Injera Card #${{idx + 1}}`);
                optionTypes.push({{type: 'card', index: idx}});
            }});
            
            // Helper function to get direction label from hex coordinates
            function getDirectionLabel(fromQ, fromR, toQ, toR) {{
                const dq = toQ - fromQ;
                const dr = toR - fromR;
                
                // Hex direction mapping (in axial coordinates)
                if (dq === 1 && dr === 0) return 'SE â†˜';
                if (dq === 1 && dr === -1) return 'NE â†—';
                if (dq === 0 && dr === -1) return 'N â†‘';
                if (dq === -1 && dr === 0) return 'NW â†–';
                if (dq === -1 && dr === 1) return 'SW â†™';
                if (dq === 0 && dr === 1) return 'S â†“';
                
                return `(${{toQ}}, ${{toR}})`; // Fallback to coordinates
            }}
            
            // Add adjacent empty tile options
            adjacentEmptyTiles.forEach((tile, idx) => {{
                const direction = getDirectionLabel(selectedTile.q, selectedTile.r, tile.q, tile.r);
                const tahiniLabel = tile.tahini > 0 ? ` +${{tile.tahini}}` : '';
                options.push(`Empty Tile ${{direction}}${{tahiniLabel}}${{tile.hotToken ? ' ðŸ”¥' : ''}}`);
                optionTypes.push({{type: 'tile', tile: tile}});
            }});
            
            // If only one option, use it automatically
            let selectedOption = 0;
            if (options.length > 1) {{
                console.log('Multiple options available:', options);
                
                // Create custom modal for selection
                selectedOption = await showSelectionModal(
                    'Choose how to eat this dish:',
                    options
                );
                
                console.log('User selected option:', selectedOption);
                
                if (selectedOption === null) {{
                    console.log('User cancelled selection');
                    return;
                }}
            }} else {{
                console.log('Only one option, using automatically:', options[0]);
            }}
            
            console.log('Proceeding with option:', optionTypes[selectedOption]);
            
            const chosen = optionTypes[selectedOption];
            
            // PRE-CHECK: Will hot handling succeed? Calculate requirements first
            const dishName = selectedTile.dish;
            const wasHot = selectedTile.hot;
            const isBerbere = dishName === 'Berbere Misir';
            const needsHotDish = wasHot ? (isBerbere ? 2 : 1) : 0;
            
            let needsHotTile = 0;
            let usedEmptyTile = null;
            if (chosen.type === 'tile') {{
                usedEmptyTile = chosen.tile;
                if (usedEmptyTile.hotToken) {{
                    const isBerbereHotToken = Math.abs(usedEmptyTile.q) <= 1 && Math.abs(usedEmptyTile.r) <= 1 && 
                                             Math.abs(usedEmptyTile.q + usedEmptyTile.r) <= 1;
                    needsHotTile = isBerbereHotToken ? 2 : 1;
                }}
            }}
            
            const totalHotHandling = needsHotDish + needsHotTile;
            
            // DISCARD A CARD TO EAT (but not the resource card if using Injera)
            let availableForDiscard = currentPlayer.hand.slice(); // Copy
            
            // If using Injera card, we need to keep ONE Injera (to use it)
            // But we can discard other Injeras if we have multiple
            if (chosen.type === 'card') {{
                const injeraCount = currentPlayer.hand.filter(c => c.type === 'Clean Injera').length;
                
                if (injeraCount === 1) {{
                    // Only 1 Injera - need to use it, so can't discard it
                    // Must have other cards to discard
                    availableForDiscard = currentPlayer.hand.filter(c => c.type !== 'Clean Injera');
                    
                    if (availableForDiscard.length === 0) {{
                        alert('Cannot eat! You only have 1 Injera card in hand. You need to use it to eat and discard another card. Draw more cards or use an adjacent empty tile instead.');
                        return;
                    }}
                }} else {{
                    // Multiple Injeras - can discard all except one
                    // Remove one Injera from the available list (the one we'll use)
                    const firstInjeraIdx = availableForDiscard.findIndex(c => c.type === 'Clean Injera');
                    availableForDiscard.splice(firstInjeraIdx, 1);
                }}
            }}
            
            if (availableForDiscard.length === 0) {{
                alert('No cards available to discard! You need at least one card in hand.');
                return;
            }}
            
            const discardOptions = availableForDiscard.map((card, idx) => `${{idx + 1}}. ${{card.name}}`);
            const discardIdx = await showSelectionModal('Discard a card to eat:', discardOptions);
            if (discardIdx === null) {{
                alert('Cancelled! You must discard a card to eat.');
                return;
            }}
            
            const cardToDiscard = availableForDiscard[discardIdx];
            // Remove from actual hand
            const actualDiscardIdx = currentPlayer.hand.findIndex(c => c === cardToDiscard);
            currentPlayer.hand.splice(actualDiscardIdx, 1);
            const discardMessage = `Discarded ${{cardToDiscard.name}}`;
            
            // NOW check if player has enough resources for hot handling (AFTER discarding!)
            if (totalHotHandling > 0) {{
                const availableDrinks = currentPlayer.drinks.filter(d => d.tokens > 0).reduce((sum, d) => sum + d.tokens, 0);
                let availableInjera = currentPlayer.hand.filter(c => c.type === 'Clean Injera').length;

                // IMPORTANT: If eating with an injera card, that injera is NOT available for hot handling!
                if (chosen.type === 'card') {{
                    availableInjera = Math.max(0, availableInjera - 1);
                }}

                const totalHotResources = availableDrinks + availableInjera;
                
                if (totalHotResources < totalHotHandling) {{
                    // Not enough resources! Restore the discarded card
                    currentPlayer.hand.push(cardToDiscard);
                    alert(`Not enough resources for hot handling! Need ${{totalHotHandling}}, have ${{totalHotResources}} (drinks: ${{availableDrinks}}, injera: ${{availableInjera}})\\n\\nCard returned to hand.`);
                    return;
                }}
            }}
            
            // Execute the eating - consume resources
            let resourceMessage = '';
            let emptyTileTahini = 0;
            let resourceToConsume = chosen; // Store what we'll consume later
            
            // Helper function to get direction label
            function getDirectionLabel(fromQ, fromR, toQ, toR) {{
                const dq = toQ - fromQ;
                const dr = toR - fromR;
                if (dq === 1 && dr === 0) return 'SE â†˜';
                if (dq === 1 && dr === -1) return 'NE â†—';
                if (dq === 0 && dr === -1) return 'N â†‘';
                if (dq === -1 && dr === 0) return 'NW â†–';
                if (dq === -1 && dr === 1) return 'SW â†™';
                if (dq === 0 && dr === 1) return 'S â†“';
                return `(${{toQ}}, ${{toR}})`;
            }}
            
            if (chosen.type === 'card') {{
                resourceMessage = `Used Injera card`;
            }} else {{
                // We'll use an empty tile
                emptyTileTahini = chosen.tile.tahini || 0;
                const direction = getDirectionLabel(selectedTile.q, selectedTile.r, chosen.tile.q, chosen.tile.r);
                resourceMessage = `Used empty tile ${{direction}}`;
                if (emptyTileTahini > 0) {{
                    resourceMessage += ` with +${{emptyTileTahini}} tahini`;
                }}
                resourceMessage += ` (consumed)`;
            }}
            
            // Calculate dish value based on type
            let dishValue = 0;
            if (dishName === 'Gomen' || dishName === 'Misir Wot' || dishName === 'Shiro') {{
                // Non-hot: 1 point
                dishValue = 1;
            }} else if (dishName === 'Kik Alicha' || dishName === 'Azifa' || dishName === 'Tikel Gomen') {{
                // Medium-hot: 2 points
                dishValue = 2;
            }} else if (dishName === 'Berbere Misir') {{
                // Super-hot: flat 3 points
                dishValue = 3;
            }}
            
            const tahiniValue = selectedTile.tahini || 0;
            const totalValue = dishValue + tahiniValue;
            
            // Award points and track eating
            currentPlayer.score += totalValue;
            // Add tahini points from empty tile if used
            if (emptyTileTahini > 0) {{
                currentPlayer.score += emptyTileTahini;
            }}
            currentPlayer.eaten.push(dishName);
            
            // Track super-hot count (flat scoring, no progression)
            if (dishName === 'Berbere Misir') {{
                currentPlayer.superHotCount = (currentPlayer.superHotCount || 0) + 1;
            }}
            
            // Check for bonuses
            let bonusMessage = '';
            
            // Count this dish type
            if (!currentPlayer.dishCounts) currentPlayer.dishCounts = {{}};
            currentPlayer.dishCounts[dishName] = (currentPlayer.dishCounts[dishName] || 0) + 1;
            
            // Completion bonuses (5, 6, 7 tiles) are calculated at end of game
            // Variety bonus is also calculated at end of game

            // CONSUME THE EATING RESOURCE NOW (before hot handling)
            // This prevents offering the same injera card for both eating and hot handling
            if (resourceToConsume.type === 'card') {{
                // Remove the injera card used for eating
                const cardIdx = currentPlayer.hand.findIndex(c => c.type === 'Clean Injera');
                if (cardIdx === -1) {{
                    alert('ERROR: No Injera card found! This should not happen.');
                    return;
                }}
                currentPlayer.hand.splice(cardIdx, 1);
            }} else {{
                // Remove the empty tile (do this now, not later)
                resourceToConsume.tile.removed = true;
            }}

            // If it was a hot dish OR used hot empty tile, consume drink token(s)
            // Berbere Misir is EXTRA HOT - requires 2x handling
            // (Already calculated above in pre-check: isBerbere, needsHotDish, needsHotTile, totalHotHandling)
            let drinkMessage = '';
            
            if (totalHotHandling > 0) {{
                // Handle each hot requirement
                for (let hotIdx = 0; hotIdx < totalHotHandling; hotIdx++) {{
                    const activeDrinks = currentPlayer.drinks.filter(d => d.tokens > 0);
                    const injeraCards = currentPlayer.hand.filter(c => c.type === 'Clean Injera');
                    
                    // Build fresh options for this hot handling
                    let hotOptions = [];
                    let hotOptionTypes = [];
                    
                    activeDrinks.forEach(d => {{
                        hotOptions.push(`Use ${{d.type}} token (${{d.tokens}} left)`);
                        hotOptionTypes.push({{type: 'drink', drink: d}});
                    }});
                    
                    injeraCards.forEach((card, idx) => {{
                        hotOptions.push(`Use Injera Card #${{idx + 1}}`);
                        hotOptionTypes.push({{type: 'injera', index: idx}});
                    }});
                    
                    if (hotOptions.length === 0) {{
                        alert('Not enough resources to handle all hot requirements!');
                        return;
                    }}
                    
                    // Determine what we're handling
                    let hotType = '';
                    if (hotIdx === 0 && needsHotDish) hotType = 'hot dish';
                    else hotType = 'hot tile';
                    
                    // Choose which to use
                    let selectedHotOption = 0;
                    if (hotOptions.length > 1) {{
                        const prompt = totalHotHandling > 1 
                            ? `Handle ${{hotType}} (${{hotIdx + 1}} of ${{totalHotHandling}}):`
                            : `Handle ${{hotType}}:`;
                        selectedHotOption = await showSelectionModal(prompt, hotOptions);
                        if (selectedHotOption === null) {{
                            // User tried to cancel, but we already validated resources exist
                            // Auto-select first option since canceling would waste resources
                            selectedHotOption = 0;
                            alert('Hot handling is required. Auto-selected first available resource.');
                        }}
                    }}
                    
                    const hotChoice = hotOptionTypes[selectedHotOption];
                    
                    if (hotChoice.type === 'drink') {{
                        // Use drink token
                        const usedDrink = hotChoice.drink;
                        const actualDrinkIdx = currentPlayer.drinks.findIndex(d => d.type === usedDrink.type);
                        
                        currentPlayer.drinks[actualDrinkIdx].tokens--;
                        
                        // No immediate beer penalty - applied when finished
                        
                        // Award points for drinking
                        let drinkPoints = 0;
                        if (usedDrink.type === 'Coffee') drinkPoints = 1;
                        else if (usedDrink.type === 'Beer') drinkPoints = 3;
                        
                        currentPlayer.score += drinkPoints;
                        
                        drinkMessage += `\\nUsed ${{usedDrink.type}} for ${{hotType}} (+${{drinkPoints}} pts, ${{currentPlayer.drinks[actualDrinkIdx].tokens}} left)`;
                        
                        if (currentPlayer.drinks[actualDrinkIdx].tokens === 0) {{
                            if (usedDrink.type === 'Coffee') {{
                                currentPlayer.handSizeModifier = (currentPlayer.handSizeModifier || 0) + 1;
                                currentPlayer.maxHandSize = currentPlayer.baseHandSize + currentPlayer.handSizeModifier;
                                drinkMessage += ` - Coffee finished! +1 hand size. Turn ends!`;
                                currentPlayer.drinks.splice(actualDrinkIdx, 1);
                                window.shouldEndTurnAfterAction = true;
                            }} else if (usedDrink.type === 'Water') {{
                                if (!waterRefilledThisTurn[currentPlayerIdx]) {{
                                    waterRefilledThisTurn[currentPlayerIdx] = true;
                                    const cardsNeeded = currentPlayer.maxHandSize - currentPlayer.hand.length;
                                    if (cardsNeeded > 0) {{
                                        const drawn = drawCards(currentPlayer, cardsNeeded);
                                        drinkMessage += ` - Water finished! Refilled hand! Drew ${{drawn}} cards`;
                                    }} else {{
                                        drinkMessage += ` - Water finished! Hand was already full`;
                                    }}
                                }} else {{
                                    drinkMessage += ` - Second Water finished! Turn ends!`;
                                    window.shouldEndTurnAfterAction = true;
                                }}
                                currentPlayer.drinks.splice(actualDrinkIdx, 1);
                            }} else if (usedDrink.type === 'Beer') {{
                                currentPlayer.handSizeModifier = (currentPlayer.handSizeModifier || 0) - 1;
                                currentPlayer.maxHandSize = currentPlayer.baseHandSize + currentPlayer.handSizeModifier;
                                drinkMessage += ` - Beer finished! -1 hand size. Turn ends!`;
                                currentPlayer.drinks.splice(actualDrinkIdx, 1);
                                window.shouldEndTurnAfterAction = true;
                            }}
                        }}
                    }} else {{
                        // Use injera card
                        const cardIdx = currentPlayer.hand.findIndex(c => c.type === 'Clean Injera');
                        currentPlayer.hand.splice(cardIdx, 1);
                        drinkMessage += `\\nUsed Injera card for ${{hotType}}`;
                    }}
                }}
            }}

            // Resource (Injera card or empty tile) was already consumed before hot handling
            // (This prevents offering the eating injera for hot handling)

            // Show combined message
            const dishTileTahiniBonus = tahiniValue > 0 ? ` (including +${{tahiniValue}} tahini on dish tile)` : '';
            const emptyTileBonus = emptyTileTahini > 0 ? ` + ${{emptyTileTahini}} from empty tile tahini` : '';
            alert(`${{discardMessage}}. ${{resourceMessage}} to eat ${{dishName}} for ${{totalValue}} points${{dishTileTahiniBonus}}${{emptyTileBonus}}!${{drinkMessage}}${{bonusMessage}}${{wasHot ? '\\n(Hot token remains on tile)' : ''}}`);
            
            // Mark dish tile as empty and preserve hot token if it was hot
            selectedTile.empty = true;
            selectedTile.dish = null;
            selectedTile.tahini = 0; // Clear tahini - it was consumed with the dish
            
            // Berbere Misir (super-hot) ALWAYS leaves a hot token
            // Other hot dishes also leave hot tokens
            if (wasHot || dishName === 'Berbere Misir') {{
                selectedTile.hotToken = true;
                selectedTile.hot = false;
            }}
            
            // Recalculate which tiles can be eaten (new empty tile created)
            updateCanEatEmpty();
            
            // Check if this was the last dish
            const dishesRemaining = boardData.filter(t => !t.empty && !t.removed).length;
            if (dishesRemaining === 0 && !finalRoundActive) {{
                finalRoundActive = true;
                finalRoundStartPlayer = currentPlayerIdx;
                alert(`ðŸŽŠ FINAL DISH EATEN! ðŸŽŠ\\n\\nAll other players will get one more turn, then the game ends!`);
            }}
            
            // Clear selection after eating
            selectedTile = null;

            drawBoard();
            updatePlayersPanel();
            updateGameStatus();

            // Check if turn should end due to Coffee/Beer finished
            if (window.shouldEndTurnAfterAction) {{
                window.shouldEndTurnAfterAction = false;
                alert('Your turn ends because your drink was finished!');
                nextTurn();
            }}
        }}

        function getAdjacentEmptyTiles(q, r) {{
            // Find all adjacent empty tiles that CAN BE EATEN (not removed AND canEatEmpty AND reachable)
            const neighbors = getNeighbors(q, r);
            const eatableEmptyNeighbors = [];
            const currentReachable = getCurrentReachableTiles();
            
            neighbors.forEach(nCoord => {{
                const neighbor = boardData.find(t => t.q === nCoord.q && t.r === nCoord.r);
                // Check if empty, not removed, can be eaten, AND is reachable by current player
                const isReachable = currentReachable.some(c => c.q === nCoord.q && c.r === nCoord.r);
                if (neighbor && neighbor.empty && !neighbor.removed && neighbor.canEatEmpty && isReachable) {{
                    eatableEmptyNeighbors.push(neighbor);
                }}
            }});
            
            if (eatableEmptyNeighbors.length > 0) {{
                console.log(`Tile (${{q}}, ${{r}}) has ${{eatableEmptyNeighbors.length}} eatable empty neighbors`);
            }}
            
            return eatableEmptyNeighbors;
        }}
        
        async function eatEmptyTile() {{
            const currentPlayer = playersData[currentPlayerIdx];
            
            // Check if a tile is selected
            if (!selectedTile) {{
                alert('Please select a tile first by clicking on it!');
                return;
            }}
            
            // Require discarding a card to eat
            if (currentPlayer.hand.length === 0) {{
                alert('You need at least 1 card in hand to eat!');
                return;
            }}
            
            // Check if tile is reachable
            const currentReachable = getCurrentReachableTiles();
            const isReachable = currentReachable.some(c => c.q === selectedTile.q && c.r === selectedTile.r);
            if (!isReachable) {{
                alert('You cannot reach this tile! It is outside your reachable area (shown with light green glow).');
                return;
            }}
            
            // Check if it's already removed
            if (selectedTile.removed) {{
                alert('This tile has already been removed!');
                return;
            }}
            
            // Check if it's empty
            if (!selectedTile.empty) {{
                alert('This tile has a dish on it! Eat the dish first.');
                return;
            }}
            
            // Check if it's hot (has hot token) - need drink or injera
            if (selectedTile.hotToken) {{
                const activeDrinks = currentPlayer.drinks.filter(d => d.tokens > 0);
                const injeraCards = currentPlayer.hand.filter(c => c.type === 'Clean Injera');
                
                if (activeDrinks.length === 0 && injeraCards.length === 0) {{
                    alert('This empty tile has a hot token! You need either:\\n- An active drink (with tokens), OR\\n- An Injera card');
                    return;
                }}
            }}
            
            // Check if it can be eaten (has 2+ off-board neighbors)
            if (!selectedTile.canEatEmpty) {{
                alert('This empty tile cannot be eaten - it needs at least 2 adjacent positions that are nothing (off-board or removed)!');
                return;
            }}
            
            // DISCARD A CARD - required for eating empty tile
            let discardedCard;
            if (currentPlayer.hand.length === 1) {{
                // Only one card, discard it
                discardedCard = currentPlayer.hand.pop();
            }} else {{
                // Let player choose which card to discard
                const cardOptions = currentPlayer.hand.map((c, i) => `${{i + 1}}. ${{c.name}}`);
                const choice = await showSelectionModal('Choose a card to discard:', cardOptions);
                if (choice === null) return;
                discardedCard = currentPlayer.hand.splice(choice, 1)[0];
            }}
            
            // Handle hot token if present
            let hotMessage = '';
            if (selectedTile.hotToken) {{
                // Check if this is a Berbere hot token (center cluster)
                const isBerbereHotToken = Math.abs(selectedTile.q) <= 1 && Math.abs(selectedTile.r) <= 1 && 
                                         Math.abs(selectedTile.q + selectedTile.r) <= 1;
                const hotHandlingNeeded = isBerbereHotToken ? 2 : 1; // Berbere requires 2x handling
                
                // Handle each hot requirement
                for (let hotIdx = 0; hotIdx < hotHandlingNeeded; hotIdx++) {{
                    const activeDrinks = currentPlayer.drinks.filter(d => d.tokens > 0);
                    const injeraCards = currentPlayer.hand.filter(c => c.type === 'Clean Injera');
                    
                    // Build options
                    let hotOptions = [];
                    let hotOptionTypes = [];
                    
                    activeDrinks.forEach(d => {{
                        hotOptions.push(`Use ${{d.type}} token (${{d.tokens}} left)`);
                        hotOptionTypes.push({{type: 'drink', drink: d}});
                    }});
                    
                    injeraCards.forEach((card, idx) => {{
                        hotOptions.push(`Use Injera Card #${{idx + 1}}`);
                        hotOptionTypes.push({{type: 'injera', index: idx}});
                    }});
                    
                    if (hotOptions.length === 0) {{
                        alert('Not enough resources to handle hot tile!');
                        return;
                    }}
                    
                    // Choose
                    let selectedHotOption = 0;
                    if (hotOptions.length > 1) {{
                        const prompt = hotHandlingNeeded > 1 
                            ? `Hot empty tile! Extra hot! (${{hotIdx + 1}} of ${{hotHandlingNeeded}}):`
                            : 'Hot empty tile! Choose how to handle it:';
                        selectedHotOption = await showSelectionModal(prompt, hotOptions);
                        if (selectedHotOption === null) return;
                    }}
                    
                    const hotChoice = hotOptionTypes[selectedHotOption];
                    
                    if (hotChoice.type === 'drink') {{
                        const usedDrink = hotChoice.drink;
                        const actualDrinkIdx = currentPlayer.drinks.findIndex(d => d.type === usedDrink.type);
                        
                        currentPlayer.drinks[actualDrinkIdx].tokens--;
                        
                        // No immediate beer penalty - applied when finished
                        
                        let drinkPoints = 0;
                        if (usedDrink.type === 'Coffee') drinkPoints = 1;
                        else if (usedDrink.type === 'Beer') drinkPoints = 3;
                        
                        currentPlayer.score += drinkPoints;
                        hotMessage += `\\nUsed ${{usedDrink.type}} for hot tile (+${{drinkPoints}} pts, ${{currentPlayer.drinks[actualDrinkIdx].tokens}} left)`;
                        
                        if (currentPlayer.drinks[actualDrinkIdx].tokens === 0) {{
                            if (usedDrink.type === 'Coffee') {{
                                currentPlayer.handSizeModifier = (currentPlayer.handSizeModifier || 0) + 1;
                                currentPlayer.maxHandSize = currentPlayer.baseHandSize + currentPlayer.handSizeModifier;
                                hotMessage += ` - Coffee finished! +1 hand size. Turn ends!`;
                                currentPlayer.drinks.splice(actualDrinkIdx, 1);
                                window.shouldEndTurnAfterAction = true;
                            }} else if (usedDrink.type === 'Water') {{
                                if (!waterRefilledThisTurn[currentPlayerIdx]) {{
                                    waterRefilledThisTurn[currentPlayerIdx] = true;
                                    const cardsNeeded = currentPlayer.maxHandSize - currentPlayer.hand.length;
                                    if (cardsNeeded > 0) {{
                                        const drawn = drawCards(currentPlayer, cardsNeeded);
                                        hotMessage += ` - Water finished! Refilled hand! Drew ${{drawn}} cards`;
                                    }} else {{
                                        hotMessage += ` - Water finished! Hand was already full`;
                                    }}
                                }} else {{
                                    hotMessage += ` - Second Water finished! Turn ends!`;
                                    window.shouldEndTurnAfterAction = true;
                                }}
                                currentPlayer.drinks.splice(actualDrinkIdx, 1);
                            }} else if (usedDrink.type === 'Beer') {{
                                currentPlayer.handSizeModifier = (currentPlayer.handSizeModifier || 0) - 1;
                                currentPlayer.maxHandSize = currentPlayer.baseHandSize + currentPlayer.handSizeModifier;
                                hotMessage += ` - Beer finished! -1 hand size. Turn ends!`;
                                currentPlayer.drinks.splice(actualDrinkIdx, 1);
                                window.shouldEndTurnAfterAction = true;
                            }}
                        }}
                    }} else {{
                        const cardIdx = currentPlayer.hand.findIndex(c => c.type === 'Clean Injera');
                        currentPlayer.hand.splice(cardIdx, 1);
                        hotMessage += `\\nUsed Injera card for hot tile`;
                    }}
                }}
            }}

            // Award points for tahini tokens on empty tile
            const tahiniPoints = selectedTile.tahini || 0;
            console.log('Empty tile tahini:', tahiniPoints, 'Current score:', currentPlayer.score);
            if (tahiniPoints > 0) {{
                currentPlayer.score += tahiniPoints;
                console.log('Added tahini points, new score:', currentPlayer.score);
            }}
            
            // Remove the tile
            selectedTile.removed = true;
            
            // Recalculate which empty tiles can now be eaten (since we created a new gap)
            updateCanEatEmpty();
            
            const pointsMessage = tahiniPoints > 0 ? ` +${{tahiniPoints}} points from tahini!` : '';
            alert(`Discarded ${{discardedCard.name}}. ${{currentPlayer.name}} ate the empty injera tile!${{pointsMessage}}${{hotMessage}} It's now removed from the board.`);
            
            // Update display
            updatePlayersPanel();
            updateGameStatus();
            
            // Clear selection
            selectedTile = null;
            
            drawBoard();
            updatePlayersPanel();
            updateGameStatus();

            // Check if turn should end due to Coffee/Beer finished
            if (window.shouldEndTurnAfterAction) {{
                window.shouldEndTurnAfterAction = false;
                alert('Your turn ends because your drink was finished!');
                nextTurn();
            }}
        }}

        function updateCanEatEmpty() {{
            // Recalculate canEatEmpty for all empty tiles
            let eatableCount = 0;
            boardData.forEach(tile => {{
                if (tile.empty && !tile.removed) {{
                    // Count neighbors that are nothing (off-board or removed)
                    let emptyNeighbors = 0;
                    const neighbors = getNeighbors(tile.q, tile.r);
                    
                    neighbors.forEach(nCoord => {{
                        const neighbor = boardData.find(t => t.q === nCoord.q && t.r === nCoord.r);
                        if (!neighbor) {{
                            // Off board
                            emptyNeighbors++;
                        }} else if (neighbor.removed) {{
                            // Removed tile
                            emptyNeighbors++;
                        }}
                    }});
                    
                    tile.canEatEmpty = emptyNeighbors >= 2;
                    if (tile.canEatEmpty) eatableCount++;
                }}
            }});
            console.log('updateCanEatEmpty: Found', eatableCount, 'eatable empty tiles');
        }}
        
        function getNeighbors(q, r) {{
            // Return all 6 neighbor coordinates
            return [
                {{q: q + 1, r: r}},
                {{q: q + 1, r: r - 1}},
                {{q: q, r: r - 1}},
                {{q: q - 1, r: r}},
                {{q: q - 1, r: r + 1}},
                {{q: q, r: r + 1}}
            ];
        }}
        
        function getTrianglesContaining(q, r) {{
            // Find all possible triangles (3 adjacent tiles) that contain this tile
            const triangles = [];
            const neighbors = getNeighbors(q, r);
            
            // Check each pair of neighbors to see if they form a triangle with this tile
            for (let i = 0; i < neighbors.length; i++) {{
                for (let j = i + 1; j < neighbors.length; j++) {{
                    const n1 = neighbors[i];
                    const n2 = neighbors[j];
                    
                    // Check if n1 and n2 are adjacent to each other
                    const n1Neighbors = getNeighbors(n1.q, n1.r);
                    const areAdjacent = n1Neighbors.some(n => n.q === n2.q && n.r === n2.r);
                    
                    if (areAdjacent) {{
                        // This is a valid triangle
                        const tile1 = boardData.find(t => t.q === q && t.r === r);
                        const tile2 = boardData.find(t => t.q === n1.q && t.r === n1.r);
                        const tile3 = boardData.find(t => t.q === n2.q && t.r === n2.r);
                        
                        if (tile1 && tile2 && tile3 && !tile1.removed && !tile2.removed && !tile3.removed) {{
                            triangles.push([tile1, tile2, tile3]);
                        }}
                    }}
                }}
            }}
            
            return triangles;
        }}
        
        async function addTahini() {{
            const currentPlayer = playersData[currentPlayerIdx];
            
            // Check if player has tahini card
            const tahiniCards = currentPlayer.hand.filter(c => c.name === 'Tahini');
            if (tahiniCards.length === 0) {{
                alert('No Tahini cards in hand!');
                return;
            }}
            
            if (!selectedTile) {{
                alert('Please select a tile first by clicking on it! This will be the top of the triangle.');
                return;
            }}
            
            // Check if selected tile is reachable
            const currentReachable = getCurrentReachableTiles();
            const isReachable = currentReachable.some(c => c.q === selectedTile.q && c.r === selectedTile.r);
            if (!isReachable) {{
                alert('You cannot place tahini on this tile! It is outside your reachable area (shown with light green glow).');
                return;
            }}
            
            if (selectedTile.removed) {{
                alert('This tile has been removed!');
                return;
            }}
            
            // Find all triangles containing this tile as the "top"
            const triangles = getTrianglesContaining(selectedTile.q, selectedTile.r);
            
            if (triangles.length === 0) {{
                alert('No valid triangles found! Tahini must be placed on a triangle of 3 adjacent tiles.');
                return;
            }}
            
            // Categorize triangles by orientation relative to selected tile
            const leftTriangles = [];
            const rightTriangles = [];
            
            triangles.forEach(tri => {{
                // Selected tile should be the TOP of the triangle
                // We need to identify which of the 3 tiles is highest (smallest r value)
                const sorted = [...tri].sort((a, b) => {{
                    if (a.r !== b.r) return a.r - b.r; // Smaller r = higher up
                    return a.q - b.q;
                }});
                
                const top = sorted[0];
                const bottom1 = sorted[1];
                const bottom2 = sorted[2];
                
                // Only include triangles where selected tile is the top
                if (top.q !== selectedTile.q || top.r !== selectedTile.r) {{
                    return; // Skip this triangle
                }}
                
                // Determine if triangle leans left or right based on bottom tiles
                // Left-leaning: bottom tiles are to the lower-left (smaller q)
                // Right-leaning: bottom tiles are to the lower-right (larger q)
                const avgQ = (bottom1.q + bottom2.q) / 2;
                
                if (avgQ < top.q) {{
                    leftTriangles.push([top, bottom1, bottom2]);
                }} else if (avgQ > top.q) {{
                    rightTriangles.push([top, bottom1, bottom2]);
                }}
            }});
            
            // Build user-friendly options (SWAPPED arrows)
            const options = [];
            const triangleChoices = [];
            
            if (leftTriangles.length > 0) {{
                options.push('â—£ Left-leaning triangle');
                triangleChoices.push(leftTriangles[0]);
            }}
            
            if (rightTriangles.length > 0) {{
                options.push('â—¢ Right-leaning triangle');
                triangleChoices.push(rightTriangles[0]);
            }}
            
            if (options.length === 0) {{
                alert('No valid triangles found with this tile as the top!');
                return;
            }}
            
            // Choose which triangle orientation
            let selectedIdx = 0;
            if (options.length > 1) {{
                selectedIdx = await showSelectionModal('Choose triangle orientation:', options);
                if (selectedIdx === null) return;
            }}
            
            const triangle = triangleChoices[selectedIdx];
            
            // Add tahini to all 3 tiles in triangle (only if they don't have dishes or are not removed)
            const tokensToAdd = 1;
            let tilesAffected = 0;
            triangle.forEach(tile => {{
                if (!tile.removed) {{
                    tile.tahini = (tile.tahini || 0) + tokensToAdd;
                    tilesAffected++;
                }}
            }});
            
            // Remove tahini card from hand
            const cardIdx = currentPlayer.hand.findIndex(c => c.name === 'Tahini');
            currentPlayer.hand.splice(cardIdx, 1);
            
            alert(`Added ${{tokensToAdd}} tahini token to ${{options[selectedIdx]}} (${{tilesAffected}} tiles)!`);
            
            drawBoard();
            updatePlayersPanel();
        }}
        
        async function playDrinkCard() {{
            const currentPlayer = playersData[currentPlayerIdx];
            
            // Check if player already has an active drink in their cup
            if (currentPlayer.drinks && currentPlayer.drinks.length > 0) {{
                const activeDrink = currentPlayer.drinks[0];
                alert(`Your cup is already filled with ${{activeDrink.type}} (${{activeDrink.tokens}} tokens).\\nYou must finish it before ordering another drink!`);
                return;
            }}
            
            // Find drink cards in hand
            const drinkCards = currentPlayer.hand.filter(c => c.type === 'Drink');
            
            if (drinkCards.length === 0) {{
                alert('No drink order cards in hand!');
                return;
            }}
            
            // Show selection modal
            const options = drinkCards.map((card, idx) => card.name);
            const selectedIdx = await showSelectionModal('Choose a drink to order:', options);
            
            if (selectedIdx === null) return;
            
            const selectedCard = drinkCards[selectedIdx];
            
            // Remove card from hand (it's being discarded/used)
            const handIdx = currentPlayer.hand.findIndex(c => c.name === selectedCard.name && c.type === 'Drink');
            currentPlayer.hand.splice(handIdx, 1);
            
            // Extract drink type from card name (e.g., "Order Coffee" -> "Coffee")
            const drinkType = selectedCard.name.replace('Order ', '');
            
            // Fill the cup with the drink (3 tokens)
            currentPlayer.drinks.push({{
                type: drinkType,
                tokens: 3
            }});
            
            alert(`Ordered ${{drinkType}}! Your cup is filled with 3 tokens. The order card has been discarded.`);
            
            updatePlayersPanel();
            updateGameStatus();
        }}
        
        async function playRotateCard() {{
            const currentPlayer = playersData[currentPlayerIdx];
            
            // Find rotate cards in hand
            const rotateCards = currentPlayer.hand.filter(c => c.name === 'Rotate Injera');
            
            if (rotateCards.length === 0) {{
                alert('No Rotate cards in hand!');
                return;
            }}
            
            // Ask for direction
            const direction = await showSelectionModal('Choose rotation direction:', [
                'Clockwise (60Â°)',
                'Counter-clockwise (-60Â°)'
            ]);
            
            if (direction === null) return;
            
            // Rotate all tiles by transforming their coordinates
            // Hex rotation by 60Â° clockwise: (q, r) -> (-r, q+r)
            // Hex rotation by 60Â° counter-clockwise: (q, r) -> (-q-r, q)
            
            boardData.forEach(tile => {{
                const oldQ = tile.q;
                const oldR = tile.r;
                
                if (direction === 0) {{
                    // Clockwise 60Â°: (q, r) -> (-r, q+r)
                    tile.q = -oldR;
                    tile.r = oldQ + oldR;
                }} else {{
                    // Counter-clockwise 60Â°: (q, r) -> (q+r, -q)
                    tile.q = oldQ + oldR;
                    tile.r = -oldQ;
                }}
            }});
            
            // Remove card from hand
            const cardIdx = currentPlayer.hand.findIndex(c => c.name === 'Rotate Injera');
            currentPlayer.hand.splice(cardIdx, 1);
            
            alert(`Rotated board ${{direction === 0 ? 'clockwise' : 'counter-clockwise'}}!`);
            
            // Recalculate everything with new coordinates
            updateCanEatEmpty();
            drawBoard();
            updatePlayersPanel();
        }}
        
        // Removed duplicate function below
        
        async function drinkToken() {{
            const currentPlayer = playersData[currentPlayerIdx];
            
            // Find drinks with tokens
            const activeDrinks = currentPlayer.drinks.filter(d => d.tokens > 0);
            
            if (activeDrinks.length === 0) {{
                alert('No active drinks with tokens!');
                return;
            }}
            
            // Show selection modal
            let selectedIdx = 0;
            if (activeDrinks.length > 1) {{
                const options = activeDrinks.map(d => `${{d.type}} (${{d.tokens}} tokens)`);
                selectedIdx = await showSelectionModal('Choose which drink to consume:', options);
                if (selectedIdx === null) return;
            }}
            
            const selectedDrink = activeDrinks[selectedIdx];
            
            // Find the actual drink in the player's drinks array (match by type only, tokens change)
            const drinkIdx = currentPlayer.drinks.findIndex(d => d.type === selectedDrink.type);
            
            // Consume token
            currentPlayer.drinks[drinkIdx].tokens--;
            
            // Award points
            let points = 0;
            if (selectedDrink.type === 'Coffee') points = 1;
            else if (selectedDrink.type === 'Beer') points = 3;
            // Water gives 0 points but has special ability when finished
            
            currentPlayer.score += points;
            
            console.log('=== DRINK DEBUG ===');
            console.log('Drink type:', selectedDrink.type);
            console.log('Tokens after decrement:', currentPlayer.drinks[drinkIdx].tokens);
            // No immediate beer penalty - applied when drink finishes
            
            // Check if finished
            if (currentPlayer.drinks[drinkIdx].tokens === 0) {{
                let finishMessage = '';
                let shouldEndTurn = false;
                if (selectedDrink.type === 'Coffee') {{
                    currentPlayer.handSizeModifier = (currentPlayer.handSizeModifier || 0) + 1;
                    currentPlayer.maxHandSize = currentPlayer.baseHandSize + currentPlayer.handSizeModifier;
                    finishMessage = ` Coffee finished! +1 hand size (now ${{currentPlayer.maxHandSize}}). Turn ends!`;
                    currentPlayer.drinks.splice(drinkIdx, 1);
                    shouldEndTurn = true;
                }} else if (selectedDrink.type === 'Beer') {{
                    currentPlayer.handSizeModifier = (currentPlayer.handSizeModifier || 0) - 1;
                    currentPlayer.maxHandSize = currentPlayer.baseHandSize + currentPlayer.handSizeModifier;
                    finishMessage = ` Beer finished! -1 hand size (now ${{currentPlayer.maxHandSize}}). Turn ends!`;
                    currentPlayer.drinks.splice(drinkIdx, 1);
                    shouldEndTurn = true;
                }} else if (selectedDrink.type === 'Water') {{
                    if (!waterRefilledThisTurn[currentPlayerIdx]) {{
                        waterRefilledThisTurn[currentPlayerIdx] = true;
                        const cardsNeeded = currentPlayer.maxHandSize - currentPlayer.hand.length;
                        const drawn = cardsNeeded > 0 ? drawCards(currentPlayer, cardsNeeded) : 0;
                        finishMessage = drawn > 0
                            ? ` Water finished! Refilled hand! Drew ${{drawn}} cards.`
                            : ` Water finished! Hand was already full.`;
                    }} else {{
                        finishMessage = ` Second Water finished! Turn ends!`;
                        shouldEndTurn = true;
                    }}
                    currentPlayer.drinks.splice(drinkIdx, 1);
                }}

                alert(`Drank ${{selectedDrink.type}} token! +${{points}} points.${{finishMessage}}`);
                updatePlayersPanel();
                updateGameStatus();
                if (shouldEndTurn) {{
                    alert('Your turn ends because your drink was finished!');
                    nextTurn();
                }}
            }} else {{
                alert(`Drank ${{selectedDrink.type}} token! +${{points}} points. ${{currentPlayer.drinks[drinkIdx].tokens}} tokens remaining.`);
                updatePlayersPanel();
                updateGameStatus();
            }}
        }}
        
        function debugHand() {{
            const currentPlayer = playersData[currentPlayerIdx];
            console.log('Current player:', currentPlayer.name);
            console.log('Hand:', currentPlayer.hand);
            console.log('Injera cards:', currentPlayer.hand.filter(c => c.type === 'Clean Injera'));
            alert('Check the browser console (F12) for detailed hand information');
        }}
        
        function debugGiveBeer() {{
            const currentPlayer = playersData[currentPlayerIdx];
            currentPlayer.drinks.push({{
                type: 'Beer',
                tokens: 3
            }});
            alert('DEBUG: Gave you Beer with 3 tokens!');
            updatePlayersPanel();
            updateGameStatus();
        }}
        
        // Handle canvas clicks
        canvas.addEventListener('click', (e) => {{
            const rect = canvas.getBoundingClientRect();
            const clickX = e.clientX - rect.left;
            const clickY = e.clientY - rect.top;
            
            // Find closest tile
            let closestTile = null;
            let minDist = Infinity;
            
            boardData.forEach(tile => {{
                const {{x, y}} = hexToPixel(tile.q, tile.r);
                const dist = Math.sqrt((clickX - x) ** 2 + (clickY - y) ** 2);
                if (dist < minDist && dist < hexSize) {{
                    minDist = dist;
                    closestTile = tile;
                }}
            }});
            
            if (closestTile) {{
                selectedTile = closestTile;
                console.log('Selected:', closestTile);
                drawBoard();
            }}
        }});
        
        // Initial draw
        randomizeInitialState(); // Randomize cards on each game start
        console.log('Initial board data:', boardData.filter(t => t.empty).map(t => ({{q: t.q, r: t.r, canEatEmpty: t.canEatEmpty}})));
        updateCanEatEmpty();
        console.log('After updateCanEatEmpty:', boardData.filter(t => t.empty).map(t => ({{q: t.q, r: t.r, canEatEmpty: t.canEatEmpty}})));
        drawBoard();
        updatePlayersPanel();
        updateGameStatus();
    </script>
</body>
</html>"""
    
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(html_content)
    
    print(f"âœ“ Web GUI generated: {output_file}")
    print(f"  Open this file in your web browser to play!")
    
    return output_file


# ============================================================================
# MAIN - Generate the web GUI
# ============================================================================

if __name__ == "__main__":
    import random
    import time
    
    # Set random seed based on current time to get different games each run
    random.seed(time.time())
    
    print("=== Generating Injera Board Game Web GUI ===\n")
    
    # Allow setting number of players (2-6)
    import sys
    num_players = 2  # Default
    if len(sys.argv) > 1:
        try:
            num_players = int(sys.argv[1])
            if num_players < 2 or num_players > 6:
                print(f"Invalid number of players: {num_players}. Using default: 2")
                num_players = 2
            else:
                print(f"Setting up game for {num_players} players")
        except ValueError:
            print(f"Invalid argument. Using default: 2 players")
    
    # Create a game instance
    board = Board(radius=5)
    board.place_dishes(num_players=num_players)
    
    # Create deck
    deck = Deck()
    print(f"Deck created with {len(deck.cards)} cards")
    
    # Create players and deal starting hands
    # Hand size based on player count: 2-4 players: 4 cards, 5-6 players: 3 cards
    if num_players <= 4:
        starting_hand_size = 4
    else:
        starting_hand_size = 3
    
    players = []
    for i in range(num_players):
        player = Player(name=f"Player {i+1}", position=i, base_hand_size=starting_hand_size)
        # Draw starting cards from deck
        starting_hand = deck.draw_multiple(starting_hand_size)
        for card in starting_hand:
            player.draw_card(card)
        players.append(player)
        print(f"{player.name} dealt {len(starting_hand)} cards (base hand size: {starting_hand_size})")
    
    # Generate HTML file
    output_file = generate_web_gui(board, players, deck, num_players, "injera_game.html")
    
    print("\nâœ“ Done! Open injera_game.html in your browser to see the game!")
