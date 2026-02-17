#!/usr/bin/env python3
"""
Stars Shop Bot - Launcher
"""

import asyncio
import sys
import os

# Add current directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from bot import main

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Bot to'xtatildi!")
    except Exception as e:
        print(f"❌ Xatolik: {e}")
