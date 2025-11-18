# Audio Metadata Repair Tool v2.0.0

## 🎉 Major Release: Desktop Application

This release introduces a powerful native Windows desktop application with advanced features for managing your music collection.

## ✨ New Features

### 🖥️ Native Desktop Application
- **Modern Windows GUI** built with PySide6 (Qt)
- **Real-time progress tracking** with live updates
- **Non-blocking processing** - UI stays responsive during operations
- **Comprehensive results display** with detailed statistics

### 📚 Music Library Management
- Save multiple music libraries with custom nicknames
- Quick selection from dropdown menu
- Easy management (add, edit, delete) through intuitive dialog
- Persistent storage across sessions

### 🎨 Advanced Album Art Features
- **Retry Failed Albums Dialog**: Manage albums that failed to download art
  - View all failed albums with MusicBrainz IDs
  - Batch search for MusicBrainz IDs automatically
  - Manual ID entry and editing
  - Retry downloads for selected albums
- **MusicBrainz ID Tracking**: Automatically stores IDs for all albums (even failed ones)
- **Improved Recovery**: Better options for handling failed downloads

### 📊 Report Generation
- Generate reports in **Text**, **HTML**, or **CSV** formats
- Includes comprehensive statistics:
  - Processed files summary
  - Album art download status
  - MusicBrainz IDs for failed albums
  - Recent processing activity
- Live preview before exporting
- Easy export to any location

### 📝 Filename Management
- **Automatic filename fixing** to match standard format
- Format: `Artist - Album - TrackNumber - Title.ext`
- Reads metadata from file tags or album.nfo files
- Only renames files that don't match the format
- Removes invalid filename characters

### ⚙️ Flexible Processing Options
Enable/disable individual features:
- ✓ Repair metadata from filenames
- ✓ Download and embed album art
- ✓ Generate album.nfo files
- ✓ Fix filenames to match standard format

## 🔧 Improvements

- Enhanced error handling and user feedback
- Better UI/UX with modern interface design
- Improved album art download tracking
- More reliable filename parsing
- Better handling of edge cases

## 🗑️ Removed

- Flask web application (replaced by native desktop app)
  - Better performance
  - No browser required
  - Native Windows integration

## 📦 Installation

```bash
pip install -r requirements.txt
python app_desktop.py
```

## 📋 Requirements

- Python 3.7+
- mutagen>=1.47.0
- requests>=2.31.0
- PySide6>=6.5.0

## 🚀 Getting Started

1. Install dependencies: `pip install -r requirements.txt`
2. Run the desktop app: `python app_desktop.py`
3. Select or add a music library
4. Choose your processing options
5. Click "Start Processing"

## 📖 Documentation

- See `README.md` for general information
- See `README_DESKTOP.md` for desktop app details
- See `CHANGELOG.md` for detailed change history

## 🙏 Thanks

Thank you for using Audio Metadata Repair Tool! If you encounter any issues or have suggestions, please open an issue on GitHub.

