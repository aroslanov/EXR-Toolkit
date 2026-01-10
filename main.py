#!/usr/bin/env python
"""
EXR Toolkit — Root-level launcher
"""

import sys
from pathlib import Path

# Add project root to sys.path so app module is importable
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from app.main import main

if __name__ == "__main__":
    main()
