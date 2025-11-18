#!/usr/bin/env python3
"""
Audio Metadata Repair Tool - Flask Web Interface
Web-based interface for repairing metadata for MP3 and FLAC files.
"""

from flask import Flask, render_template, request, jsonify, session
from pathlib import Path
import audio_repair
import threading
import json
import time
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'your-secret-key-change-in-production'  # Change this in production!

# Default log file path
DEFAULT_LOG_FILE = Path('metadata_repair_log.json')

# Store processing results in memory (in production, use Redis or database)
processing_results = {}


def process_audio_files(target_dir: Path, options: dict, session_id: str):
    """
    Process audio files in a background thread.
    
    Args:
        target_dir: Directory to process
        options: Dictionary with processing options
        session_id: Unique session ID for tracking
    """
    try:
        processing_results[session_id] = {
            'status': 'processing',
            'progress': 0,
            'current_file': '',
            'results': {}
        }
        
        if not target_dir.exists():
            processing_results[session_id] = {
                'status': 'error',
                'message': f"Directory '{target_dir}' does not exist!"
            }
            return
        
        # Load processing log
        log_file = DEFAULT_LOG_FILE
        log_data = audio_repair.load_log(log_file)
        
        # Find all MP3 and FLAC files
        audio_extensions = {'.mp3', '.flac'}
        audio_files = []
        
        for ext in audio_extensions:
            audio_files.extend(target_dir.rglob(f'*{ext}'))
        
        if not audio_files:
            processing_results[session_id] = {
                'status': 'error',
                'message': 'No MP3 or FLAC files found!'
            }
            return
        
        total_files = len(audio_files)
        processing_results[session_id]['results'] = {
            'total_files': total_files,
            'success_count': 0,
            'fail_count': 0,
            'skipped_count': 0,
            'nfo_generated': 0,
            'files_processed': []
        }
        
        # Repair each file
        album_art_cache = {}
        album_info = {}
        
        for idx, audio_file in enumerate(sorted(audio_files)):
            processing_results[session_id]['progress'] = int((idx + 1) / total_files * 100)
            processing_results[session_id]['current_file'] = str(audio_file.relative_to(target_dir))
            
            was_already_processed = audio_repair.is_file_processed(audio_file, log_data)
            
            # Process based on options
            if options.get('repair_metadata', True):
                # Use the full repair function, but pass empty cache if art is disabled
                art_cache = album_art_cache if options.get('download_art', True) else {}
                result, metadata = audio_repair.repair_audio_file(
                    audio_file, 
                    target_dir, 
                    art_cache,
                    log_data, 
                    log_file
                )
            else:
                # Just parse metadata without repairing, but still collect for nfo generation
                filename_metadata = audio_repair.parse_filename(audio_file.name)
                if filename_metadata:
                    artist = filename_metadata.get('artist', '')
                    album = filename_metadata.get('album', '')
                    
                    # Download and embed art if requested (even without metadata repair)
                    if artist and album and options.get('download_art', True):
                        album_key = f"{artist}||{album}"
                        if album_key not in album_art_cache:
                            album_art, _ = audio_repair.get_album_art(artist, album)
                            album_art_cache[album_key] = album_art
                            if album_art:
                                # Embed art
                                if audio_file.suffix.lower() == '.mp3':
                                    audio_repair.embed_album_art_mp3(audio_file, album_art)
                                elif audio_file.suffix.lower() == '.flac':
                                    audio_repair.embed_album_art_flac(audio_file, album_art)
                            time.sleep(0.5)
                        else:
                            # Use cached art
                            album_art = album_art_cache[album_key]
                            if album_art:
                                if audio_file.suffix.lower() == '.mp3':
                                    audio_repair.embed_album_art_mp3(audio_file, album_art)
                                elif audio_file.suffix.lower() == '.flac':
                                    audio_repair.embed_album_art_flac(audio_file, album_art)
                    
                    result = True
                    metadata = {
                        'album_dir': audio_file.parent,
                        'album_metadata': {
                            'album': album,
                            'artist': artist,
                            'albumartist': artist,
                            'year': '',
                            'genre': '',
                            'musicbrainz_release_group_id': ''
                        },
                        'track_number': filename_metadata.get('tracknumber'),
                        'track_title': filename_metadata.get('title', '')
                    }
                else:
                    result = False
                    metadata = None
            
            if result:
                if was_already_processed:
                    processing_results[session_id]['results']['skipped_count'] += 1
                else:
                    processing_results[session_id]['results']['success_count'] += 1
                
                # Track album information for nfo generation
                if metadata:
                    album_dir = metadata['album_dir']
                    if album_dir not in album_info:
                        album_info[album_dir] = {
                            'metadata': metadata['album_metadata'],
                            'tracks': {}
                        }
                    if metadata.get('track_number') and metadata.get('track_title'):
                        album_info[album_dir]['tracks'][metadata['track_number']] = metadata['track_title']
            else:
                processing_results[session_id]['results']['fail_count'] += 1
        
        # Generate album.nfo files if enabled
        if options.get('generate_nfo', True):
            nfo_generated = 0
            for album_dir, info in album_info.items():
                nfo_path = album_dir / 'album.nfo'
                if not nfo_path.exists():
                    if audio_repair.generate_album_nfo(nfo_path, info['metadata'], info['tracks']):
                        nfo_generated += 1
            processing_results[session_id]['results']['nfo_generated'] = nfo_generated
        
        # Final log save
        if options.get('repair_metadata', True):
            audio_repair.save_log(log_data, log_file)
        
        processing_results[session_id]['status'] = 'completed'
        processing_results[session_id]['progress'] = 100
        
    except Exception as e:
        processing_results[session_id] = {
            'status': 'error',
            'message': str(e)
        }


@app.route('/')
def index():
    """Main page with directory selection and options."""
    return render_template('index.html')


@app.route('/process', methods=['POST'])
def process():
    """Start processing audio files."""
    data = request.json
    target_dir = Path(data.get('target_dir', ''))
    
    if not target_dir:
        return jsonify({'error': 'Target directory is required'}), 400
    
    # Create unique session ID
    session_id = datetime.now().strftime('%Y%m%d%H%M%S%f')
    
    options = {
        'repair_metadata': data.get('repair_metadata', True),
        'download_art': data.get('download_art', True),
        'generate_nfo': data.get('generate_nfo', True)
    }
    
    # Start processing in background thread
    thread = threading.Thread(
        target=process_audio_files,
        args=(target_dir, options, session_id)
    )
    thread.daemon = True
    thread.start()
    
    return jsonify({'session_id': session_id})


@app.route('/status/<session_id>')
def status(session_id):
    """Get processing status."""
    if session_id not in processing_results:
        return jsonify({'error': 'Session not found'}), 404
    
    return jsonify(processing_results[session_id])


@app.route('/results/<session_id>')
def results(session_id):
    """Display results page."""
    if session_id not in processing_results:
        return render_template('error.html', message='Session not found'), 404
    
    result_data = processing_results[session_id]
    return render_template('results.html', results=result_data, session_id=session_id)


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)

