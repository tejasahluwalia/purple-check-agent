#!/usr/bin/env python3
"""
Entry point script for processing Reddit posts.
Calls the main function from src.process module.
"""

import sys
import os

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.process import main

if __name__ == "__main__":
    main()
