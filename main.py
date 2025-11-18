#!/usr/bin/env python3
"""
Audio Metadata Repair Tool
Main entry point for repairing metadata for MP3 and FLAC files.
"""

from pathlib import Path
import audio_repair

# Default log file path
DEFAULT_LOG_FILE = Path('metadata_repair_log.json')


def main():
    """Main function to repair all audio files in the target directory."""
    # Default to target_files directory, but allow override
    target_dir = Path('Z:\Audio\Music')
    
    if not target_dir.exists():
        print(f"Error: Directory '{target_dir}' does not exist!")
        return
    
    # Load processing log
    log_file = DEFAULT_LOG_FILE
    log_data = audio_repair.load_log(log_file)
    print(f"Loaded log: {len(log_data.get('processed_files', {}))} processed files, "
          f"{len(log_data.get('album_art', {}))} albums with art attempts")
    
    print(f"Scanning for audio files in: {target_dir.absolute()}")
    print("-" * 60)
    
    # Find all MP3 and FLAC files
    audio_extensions = {'.mp3', '.flac'}
    audio_files = []
    
    for ext in audio_extensions:
        audio_files.extend(target_dir.rglob(f'*{ext}'))
    
    if not audio_files:
        print("No MP3 or FLAC files found!")
        return
    
    print(f"Found {len(audio_files)} audio file(s)")
    print("-" * 60)
    
    # Repair each file
    success_count = 0
    fail_count = 0
    skipped_count = 0
    album_art_cache = {}  # Cache album art per album to avoid duplicate downloads
    
    # Track album information for nfo generation
    # Key: album directory path, Value: dict with metadata and tracks
    album_info = {}
    
    for audio_file in sorted(audio_files):
        print(f"Processing: {audio_file.relative_to(target_dir)}")
        # Check if already processed before calling repair function
        was_already_processed = audio_repair.is_file_processed(audio_file, log_data)
        result, metadata = audio_repair.repair_audio_file(audio_file, target_dir, album_art_cache, log_data, log_file)
        if result:
            if was_already_processed:
                skipped_count += 1
            else:
                success_count += 1
                print(f"  ✓ Successfully repaired")
                
                # Track album information for nfo generation
                if metadata:
                    album_dir = metadata['album_dir']
                    if album_dir not in album_info:
                        album_info[album_dir] = {
                            'metadata': metadata['album_metadata'],
                            'tracks': {}
                        }
                    # Add track information
                    if metadata.get('track_number') and metadata.get('track_title'):
                        album_info[album_dir]['tracks'][metadata['track_number']] = metadata['track_title']
        else:
            fail_count += 1
            print(f"  ✗ Failed to repair")
    
    # Generate album.nfo files for albums that don't have one
    print("-" * 60)
    print("Generating album.nfo files for albums without one...")
    nfo_generated = 0
    
    for album_dir, info in album_info.items():
        nfo_path = album_dir / 'album.nfo'
        if not nfo_path.exists():
            if audio_repair.generate_album_nfo(nfo_path, info['metadata'], info['tracks']):
                nfo_generated += 1
                print(f"  ✓ Generated: {nfo_path.relative_to(target_dir)}")
            else:
                print(f"  ✗ Failed to generate: {nfo_path.relative_to(target_dir)}")
    
    # Final log save
    audio_repair.save_log(log_data, log_file)
    
    print("-" * 60)
    print(f"Summary: {success_count} processed, {skipped_count} skipped, {fail_count} failed")
    if nfo_generated > 0:
        print(f"Generated {nfo_generated} album.nfo file(s)")
    print(f"Log saved to: {log_file.absolute()}")


if __name__ == '__main__':
    main()
