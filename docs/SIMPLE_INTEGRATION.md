# 🚀 SUPER SIMPLE AI INTEGRATION (3 Steps!)

I've created a JavaScript file that does all the AI work for you. Here's how to add it to your HTML:

## Step 1: Copy the AI JavaScript file

Copy `ai_support.js` to the same folder as your `injera_game.html`

## Step 2: Add ONE line to your HTML

Open `injera_game.html` and add this line **just before** `</body>` (at the very end):

```html
    <script src="ai_support.js"></script>
</body>
</html>
```

## Step 3: Tell the game which players are AI

In your HTML, find where `playersData` is defined (around line 194). 

**BEFORE:**
```javascript
let playersData = [
    {"name": "Player 1", "position": 0, "score": 0, ...},
    {"name": "Player 2", "position": 1, "score": 0, ...}
];
```

**AFTER:**
```javascript
let playersData = [
    {"name": "Player 1", "position": 0, "score": 0, ..., "isAI": false, "aiLevel": null},
    {"name": "Player 2 (AI)", "position": 1, "score": 0, ..., "isAI": true, "aiLevel": "beginner"}
];
```

Just add those two fields: `"isAI": true` and `"aiLevel": "beginner"` to any player you want to be AI.

## Step 4: Modify nextTurn() function

Find the `nextTurn()` function and add this ONE line at the very end:

```javascript
function nextTurn() {
    // ... all the existing code ...
    
    updatePlayersPanel();
    updateGameStatus();
    drawBoard();
    
    // ADD THIS LINE:
    handleAITurnIfNeeded();  // ← ADD THIS!
}
```

## Step 5 (OPTIONAL): Fix Berbere Scoring to 3 points

If you want Berbere to be flat 3 points instead of progressive, find this in `testEat()` function:

**FIND:**
```javascript
} else if (dishName === 'Berbere Misir') {
    dishValue = currentPlayer.superHotValue || 2;
}
```

**REPLACE WITH:**
```javascript
} else if (dishName === 'Berbere Misir') {
    dishValue = 3;  // Flat 3 points
}
```

## That's It!

Now:
1. Start the AI server: `python server.py`
2. Open `injera_game.html` in your browser
3. The AI will automatically play when it's their turn!

## Testing

To test, you can make BOTH players AI and watch them play:

```javascript
let playersData = [
    {... "isAI": true, "aiLevel": "beginner"},
    {... "isAI": true, "aiLevel": "beginner"}
];
```

Then just sit back and watch! 🍿

---

## Troubleshooting

**Problem:** "AI Error: Failed to fetch"
**Solution:** Make sure `python server.py` is running

**Problem:** AI doesn't move
**Solution:** Check browser console (F12) for errors. Make sure you added `handleAITurnIfNeeded()` to `nextTurn()`

**Problem:** Game crashes when AI tries to move
**Solution:** Make sure you added `"isAI"` and `"aiLevel"` fields to ALL players in playersData
