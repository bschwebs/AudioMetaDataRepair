# Audio Metadata Repair Tool - Windows Desktop Application

A native Windows desktop application for repairing metadata, downloading album art, and generating NFO files for MP3, FLAC, OGG, Opus, and M4A/MP4 audio files.

## Features

- **Native Windows GUI**: Built with PySide6 (Qt) for a native Windows look and feel
- **Music Library Management**: Save and manage multiple music libraries with custom nicknames
- **Directory Selection**: Browse and select directories using native Windows dialogs
- **Optional Features**: Enable/disable individual features:
  - Repair metadata from filenames
  - Download and embed album art
  - Generate album.nfo files
  - Fix filenames to match standard format
- **Real-time Progress**: See processing progress with progress bar and current file
- **Results Display**: View detailed results after processing
- **Report Generation**: Generate text, HTML, or CSV reports from processing logs
- **Retry Failed Albums**: Retry album art downloads with MusicBrainz IDs
  - Batch search for MusicBrainz IDs
  - Manual ID entry and editing
  - Retry selected albums

## Installation

1. Install Python 3.7 or higher
2. Install required dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Running the Desktop Application

1. Start the application:
   ```bash
   python app_desktop.py
   ```

2. The application window will open with:
   - Directory selection field with Browse button
   - Processing options checkboxes
   - Start Processing button
   - Progress bar and status
   - Results display area

## Usage

1. **Select Music Library or Directory**: 
   - Select a saved library from the dropdown (if you have saved libraries)
   - Or click "Manage Libraries..." to add/edit/remove saved libraries with nicknames
   - Or click "Browse..." to open a directory selection dialog
   - Or type the full path directly (e.g., `Z:\Audio\Music`)

2. **Select Options**:
   - ✓ **Repair Metadata**: Updates ID3 tags and Vorbis comments from filenames
   - ✓ **Download Album Art**: Downloads and embeds album covers from MusicBrainz
   - ✓ **Generate NFO Files**: Creates album.nfo files for albums without one
   - ✓ **Fix Filenames**: Renames files to match format: `Artist - Album - TrackNumber - Title.ext`

3. **Start Processing**: Click "Start Processing" to begin

4. **Monitor Progress**: Watch the progress bar and current file being processed

5. **View Results**: See a summary of processed files when complete

6. **Generate Reports**: Click "Generate Report" to create text, HTML, or CSV reports

7. **Retry Failed Albums**: Click "Retry Failed Albums" to:
   - View albums that failed to download art
   - Search for MusicBrainz IDs (single or batch)
   - Manually enter/edit MusicBrainz IDs
   - Retry downloading art for selected albums

## Features Details

### Repair Metadata
- Extracts metadata from filenames (format: `Artist - Album - TrackNumber - Title.ext`)
- Updates metadata tags for multiple formats:
  - **MP3**: ID3 tags
  - **FLAC**: Vorbis comments
  - **OGG/Opus**: Vorbis comments
  - **M4A/MP4**: iTunes-style tags
- Uses album.nfo files if available for additional metadata

### Download Album Art
- Searches MusicBrainz for album information
- Downloads cover art from Cover Art Archive
- Embeds art directly into audio files
- Caches downloads to avoid duplicates

### Generate NFO Files
- Creates album.nfo files for albums that don't have one
- Includes all metadata and track information
- Uses the same format as existing nfo files

### Fix Filenames
- Renames files to match standard format: `Artist - Album - TrackNumber - Title.ext`
- Reads metadata from file tags (ID3/Vorbis) or album.nfo files
- Only renames files that don't match the format
- Removes invalid filename characters

### Music Library Management
- Save multiple music library paths with custom nicknames
- Quick selection from dropdown menu
- Add, edit, or delete libraries through management dialog
- Libraries are saved in `music_libraries.json` (user-specific)

### Report Generation
- Generate detailed reports in multiple formats:
  - **Text Report**: Plain text summary with statistics
  - **HTML Report**: Formatted HTML with tables and styling
  - **CSV Report**: Spreadsheet-compatible format
- Reports include:
  - Processed files summary
  - Album art download status
  - MusicBrainz IDs for failed albums
  - Recent processing activity

### Retry Failed Albums
- View all albums that failed to download art
- Search for MusicBrainz IDs automatically (single or batch)
- Manually enter or edit MusicBrainz IDs
- Retry downloading art for selected albums
- Real-time progress updates during batch searches

## Technical Details

- **Framework**: PySide6 (Qt for Python)
- **Threading**: Uses QThread for non-blocking file processing
- **UI**: Native Windows controls and dialogs
- **Progress Tracking**: Real-time progress updates

## Building a Standalone Executable

To create a standalone `.exe` file using PyInstaller:

1. Install PyInstaller:
   ```bash
   pip install pyinstaller
   ```

2. Build the executable:
   ```bash
   pyinstaller --onefile --windowed --name "AudioMetadataRepair" app_desktop.py
   ```

3. The executable will be in the `dist` folder

## Technical Details

- **Framework**: PySide6 (Qt for Python)
- **Threading**: Uses QThread for non-blocking file processing
- **UI**: Native Windows controls and dialogs
- **Progress Tracking**: Real-time progress updates

