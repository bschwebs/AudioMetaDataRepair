# Building the Installer

This guide explains how to create a standalone executable and Windows installer for Audio Metadata Repair Tool.

## Prerequisites

1. **Python 3.7+** installed on your system
2. **PyInstaller** for creating the executable
3. **Inno Setup** (optional, for creating a Windows installer)

## Step 1: Install Build Dependencies

```bash
pip install pyinstaller
```

Or add to requirements:
```bash
pip install -r requirements.txt
pip install pyinstaller
```

## Step 2: Build the Executable

### Option A: Using the Build Script

```bash
python build_exe.py
```

### Option B: Using PyInstaller Directly

```bash
pyinstaller --onefile --windowed --name AudioMetadataRepair app_desktop.py
```

### Option C: Using the Spec File (Recommended)

First, generate a spec file:
```bash
pyinstaller --name AudioMetadataRepair --onefile --windowed app_desktop.py
```

This creates `AudioMetadataRepair.spec`. You can edit this file to customize the build, then run:
```bash
pyinstaller AudioMetadataRepair.spec
```

## Step 3: Test the Executable

1. Navigate to the `dist` folder
2. Run `AudioMetadataRepair.exe`
3. Test all features to ensure everything works

## Step 4: Create the Installer (Optional)

### Using Inno Setup

1. **Download Inno Setup**: https://jrsoftware.org/isdl.php
2. **Install Inno Setup Compiler**
3. **Open** `build_installer.iss` in Inno Setup Compiler
4. **Review** the settings (app name, version, etc.)
5. **Build** → **Compile** (or press F9)
6. The installer will be created in the `installer` folder

### Customizing the Installer

Edit `build_installer.iss` to customize:
- App name and version
- Publisher information
- Install location
- Icons and shortcuts
- License file

## Build Output

After building, you'll have:

- **Executable**: `dist/AudioMetadataRepair.exe` (standalone, can be distributed as-is)
- **Installer**: `installer/AudioMetadataRepair-Setup.exe` (if using Inno Setup)

## Distribution

### Standalone Executable
- Just distribute `AudioMetadataRepair.exe`
- No installation needed - users can run it directly
- All dependencies are bundled

### Installer Package
- Distribute `AudioMetadataRepair-Setup.exe`
- Users run the installer to install the application
- Creates Start Menu shortcuts
- Can be uninstalled via Windows Settings

## Troubleshooting

### Executable is Large
- This is normal - PyInstaller bundles Python and all dependencies
- Typical size: 50-100 MB
- Use `--onefile` for a single file, or remove it for a folder with multiple files

### Missing Modules
- Add `--hidden-import=module_name` to PyInstaller arguments
- Check the build script for common hidden imports

### Antivirus False Positives
- Some antivirus software may flag PyInstaller executables
- This is a known issue with PyInstaller
- Consider code signing the executable (requires a certificate)

### Icon Not Showing
- Create an `.ico` file for your application
- Add `--icon=path/to/icon.ico` to PyInstaller arguments
- Update the spec file with the icon path

## Advanced Options

### Code Signing (Optional)
To sign your executable (removes Windows warnings):

1. Obtain a code signing certificate
2. Use `signtool.exe` (part of Windows SDK):
   ```bash
   signtool sign /f certificate.pfx /p password /t http://timestamp.digicert.com AudioMetadataRepair.exe
   ```

### Reducing Executable Size
- Use `--exclude-module` to exclude unused modules
- Use UPX compression (if available)
- Consider using `--onedir` instead of `--onefile` (creates a folder instead)

## Notes

- The executable is standalone - no Python installation required on target machines
- First run may be slightly slower (extraction of bundled files)
- All user data (logs, libraries) are stored in the user's directory
- The executable works on Windows 10/11 (64-bit)

