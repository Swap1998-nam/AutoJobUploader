#!/usr/bin/env python
"""
🚀 START HERE - Quick Start Guide
Run this script to get started with the fixed backend
"""

import subprocess
import sys
import os
from pathlib import Path

def run_command(cmd, description):
    """Run a command and show output"""
    print(f"\n{'='*60}")
    print(f"📌 {description}")
    print(f"{'='*60}")
    print(f"Command: {cmd}\n")
    
    result = subprocess.run(cmd, shell=True)
    return result.returncode == 0

def main():
    backend_path = Path(__file__).parent
    
    print("""
    ╔══════════════════════════════════════════════════════════╗
    ║     🎯 JOB APPLY AUTOMATION - QUICK START GUIDE          ║
    ║                                                          ║
    ║     ChromeDriver issues have been FIXED! ✅              ║
    ║                                                          ║
    ║     Choose what to do next:                             ║
    ╚══════════════════════════════════════════════════════════╝
    """)
    
    print("""
    Option 1: ⚡ Quick Health Check (RECOMMENDED)
    ──────────────────────────────────
    Verify everything is working:
    > python health_check.py
    
    Option 2: 🔍 Full Startup Verification  
    ──────────────────────────────────
    Detailed checks:
    > python verify_startup.py
    
    Option 3: 🚀 Start Backend Directly
    ──────────────────────────────────
    > uvicorn job_apply_backend:app --reload --port 8000
    
    Option 4: 🧪 Test Login (with visible browser)
    ──────────────────────────────────
    > python debug_linkedin.py
    
    Option 5: 📚 Read Documentation
    ──────────────────────────────────
    - CHROMEDRIVER_FIX.md  (Overview of fixes)
    - SETUP_GUIDE.md       (Detailed setup)
    - TROUBLESHOOTING.md   (Common issues)
    """)
    
    choice = input("\nWhat would you like to do? (1-5 or Q to quit): ").strip().lower()
    
    commands = {
        '1': (f"{sys.executable} health_check.py", "Running Health Check..."),
        '2': (f"{sys.executable} verify_startup.py", "Running Full Verification..."),
        '3': (f"{sys.executable} -m uvicorn job_apply_backend:app --reload --port 8000", "Starting Backend..."),
        '4': (f"{sys.executable} debug_linkedin.py", "Running Debug Tool..."),
        '5': ("", ""),
    }
    
    if choice == 'q':
        print("\nGoodbye! 👋\n")
        return 0
    
    if choice == '5':
        print("""
        📖 Documentation Files:
        
        1. CHROMEDRIVER_FIX.md
           → Overview of what was fixed
           → Quick troubleshooting
           → Files affected
        
        2. SETUP_GUIDE.md  
           → Step-by-step setup
           → Testing instructions
           → Requirements
        
        3. TROUBLESHOOTING.md
           → Common errors
           → Solutions for each error
           → FAQ
        
        Run 'cat [filename]' to view any of these files.
        """)
        return 0
    
    if choice in commands:
        cmd, desc = commands[choice]
        if cmd:
            run_command(cmd, desc)
    else:
        print("\n❌ Invalid choice. Please select 1-5 or Q.\n")
        return 1
    
    return 0

if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n\n⏹️  Cancelled by user.\n")
        sys.exit(0)
