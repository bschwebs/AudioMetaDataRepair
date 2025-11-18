# Audio Metadata Repair Tool - Flask Web Interface

A web-based interface for repairing metadata, downloading album art, and generating NFO files for MP3 and FLAC audio files.

## Features

- **Web-based Interface**: Easy-to-use browser interface
- **Directory Selection**: Choose any directory on your system
- **Optional Features**: Enable/disable individual features:
  - Repair metadata from filenames
  - Download and embed album art
  - Generate album.nfo files
- **Real-time Progress**: See processing progress in real-time
- **Results Summary**: View detailed results after processing

## Installation

1. Install Python 3.7 or higher
2. Install required dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Running the Web Application

1. Start the Flask server:
   ```bash
   python app.py
   ```

2. Open your web browser and navigate to:
   ```
   http://localhost:5000
   ```

3. Enter the path to your music directory and select which features to enable

4. Click "Start Processing" and watch the progress

5. View results when processing is complete

## Usage

1. **Enter Target Directory**: Type the full path to your music directory (e.g., `Z:\Audio\Music`)

2. **Select Options**:
   - **Repair Metadata**: Updates ID3 tags and Vorbis comments from filenames
   - **Download Album Art**: Downloads and embeds album covers from MusicBrainz
   - **Generate NFO Files**: Creates album.nfo files for albums without one

3. **Start Processing**: Click the button to begin

4. **Monitor Progress**: Watch real-time progress updates

5. **View Results**: See a summary of processed files when complete

## Features Details

### Repair Metadata
- Extracts metadata from filenames (format: `Artist - Album - TrackNumber - Title.ext`)
- Updates ID3 tags for MP3 files
- Updates Vorbis comments for FLAC files
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

## Technical Details

- **Framework**: Flask 3.0+
- **Background Processing**: Uses threading for non-blocking file processing
- **Session Management**: Each processing job gets a unique session ID
- **Progress Tracking**: Real-time progress updates via AJAX polling

## Security Note

⚠️ **Important**: Change the `secret_key` in `app.py` before deploying to production!

## Development

The application runs in debug mode by default. For production:
- Set `debug=False` in `app.py`
- Use a proper WSGI server (e.g., Gunicorn, uWSGI)
- Configure proper session storage (Redis, database)
- Set up proper error handling and logging

