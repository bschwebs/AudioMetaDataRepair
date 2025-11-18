#!/usr/bin/env python3
"""
Build script for creating a standalone executable using PyInstaller.
"""

import PyInstaller.__main__
import sys
from pathlib import Path

def build_executable():
    """Build the executable using PyInstaller."""
    
    # PyInstaller arguments
    args = [
        'app_desktop.py',
        '--name=AudioMetadataRepair',
        '--onefile',  # Create a single executable file
        '--windowed',  # No console window (Windows only)
        '--icon=NONE',  # Add icon path here if you have one
        '--add-data=README.md;.',  # Include README
        '--add-data=README_DESKTOP.md;.',  # Include desktop README
        '--hidden-import=PySide6.QtCore',
        '--hidden-import=PySide6.QtGui',
        '--hidden-import=PySide6.QtWidgets',
        '--hidden-import=mutagen',
        '--hidden-import=mutagen.id3',
        '--hidden-import=mutagen.mp3',
        '--hidden-import=mutagen.flac',
        '--hidden-import=requests',
        '--collect-all=PySide6',
        '--collect-all=mutagen',
        '--noconfirm',  # Overwrite output directory without asking
        '--clean',  # Clean PyInstaller cache
    ]
    
    print("Building executable with PyInstaller...")
    print("This may take a few minutes...")
    
    try:
        PyInstaller.__main__.run(args)
        print("\n✓ Build complete!")
        print(f"Executable location: dist/AudioMetadataRepair.exe")
    except Exception as e:
        print(f"\n✗ Build failed: {e}")
        sys.exit(1)

if __name__ == '__main__':
    build_executable()

