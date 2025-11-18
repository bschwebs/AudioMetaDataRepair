# Release Notes

## Version 2.0.0 - Desktop Application Release

### 🎉 Major Features

#### Desktop Application (`app_desktop.py`)
- **Native Windows GUI**: Built with PySide6 (Qt) for a native Windows experience
- **Music Library Management**: Save and manage multiple music libraries with custom nicknames
  - Quick selection from dropdown menu
  - Add, edit, or delete libraries through management dialog
  - Persistent storage in `music_libraries.json`
- **Real-time Progress Tracking**: Live progress bar and current file display
- **Comprehensive Results Display**: Detailed summary after processing

#### Advanced Album Art Features
- **Retry Failed Albums**: Dedicated dialog to manage albums that failed to download art
  - View all failed albums with their MusicBrainz IDs
  - Batch search for MusicBrainz IDs automatically
  - Manual ID entry and editing
  - Retry downloading art for selected albums
  - Real-time progress updates during batch searches
- **MusicBrainz ID Tracking**: Automatically stores MusicBrainz IDs for all albums (even failed ones)
- **Improved Error Handling**: Better tracking and recovery options for failed downloads

#### Report Generation
- **Multiple Formats**: Generate reports in Text, HTML, or CSV formats
- **Comprehensive Data**: Includes:
  - Processed files summary with statistics
  - Album art download status
  - MusicBrainz IDs for failed albums
  - Recent processing activity
- **Live Preview**: Preview reports before exporting
- **Easy Export**: Save reports to any location

#### Filename Management
- **Automatic Filename Fixing**: Rename files to match standard format
  - Format: `Artist - Album - TrackNumber - Title.ext`
  - Reads metadata from file tags (ID3/Vorbis) or album.nfo files
  - Only renames files that don't match the format
  - Removes invalid filename characters
- **Smart Metadata Extraction**: Uses embedded tags when filename parsing fails

### ✨ Enhanced Features

#### Processing Options
- **Flexible Configuration**: Enable/disable individual features:
  - ✓ Repair metadata from filenames
  - ✓ Download and embed album art
  - ✓ Generate album.nfo files
  - ✓ Fix filenames to match standard format

#### Improved User Experience
- **Better UI/UX**: Modern, intuitive interface with clear visual feedback
- **Non-blocking Processing**: Background threading keeps UI responsive
- **Status Updates**: Real-time status bar updates during processing
- **Error Messages**: Clear, actionable error messages

### 🔧 Technical Improvements

- **Modular Architecture**: Clean separation between UI and core logic
- **Efficient Processing**: Optimized file scanning and metadata extraction
- **Better Logging**: Enhanced JSON logging with MusicBrainz ID tracking
- **Code Quality**: Improved error handling and code organization

### 📋 Command Line Tool (`main.py`)

The original command-line tool remains available for:
- Batch processing via terminal
- Scripting and automation
- Server environments without GUI

### 🗑️ Removed Features

- **Flask Web Application**: Removed in favor of native desktop application
  - Better performance
  - No browser required
  - Native Windows integration

### 📦 Dependencies

- `mutagen>=1.47.0` - Audio metadata handling
- `requests>=2.31.0` - HTTP requests for MusicBrainz API
- `PySide6>=6.5.0` - Qt framework for desktop GUI

### 🚀 Getting Started

1. Install Python 3.7 or higher
2. Install dependencies: `pip install -r requirements.txt`
3. Run the desktop app: `python app_desktop.py`
4. Or use the CLI tool: `python main.py`

### 📝 Notes

- All features from previous versions are maintained
- Backward compatible with existing log files
- Works with existing `album.nfo` files
- Respects MusicBrainz API rate limits

---

## Version 1.0.0 - Initial Release

### Core Features

- **Metadata Repair**: Extract and repair metadata from filenames
- **Album Art Download**: Automatic download and embedding from MusicBrainz
- **NFO File Support**: Read and generate `album.nfo` files
- **JSON Logging**: Track processed files to prevent duplicate work
- **Multiple Formats**: Support for MP3 and FLAC files
- **Smart Processing**: Skip already-processed files unless modified

### File Format Support

- **MP3**: ID3 tag support
- **FLAC**: Vorbis comment support
- **Filename Parsing**: `Artist - Album - TrackNumber - Title.ext` format

### Metadata Sources

1. Filename parsing
2. `album.nfo` files (optional)
3. Embedded file tags (for filename fixing)

---

## Future Enhancements

Potential features for future releases:
- Support for additional audio formats (OGG, M4A, etc.)
- Batch operations across multiple libraries
- Advanced metadata editing
- Integration with additional music databases
- Export/import library configurations

