"""
Injera Game - Player Setup Tool
Modifies your existing HTML file to add/remove players and set AI status

Usage:
    python setup_players.py

This will:
1. Ask for number of players (2-6)
2. Ask for each player's name and AI status
3. Update your injera_game.html file with the new configuration
"""

import json
import re
import sys


def get_player_config():
    """Interactive prompts to get player configuration"""
    print("=" * 70)
    print("🍽️  INJERA GAME - PLAYER SETUP")
    print("=" * 70)
    print()
    
    # Get number of players
    while True:
        try:
            num_players = int(input("How many players? (2-6): "))
            if 2 <= num_players <= 6:
                break
            print("❌ Please enter a number between 2 and 6.")
        except ValueError:
            print("❌ Please enter a valid number.")
    
    print()
    
    # Determine base hand size
    if num_players <= 4:
        base_hand_size = 4
    else:
        base_hand_size = 3
    
    # Get player configurations
    players = []
    for i in range(num_players):
        print(f"--- Player {i+1} (Position {i}) ---")
        
        # Get name
        default_name = f"Player {i+1}"
        name = input(f"  Name [default: {default_name}]: ").strip()
        if not name:
            name = default_name
        
        # Get AI status
        while True:
            ai_input = input(f"  Is '{name}' a Neural AI? (y/n) [default: n]: ").strip().lower()
            if not ai_input or ai_input in ['n', 'no']:
                is_ai = False
                ai_level = None
                break
            if ai_input in ['y', 'yes']:
                is_ai = True
                ai_level = "neural"
                break
            print("  ❌ Please enter 'y' or 'n'")
        
        players.append({
            'name': name,
            'position': i,
            'is_ai': is_ai,
            'ai_level': ai_level,
            'base_hand_size': base_hand_size
        })
        print()
    
    # Special cards configuration
    print("--- Special Cards (Advanced Mode) ---")
    while True:
        sc_input = input("  Enable special cards? (y/n) [default: n]: ").strip().lower()
        if not sc_input or sc_input in ['n', 'no']:
            special_cards_config = None
            break
        elif sc_input in ['y', 'yes']:
            special_cards_config = {'deal': 3, 'keep': 2}
            break
        print("  Please enter 'y' or 'n'")
    print()

    return num_players, players, base_hand_size, special_cards_config


def create_players_json(players, base_hand_size):
    """Create the playersData JavaScript array"""
    players_list = []

    for p in players:
        player_obj = {
            "name": p['name'],
            "position": p['position'],
            "score": 0,
            "handSizeModifier": 0,
            "baseHandSize": base_hand_size,
            "maxHandSize": base_hand_size,
            "superHotCount": 0,
            "superHotValue": 3,
            "hand": [],  # Will be filled by randomizeInitialState()
            "eaten": [],
            "dishCounts": {
                "Gomen": 0,
                "Azifa": 0,
                "Shiro": 0,
                "Kik Alicha": 0,
                "Misir Wot": 0,
                "Tikel Gomen": 0,
                "Key Sir": 0
            },
            "tastedAllTypes": False,
            "drinks": [],
            "specialCards": [],
            "tahiniConsumed": 0,
            "hotDishesEaten": 0,
            "totalHotEaten": 0
        }

        # Add AI fields if this player is AI
        if p['is_ai']:
            player_obj["isAI"] = True
            player_obj["aiLevel"] = p['ai_level']  # Now uses the chosen level

        players_list.append(player_obj)

    return json.dumps(players_list, separators=(',', ': '))


def create_reachable_json(num_players):
    """
    Create the reachableByPlayer JavaScript array
    This is a simplified version - generates basic sectors for each player
    """
    # For now, generate empty placeholders
    # The actual reachable calculation would require the full board logic
    # Users can run the game and it will work (tiles will just need manual checking)
    
    # Generate placeholder - all tiles are reachable by all players for now
    # This will be populated properly when the board state initializes
    reachable_arrays = []
    for i in range(num_players):
        reachable_arrays.append([])  # Empty for now
    
    return json.dumps(reachable_arrays, separators=(',', ': '))


