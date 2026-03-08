#!/usr/bin/env python3
"""
Quick Start Script - Get the AI system up and running quickly
"""

import os
import sys

# Fix Windows emoji support
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

import subprocess
import webbrowser
from pathlib import Path

def main():
    print("=" * 70)
    print("🍽️  INJERA BOARD GAME - AI QUICK START")
    print("=" * 70)
    print()
    
    # Check if we're in the right directory
    if not os.path.exists('server.py'):
        print("❌ Error: Please run this script from the injera_ai directory")
        print()
        print("cd injera_ai")
        print("python quick_start.py")
        return 1
    
    # Step 1: Check Python version
    print("Step 1: Checking Python version...")
    version = sys.version_info
    print(f"  Python {version.major}.{version.minor}.{version.micro}")
    if version.major < 3 or (version.major == 3 and version.minor < 7):
        print("  ⚠️  Warning: Python 3.7+ recommended")
    else:
        print("  ✓ Python version OK")
    print()
    
    # Step 2: Install dependencies
    print("Step 2: Installing dependencies...")
    print("  Running: pip install -r requirements.txt")
    try:
        subprocess.run([sys.executable, '-m', 'pip', 'install', '-q', '-r', 'requirements.txt'], 
                      check=True)
        print("  ✓ Dependencies installed")
    except subprocess.CalledProcessError:
        print("  ❌ Failed to install dependencies")
        print("  Try manually: pip install -r requirements.txt")
        return 1
    print()
    
    # Step 3: Run tests
    print("Step 3: Running tests...")
    try:
        result = subprocess.run([sys.executable, 'test_ai.py'], 
                              capture_output=True, text=True, check=True)
        print("  ✓ All tests passed")
    except subprocess.CalledProcessError as e:
        print("  ❌ Tests failed")
        print(e.stdout)
        print(e.stderr)
        return 1
    print()
    
    # Step 4: Instructions
    print("=" * 70)
    print("✅ SETUP COMPLETE!")
    print("=" * 70)
    print()
    print("Next steps:")
    print()
    print("1️⃣  Start the AI server:")
    print("   python server.py")
    print()
    print("2️⃣  Modify your injera_game.html file:")
    print("   See INTEGRATION_GUIDE.md for detailed instructions")
    print()
    print("3️⃣  Open the game in your browser and play!")
    print()
    print("=" * 70)
    print()
    
    # Ask if they want to start the server now
    try:
        response = input("Start the AI server now? (y/n): ").strip().lower()
        if response == 'y':
            print()
            print("Starting server...")
            print("Press Ctrl+C to stop")
            print()
            subprocess.run([sys.executable, 'server.py'])
    except KeyboardInterrupt:
        print()
        print("Server stopped")
    
    return 0

if __name__ == '__main__':
    try:
        exit_code = main()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print()
        print("Interrupted by user")
        sys.exit(0)
