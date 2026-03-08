# Import Error Fix

If you're getting `ModuleNotFoundError: No module named 'engine.game_engine'`, follow these steps:

## Quick Fix

**Make sure you're running commands from the correct directory:**

```bash
# Navigate to the injera_ai directory
cd "c:\Users\obfel\injera\fullProject\injera_ai_complete\injera_ai"

# Verify you're in the right place (should see these files)
ls
# Should show: engine/, neural_ai/, server.py, train_neural_ai.py, etc.

# Test imports
python fix_imports.py
```

## Why This Happens

Python needs to find the `engine` module. The neural AI code looks for it in the parent directory.

**Correct structure:**
```
injera_ai/
├── engine/                 # Game engine module
├── neural_ai/             # Neural AI module
├── train_neural_ai.py     # Training script
└── server.py              # Game server
```

## Solutions

### Solution 1: Run from the right directory (Recommended)

```bash
# Always run from injera_ai/
cd "c:\Users\obfel\injera\fullProject\injera_ai_complete\injera_ai"

# Then run commands
python train_neural_ai.py --games 50
python test_neural_ai.py
python server.py
```

### Solution 2: Set PYTHONPATH (Alternative)

**Windows CMD:**
```cmd
set PYTHONPATH=c:\Users\obfel\injera\fullProject\injera_ai_complete\injera_ai
python train_neural_ai.py --games 50
```

**Windows PowerShell:**
```powershell
$env:PYTHONPATH="c:\Users\obfel\injera\fullProject\injera_ai_complete\injera_ai"
python train_neural_ai.py --games 50
```

**Git Bash / MSYS:**
```bash
export PYTHONPATH="/c/Users/obfel/injera/fullProject/injera_ai_complete/injera_ai"
python train_neural_ai.py --games 50
```

### Solution 3: Install as package (Advanced)

Create `setup.py` in injera_ai/:

```python
from setuptools import setup, find_packages

setup(
    name="injera_ai",
    version="0.1.0",
    packages=find_packages(),
)
```

Then install in development mode:
```bash
cd injera_ai
pip install -e .
```

## Verify Fix Worked

Run the test:
```bash
python fix_imports.py
```

You should see:
```
✅ All imports working correctly!
```

## Still Having Issues?

1. **Check you're in the right directory:**
   ```bash
   pwd  # Should end in: injera_ai_complete/injera_ai
   ```

2. **Check Python can find the modules:**
   ```bash
   python -c "import sys; sys.path.insert(0, '.'); from engine.game_state import GameState; print('OK')"
   ```

3. **Check file structure:**
   ```bash
   ls engine/  # Should show: __init__.py, game_state.py, etc.
   ls neural_ai/  # Should show: __init__.py, state_encoder.py, etc.
   ```

4. **Check __init__.py files exist:**
   ```bash
   ls engine/__init__.py neural_ai/__init__.py
   ```

If files are missing, the installation might be incomplete.
