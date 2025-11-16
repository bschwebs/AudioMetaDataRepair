# Audio Metadata Repair Tool

A Python tool to repair metadata for MP3 and FLAC audio files by extracting information from filenames and optional `album.nfo` files.

## Features

- Automatically scans for MP3 and FLAC files recursively
- Extracts metadata from filenames (supports format: `Artist - Album - TrackNumber - Title.ext`)
- Optionally reads metadata from `album.nfo` files if present
- Updates ID3 tags for MP3 files and Vorbis comments for FLAC files
- Handles common metadata fields: title, artist, album, track number, year, genre, album artist
- Downloads and embeds album art from MusicBrainz Cover Art Archive
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

