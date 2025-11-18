# Audio Metadata Repair Tool

A Python tool to repair metadata for MP3 and FLAC audio files by extracting information from filenames and optional `album.nfo` files.

## Available Versions

- **Command Line** (`main.py`): Simple CLI tool for batch processing
- **Desktop Application** (`app_desktop.py`): Native Windows GUI with advanced features (recommended)

See `README_DESKTOP.md` for details on the desktop application features.

## Features

- Automatically scans for MP3, FLAC, OGG, Opus, and M4A/MP4 files recursively
- Extracts metadata from filenames (supports format: `Artist - Album - TrackNumber - Title.ext`)
- Optionally reads metadata from `album.nfo` files if present
- Updates metadata tags for multiple formats:
  - **MP3**: ID3 tags
  - **FLAC**: Vorbis comments
  - **OGG/Opus**: Vorbis comments
  - **M4A/MP4**: iTunes-style tags
- Handles common metadata fields: title, artist, album, track number, year, genre, album artist
- Downloads and embeds album art from MusicBrainz Cover Art Archive
- Fix filenames to match standard format (desktop app only)
- Music library management with custom nicknames (desktop app only)
- Report generation in text, HTML, or CSV formats (desktop app only)
- Retry failed album art downloads with MusicBrainz IDs (desktop app only)
- JSON logging to track processed files and prevent duplicate work
- Skips files that have already been processed (unless modified)
- Skips album art downloads for albums that have already been attempted

## Installation

1. Install Python 3.7 or higher
2. Install required dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Usage

1. Place your audio files in the `target_files` directory (or modify the path in `main.py`)
2. Optionally include `album.nfo` files in album directories for additional metadata
3. Run the script:
   ```bash
   python main.py
   ```

## File Organization

The tool works best with files organized like:
```
target_files/
  Artist Name/
    Album Name (Year)/
      album.nfo (optional)
      Artist Name - Album Name - 01 - Track Title.mp3
      Artist Name - Album Name - 02 - Track Title.mp3
      ...
```

## Filename Format

The tool can parse filenames in these formats:
- `Artist - Album - TrackNumber - Title.ext` (preferred)
- `Artist - Title.ext` (fallback)

## Metadata Sources

1. **Filename parsing**: Extracts artist, album, track number, and title from the filename
2. **album.nfo files**: If present, provides additional metadata like:
   - Album title
   - Album artist
   - Year
   - Genre
   - Track titles (can override filename-extracted titles)

## Album Art Processing

The tool automatically downloads and embeds album art for your audio files using the MusicBrainz database and Cover Art Archive.

### How It Works

1. **Search Process**: For each album, the tool searches MusicBrainz using the artist and album name extracted from filenames or `album.nfo` files
2. **MusicBrainz ID**: If an `album.nfo` file contains a `musicbrainzreleasegroupid`, it uses that directly for faster lookup
3. **Cover Art Download**: Downloads the front cover art from the Cover Art Archive
4. **Fallback**: If release-group art isn't available, it attempts to find art from individual releases
5. **Embedding**: The downloaded art is embedded directly into each audio file:
   - **MP3 files**: Uses ID3 APIC (Attached Picture) frames
   - **FLAC files**: Uses Vorbis comment picture blocks
   - **OGG/Opus files**: Uses Vorbis comment metadata_block_picture
   - **M4A/MP4 files**: Uses MP4 covr atom

### Supported Image Formats

The tool automatically detects and supports:
- JPEG (most common)
- PNG
- GIF
- WebP

### Caching and Efficiency

- **Per-Album Download**: Album art is downloaded once per album, not per track
- **Session Cache**: Art downloaded during a session is cached in memory for all tracks from that album
- **Persistent Logging**: Failed download attempts are logged to prevent repeated API calls for albums without available art
- **Rate Limiting**: Includes a 0.5-second delay between API requests to respect MusicBrainz rate limits

### What Gets Embedded

- **Image Type**: Front cover (type 3 in ID3/Vorbis standards)
- **Description**: "Cover"
- **Replacement**: Existing album art is removed before embedding new art

### Handling Failures

- If album art cannot be found, the script continues processing metadata without art
- Failed attempts are logged so the tool won't retry the same album in future runs
- You'll see messages like:
  - `✓ Found album art` - Successfully downloaded and embedded
  - `⚠ No album art found` - Art not available for this album
  - `⊘ Album art already attempted (skipping download)` - Previously tried, skipping

### Data Sources

- **MusicBrainz API**: Used to search for release groups and releases
- **Cover Art Archive**: Provides the actual cover art images
- Both services are free and open-source, requiring no API keys

## JSON Logging

The script maintains a `metadata_repair_log.json` file to track:
- **Processed files**: Records which files have been processed, when, and whether they have album art
- **Album art attempts**: Tracks which albums have had art download attempts (successful or not)

This prevents:
- Re-processing files that haven't been modified since last run
- Re-downloading album art for albums that have already been attempted

The log file is automatically created and updated. You can delete it to force re-processing of all files.

## Notes

- The script will preserve existing metadata where possible
- Filename-extracted metadata takes precedence for track-specific information
- Album-level metadata from `album.nfo` supplements filename data
- All changes are written directly to the audio files
- Files are only re-processed if they've been modified since the last run
- Album art is downloaded once per album and embedded in all tracks from that album
- The script respects MusicBrainz API rate limits with delays between requests
- For large collections, processing may take longer due to API calls for album art
- Network connectivity is required for album art downloads