def update_html_file(html_path, num_players, players, base_hand_size, special_cards_config=None):
    """Update the HTML file with new player configuration"""
    
    print(f"\n📖 Reading {html_path}...")
    
    try:
        with open(html_path, 'r', encoding='utf-8') as f:
            html_content = f.read()
    except FileNotFoundError:
        print(f"❌ ERROR: Could not find {html_path}")
        print("   Make sure you're running this script in the same folder as your HTML file!")
        return False
    
    # Create new player data
    players_json = create_players_json(players, base_hand_size)
    reachable_json = create_reachable_json(num_players)
    
    # Update playersData
    html_content = re.sub(
        r'let playersData = \[.*?\];',
        f'let playersData = {players_json};',
        html_content,
        flags=re.DOTALL
    )
    
    # Update reachableByPlayer  
    html_content = re.sub(
        r'let reachableByPlayer = \[.*?\];',
        f'let reachableByPlayer = {reachable_json};',
        html_content,
        flags=re.DOTALL
    )
    
    # Update numPlayers
    html_content = re.sub(
        r'let numPlayers = \d+;',
        f'let numPlayers = {num_players};',
        html_content
    )

    # Update special cards config
    sc_enabled = 'true' if special_cards_config else 'false'
    sc_deal = special_cards_config['deal'] if special_cards_config else 0
    sc_keep = special_cards_config['keep'] if special_cards_config else 0
    html_content = re.sub(
        r'let specialCardsEnabled = (true|false);',
        f'let specialCardsEnabled = {sc_enabled};',
        html_content
    )
    html_content = re.sub(
        r'let specialCardsDealCount = \d+;',
        f'let specialCardsDealCount = {sc_deal};',
        html_content
    )
    html_content = re.sub(
        r'let specialCardsKeepCount = \d+;',
        f'let specialCardsKeepCount = {sc_keep};',
        html_content
    )

    # Add reachable tiles calculator function if not present
    if 'calculateReachableTiles' not in html_content:
        print("📝 Adding reachable tiles calculator function...")
        
        calculator_code = '''
        function calculateReachableTiles() {
            /**
             * Calculate which tiles each player can reach based on their position.
             * Players sit at vertices of a FLAT-TOP hexagon.
             * Each player gets a sector (wedge) of the board.
             */
            
            console.log('Calculating reachable tiles for', numPlayers, 'players...');
            
            // Flat-top hexagon vertices at: 0°, 60°, 120°, 180°, 240°, 300°
            let playerVertices;
            if (numPlayers === 2) {
                playerVertices = [300, 120];  // P1: top-right, P2: bottom-left (opposite)
            } else if (numPlayers === 3) {
                playerVertices = [300, 60, 180];  // 120° apart
            } else if (numPlayers === 4) {
                playerVertices = [300, 0, 120, 180];  // Symmetric pairs
            } else if (numPlayers === 5) {
                playerVertices = [300, 0, 60, 120, 240];  // skip 180°
            } else if (numPlayers === 6) {
                playerVertices = [300, 0, 60, 120, 180, 240];  // all vertices
            }
            
            // Define sector conditions for each vertex angle
            const vertexConditions = {
                0:   (q, r) => q >= 0,           // Right
                60:  (q, r) => q + r >= 0,       // Bottom-right
                120: (q, r) => r >= 0,           // Bottom-left
                180: (q, r) => q <= 0,           // Left
                240: (q, r) => q + r <= 0,       // Top-left
                300: (q, r) => r <= 0            // Top-right
            };
            
            // Calculate reachable tiles for each player
            reachableByPlayer = [];
            
            for (let playerIdx = 0; playerIdx < numPlayers; playerIdx++) {
                const vertexAngle = playerVertices[playerIdx];
                const condition = vertexConditions[vertexAngle];
                const reachable = [];
                
                // Check each tile
                boardData.forEach(tile => {
                    if (!tile.removed && condition(tile.q, tile.r)) {
                        reachable.push({q: tile.q, r: tile.r});
                    }
                });
                
                reachableByPlayer.push(reachable);
                console.log(`Player ${playerIdx} (${vertexAngle}°): ${reachable.length} reachable tiles`);
            }
            
            console.log('✓ Reachable tiles calculated!');
        }
        '''
        
        # Insert before the "Initial draw" comment
        html_content = html_content.replace(
            '// Initial draw',
            calculator_code + '\n        // Initial draw'
        )
    
    # Make sure calculateReachableTiles() is called after randomizeInitialState()
    if 'randomizeInitialState();' in html_content and 'calculateReachableTiles();' not in html_content:
        print("📝 Adding call to calculateReachableTiles()...")
        html_content = html_content.replace(
            'randomizeInitialState();',
            'randomizeInitialState();\n        calculateReachableTiles();'
        )
    
    # Write updated HTML
    print(f"💾 Writing updated {html_path}...")
    with open(html_path, 'w', encoding='utf-8') as f:
        f.write(html_content)
    
    return True


def main():
    # Get configuration
    num_players, players, base_hand_size, special_cards_config = get_player_config()

    # Summary
    print()
    print("=" * 70)
    print("CONFIGURATION SUMMARY:")
    print("=" * 70)
    print(f"Players: {num_players}")
    print(f"Starting hand size: {base_hand_size} cards")
    if special_cards_config:
        print(f"Special cards: deal {special_cards_config['deal']}, keep {special_cards_config['keep']}")
    else:
        print("Special cards: disabled")
    print()
    for p in players:
        if p['is_ai']:
            player_type = 'Neural AI (Trained ML Model)'
        else:
            player_type = "Human"
        print(f"  Position {p['position']}: {player_type:35} - {p['name']}")
    print()

    # Confirm
    confirm = input("Update injera_game.html with this configuration? (y/n): ").strip().lower()
    if confirm not in ['y', 'yes']:
        print("Cancelled.")
        return

    # Update HTML file
    html_file = "injera_game.html"
    success = update_html_file(html_file, num_players, players, base_hand_size, special_cards_config)
    
    if success:
        print()
        print("=" * 70)
        print("✅ SUCCESS! HTML file updated!")
        print("=" * 70)
        print()
        print("✨ Added features:")
        print("   • Updated player count and names")
        print("   • Set AI players")  
        print("   • Added reachable tiles calculator")
        print("   • Calculator will run automatically on game load")
        print()
        print("📝 Next steps:")
        print("   1. Make sure AI server is running: python server.py")
        print("   2. Open (or refresh) injera_game.html in your browser")
        print("   3. Press F12 to see console - should show 'Reachable tiles calculated!'")
        print("   4. Play! 🎮")
        print()
    else:
        print("\n❌ Failed to update HTML file.")
        sys.exit(1)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n❌ Cancelled by user.")
        sys.exit(0)