#!/usr/bin/env python3
"""
Audio Metadata Repair Module
Contains all functions for repairing audio file metadata and downloading album art.
"""

import re
import json
import xml.etree.ElementTree as ET
import requests
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, Tuple
from mutagen.id3 import ID3, TIT2, TPE1, TALB, TRCK, TDRC, TCON, TPE2, APIC
from mutagen.mp3 import MP3
from mutagen.flac import FLAC
from mutagen.flac import Picture


# ============================================================================
# Logging Functions
# ============================================================================

def load_log(log_file: Path) -> Dict:
    """Load the processing log from JSON file."""
    if log_file.exists():
        try:
            with open(log_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            print(f"Warning: Could not load log file: {e}")
            print("Starting with empty log.")
    
    return {
        'processed_files': {},
        'album_art': {}
    }


def save_log(log_data: Dict, log_file: Path):
    """Save the processing log to JSON file."""
    try:
        with open(log_file, 'w', encoding='utf-8') as f:
            json.dump(log_data, f, indent=2, ensure_ascii=False)
    except IOError as e:
        print(f"Warning: Could not save log file: {e}")


def is_file_processed(file_path: Path, log_data: Dict) -> bool:
    """Check if a file has already been processed and hasn't been modified since."""
    file_str = str(file_path)
    
    if file_str not in log_data.get('processed_files', {}):
        return False
    
    file_info = log_data['processed_files'][file_str]
    
    # Check if file still exists and hasn't been modified
    if not file_path.exists():
        return False
    
    try:
        current_mtime = file_path.stat().st_mtime
        logged_mtime = file_info.get('file_mtime', 0)
        
        # If file was modified after last processing, it needs reprocessing
        if current_mtime > logged_mtime:
            return False
        
        return True
    except OSError:
        return False


def mark_file_processed(file_path: Path, log_data: Dict, has_art: bool = False):
    """Mark a file as processed in the log."""
    file_str = str(file_path)
    
    try:
        mtime = file_path.stat().st_mtime
    except OSError:
        mtime = 0
    
    if 'processed_files' not in log_data:
        log_data['processed_files'] = {}
    
    log_data['processed_files'][file_str] = {
        'last_processed': datetime.now().isoformat(),
        'file_mtime': mtime,
        'has_art': has_art
    }


def has_album_art_downloaded(artist: str, album: str, log_data: Dict) -> bool:
    """Check if album art has already been downloaded for this album."""
    album_key = f"{artist}||{album}"
    album_art_data = log_data.get('album_art', {})
    
    if album_key not in album_art_data:
        return False
    
    return album_art_data[album_key].get('downloaded', False)


def get_failed_albums(log_data: Dict) -> list:
    """Get list of albums that failed to download art, with their MusicBrainz IDs if available."""
    failed_albums = []
    album_art_data = log_data.get('album_art', {})
    
    for album_key, art_info in album_art_data.items():
        if not art_info.get('downloaded', False):
            artist, album = album_key.split('||', 1)
            failed_albums.append({
                'artist': artist,
                'album': album,
                'musicbrainz_id': art_info.get('musicbrainz_release_group_id', ''),
                'last_attempted': art_info.get('last_downloaded', '')
            })
    
    return failed_albums


def retry_album_art_with_id(artist: str, album: str, musicbrainz_id: str, log_data: Dict, log_file: Path) -> Tuple[bool, Optional[bytes]]:
    """
    Retry downloading album art using a specific MusicBrainz release group ID.
    Returns (success: bool, image_data: Optional[bytes])
    """
    try:
        album_art_data, found_mb_id = get_album_art(artist, album, musicbrainz_id)
        success = album_art_data is not None
        
        # Update log
        mark_album_art_downloaded(artist, album, log_data, success, found_mb_id or musicbrainz_id)
        save_log(log_data, log_file)
        
        return success, album_art_data
    except Exception as e:
        print(f"Error retrying album art: {e}")
        return False, None


def batch_search_musicbrainz_ids(failed_albums: list, progress_callback=None) -> Dict[str, str]:
    """
    Batch search for MusicBrainz IDs for multiple albums.
    
    Args:
        failed_albums: List of dicts with 'artist' and 'album' keys
        progress_callback: Optional callback function(album_key, mb_id) for progress updates
    
    Returns:
        Dictionary mapping album_key (artist||album) to MusicBrainz ID (or empty string if not found)
    """
    results = {}
    
    for album_info in failed_albums:
        artist = album_info.get('artist', '')
        album = album_info.get('album', '')
        album_key = f"{artist}||{album}"
        
        if not artist or not album:
            results[album_key] = ''
            continue
        
        mb_id = search_musicbrainz_release_group(artist, album)
        results[album_key] = mb_id or ''
        
        if progress_callback:
            progress_callback(album_key, mb_id or '')
        
        # Be polite to the API
        time.sleep(0.5)
    
    return results


def mark_album_art_downloaded(artist: str, album: str, log_data: Dict, success: bool, musicbrainz_id: Optional[str] = None):
    """Mark album art as downloaded (or attempted) in the log."""
    album_key = f"{artist}||{album}"
    
    if 'album_art' not in log_data:
        log_data['album_art'] = {}
    
    log_data['album_art'][album_key] = {
        'downloaded': success,
        'last_downloaded': datetime.now().isoformat(),
        'musicbrainz_release_group_id': musicbrainz_id or ''
    }


# ============================================================================
# Album Art Functions
# ============================================================================

def search_musicbrainz_release_group(artist: str, album: str) -> Optional[str]:
    """
    Search MusicBrainz for a release group ID.
    Returns the release group ID if found, None otherwise.
    """
    try:
        search_url = "https://musicbrainz.org/ws/2/release-group"
        params = {
            'query': f'artist:"{artist}" AND release:"{album}"',
            'fmt': 'json',
            'limit': 1
        }
        
        headers = {
            'User-Agent': 'AudioMetadataRepair/1.0 (https://github.com/yourusername)'
        }
        
        response = requests.get(search_url, params=params, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        if not data.get('release-groups'):
            return None
        
        return data['release-groups'][0]['id']
    except Exception as e:
        print(f"  Warning: Could not search MusicBrainz: {e}")
        return None


def get_album_art(artist: str, album: str, musicbrainz_release_group_id: Optional[str] = None) -> Tuple[Optional[bytes], Optional[str]]:
    """
    Download album art from Cover Art Archive (MusicBrainz).
    Returns tuple: (image data as bytes, release_group_id) or (None, release_group_id) if not found.
    """
    try:
        # If we have a MusicBrainz release group ID, use it directly
        if musicbrainz_release_group_id:
            release_group_id = musicbrainz_release_group_id
        else:
            # Search MusicBrainz for the release group
            release_group_id = search_musicbrainz_release_group(artist, album)
            if not release_group_id:
                return None, None
        
        # Get cover art from Cover Art Archive
        cover_art_url = f"https://coverartarchive.org/release-group/{release_group_id}/front"
        
        headers = {
            'User-Agent': 'AudioMetadataRepair/1.0 (https://github.com/yourusername)'
        }
        
        response = requests.get(cover_art_url, headers=headers, timeout=10, allow_redirects=True)
        
        if response.status_code == 200:
            return response.content, release_group_id
        elif response.status_code == 404:
            # Try to get from releases instead
            releases_url = f"https://musicbrainz.org/ws/2/release-group/{release_group_id}"
            params = {'inc': 'releases', 'fmt': 'json'}
            response = requests.get(releases_url, params=params, headers=headers, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                releases = data.get('releases', [])
                if releases:
                    release_id = releases[0]['id']
                    cover_art_url = f"https://coverartarchive.org/release/{release_id}/front"
                    response = requests.get(cover_art_url, headers=headers, timeout=10, allow_redirects=True)
                    if response.status_code == 200:
                        return response.content, release_group_id
        
        return None, release_group_id
    except Exception as e:
        print(f"  Warning: Could not download album art: {e}")
        return None, None


def embed_album_art_mp3(file_path: Path, image_data: bytes, mime_type: str = 'image/jpeg'):
    """Embed album art into an MP3 file."""
    try:
        audio_file = MP3(str(file_path), ID3=ID3)
        
        if audio_file.tags is None:
            audio_file.add_tags()
        
        # Remove existing album art
        if 'APIC:' in audio_file.tags:
            del audio_file.tags['APIC:']
        
        # Add new album art
        audio_file.tags.add(
            APIC(
                encoding=3,
                mime=mime_type,
                type=3,  # Cover (front)
                desc='Cover',
                data=image_data
            )
        )
        
        audio_file.save()
        return True
    except Exception as e:
        print(f"  Error embedding album art: {e}")
        return False


def embed_album_art_flac(file_path: Path, image_data: bytes, mime_type: str = 'image/jpeg'):
    """Embed album art into a FLAC file."""
    try:
        audio_file = FLAC(str(file_path))
        
        # Remove existing pictures
        audio_file.clear_pictures()
        
        # Create picture block
        picture = Picture()
        picture.type = 3  # Cover (front)
        picture.mime = mime_type
        picture.data = image_data
        
        audio_file.add_picture(picture)
        audio_file.save()
        return True
    except Exception as e:
        print(f"  Error embedding album art: {e}")
        return False


# ============================================================================
# Parsing Functions
# ============================================================================

def parse_album_nfo(nfo_path: Path) -> Optional[Dict]:
    """Parse album.nfo file and extract metadata."""
    try:
        tree = ET.parse(nfo_path)
        root = tree.getroot()
        
        metadata = {
            'album': root.findtext('title', '').strip(),
            'artist': root.findtext('artist', '').strip(),
            'albumartist': root.findtext('albumartist', '').strip(),
            'year': root.findtext('year', '').strip(),
            'genre': root.findtext('genre', '').strip(),
            'musicbrainz_release_group_id': root.findtext('musicbrainzreleasegroupid', '').strip(),
            'tracks': {}
        }
        
        # Parse track information
        for track in root.findall('track'):
            position = track.findtext('position', '').strip()
            title = track.findtext('title', '').strip()
            if position and title:
                metadata['tracks'][int(position)] = title
        
        return metadata
    except Exception as e:
        print(f"Warning: Could not parse {nfo_path}: {e}")
        return None


def generate_album_nfo(nfo_path: Path, album_metadata: Dict, tracks: Dict[int, str]) -> bool:
    """
    Generate an album.nfo file with the provided metadata and track information.
    
    Args:
        nfo_path: Path where the album.nfo file should be created
        album_metadata: Dictionary containing album-level metadata
        tracks: Dictionary mapping track numbers to track titles
    """
    try:
        # Create root element
        root = ET.Element('album')
        
        # Add review and outline (empty, as in original format)
        ET.SubElement(root, 'review')
        ET.SubElement(root, 'outline')
        
        # Add lockdata
        lockdata = ET.SubElement(root, 'lockdata')
        lockdata.text = 'false'
        
        # Add dateadded
        dateadded = ET.SubElement(root, 'dateadded')
        dateadded.text = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # Add title (album name)
        title = ET.SubElement(root, 'title')
        title.text = album_metadata.get('album', '').strip()
        
        # Add year
        year = ET.SubElement(root, 'year')
        year.text = album_metadata.get('year', '').strip()
        
        # Add premiered and releasedate (use year if available)
        year_value = album_metadata.get('year', '').strip()
        if year_value:
            premiered = ET.SubElement(root, 'premiered')
            premiered.text = f"{year_value}-01-01"
            releasedate = ET.SubElement(root, 'releasedate')
            releasedate.text = f"{year_value}-01-01"
        
        # Add runtime (empty for now, could be calculated from track durations)
        runtime = ET.SubElement(root, 'runtime')
        runtime.text = ''
        
        # Add genre
        genre = ET.SubElement(root, 'genre')
        genre.text = album_metadata.get('genre', '').strip()
        
        # Add MusicBrainz IDs if available
        mb_id = album_metadata.get('musicbrainz_release_group_id', '').strip()
        if mb_id:
            mb_album_id = ET.SubElement(root, 'musicbrainzalbumid')
            mb_album_id.text = mb_id
            mb_release_group_id = ET.SubElement(root, 'musicbrainzreleasegroupid')
            mb_release_group_id.text = mb_id
        
        # Add art (empty, art is embedded in files)
        ET.SubElement(root, 'art')
        
        # Add artist
        artist = ET.SubElement(root, 'artist')
        artist.text = album_metadata.get('artist', '').strip()
        
        # Add albumartist
        albumartist = ET.SubElement(root, 'albumartist')
        albumartist.text = album_metadata.get('albumartist', album_metadata.get('artist', '')).strip()
        
        # Add tracks in sorted order
        for track_num in sorted(tracks.keys()):
            track_elem = ET.SubElement(root, 'track')
            position = ET.SubElement(track_elem, 'position')
            position.text = str(track_num)
            title = ET.SubElement(track_elem, 'title')
            title.text = tracks[track_num].strip()
            # Duration not available from filename parsing
            duration = ET.SubElement(track_elem, 'duration')
            duration.text = ''
        
        # Create tree and write to file
        tree = ET.ElementTree(root)
        ET.indent(tree, space='  ')  # Pretty print with 2-space indentation
        
        # Write to file with proper XML declaration
        tree.write(nfo_path, encoding='utf-8', xml_declaration=True)
        return True
    except Exception as e:
        print(f"  Warning: Could not generate album.nfo: {e}")
        return False


def parse_filename(filename: str) -> Optional[Dict]:
    """
    Parse filename to extract metadata.
    Expected format: "Artist - Album - TrackNumber - Title.ext"
    """
    # Remove extension
    name_without_ext = Path(filename).stem
    
    # Try to match pattern: Artist - Album - TrackNumber - Title
    pattern = r'^(.+?)\s*-\s*(.+?)\s*-\s*(\d+)\s*-\s*(.+)$'
    match = re.match(pattern, name_without_ext)
    
    if match:
        artist, album, track_num, title = match.groups()
        return {
            'artist': artist.strip(),
            'album': album.strip(),
            'tracknumber': int(track_num),
            'title': title.strip()
        }
    
    # Try simpler pattern: Artist - Title
    pattern2 = r'^(.+?)\s*-\s*(.+)$'
    match2 = re.match(pattern2, name_without_ext)
    if match2:
        artist, title = match2.groups()
        return {
            'artist': artist.strip(),
            'title': title.strip()
        }
    
    return None


def fix_filename(file_path: Path, metadata: Dict, album_metadata: Optional[Dict] = None) -> bool:
    """
    Rename a file to match the expected format: "Artist - Album - TrackNumber - Title.ext"
    
    Args:
        file_path: Path to the file to rename
        metadata: Dictionary with track metadata (from filename or tags)
        album_metadata: Optional album-level metadata (from album.nfo)
    
    Returns:
        True if file was renamed, False otherwise
    """
    try:
        # Get metadata from parameters or try to read from file tags
        artist = metadata.get('artist', '')
        album = metadata.get('album', '')
        track_number = metadata.get('tracknumber', 0)
        title = metadata.get('title', '')
        
        # If missing, try to get from album metadata
        if not artist and album_metadata:
            artist = album_metadata.get('artist', '')
        if not album and album_metadata:
            album = album_metadata.get('album', '')
        
        # If still missing, try to read from file tags
        if not artist or not album or not track_number or not title:
            if file_path.suffix.lower() == '.mp3':
                try:
                    audio_file = MP3(str(file_path))
                    if not artist:
                        artist = audio_file.get('TPE1', [''])[0] or audio_file.get('TPE2', [''])[0]
                    if not album:
                        album = audio_file.get('TALB', [''])[0]
                    if not track_number:
                        track_num_str = audio_file.get('TRCK', ['0'])[0]
                        try:
                            track_number = int(track_num_str.split('/')[0])
                        except:
                            track_number = 0
                    if not title:
                        title = audio_file.get('TIT2', [''])[0]
                except:
                    pass
            elif file_path.suffix.lower() == '.flac':
                try:
                    audio_file = FLAC(str(file_path))
                    if not artist:
                        artist = audio_file.get('ARTIST', [''])[0] or audio_file.get('ALBUMARTIST', [''])[0]
                    if not album:
                        album = audio_file.get('ALBUM', [''])[0]
                    if not track_number:
                        track_num_str = audio_file.get('TRACKNUMBER', ['0'])[0]
                        try:
                            track_number = int(track_num_str.split('/')[0])
                        except:
                            track_number = 0
                    if not title:
                        title = audio_file.get('TITLE', [''])[0]
                except:
                    pass
        
        # Check if we have all required fields
        if not artist or not album or not track_number or not title:
            return False
        
        # Format track number with zero padding
        track_str = f"{track_number:02d}"
        
        # Clean up strings (remove invalid filename characters)
        def clean_filename(s: str) -> str:
            # Remove invalid characters for Windows/Linux
            invalid_chars = '<>:"/\\|?*'
            for char in invalid_chars:
                s = s.replace(char, '')
            # Replace multiple spaces with single space
            s = ' '.join(s.split())
            return s.strip()
        
        artist = clean_filename(artist)
        album = clean_filename(album)
        title = clean_filename(title)
        
        # Build new filename
        new_name = f"{artist} - {album} - {track_str} - {title}{file_path.suffix}"
        new_path = file_path.parent / new_name
        
        # Check if new filename is different
        if new_path == file_path:
            return False  # Already correct format
        
        # Check if target file already exists
        if new_path.exists():
            return False  # Would overwrite existing file
        
        # Rename the file
        file_path.rename(new_path)
        return True
        
    except Exception as e:
        print(f"  Error fixing filename: {e}")
        return False


# ============================================================================
# Repair Functions
# ============================================================================

def repair_mp3_metadata(file_path: Path, metadata: Dict, album_metadata: Optional[Dict] = None, album_art: Optional[bytes] = None):
    """Repair metadata for MP3 files."""
    try:
        audio_file = MP3(str(file_path), ID3=ID3)
        
        # Create ID3 tag if it doesn't exist
        if audio_file.tags is None:
            audio_file.add_tags()
        
        # Set metadata from parsed filename
        if 'title' in metadata:
            audio_file.tags['TIT2'] = TIT2(encoding=3, text=metadata['title'])
        
        if 'artist' in metadata:
            audio_file.tags['TPE1'] = TPE1(encoding=3, text=metadata['artist'])
        
        if 'album' in metadata:
            audio_file.tags['TALB'] = TALB(encoding=3, text=metadata['album'])
        
        if 'tracknumber' in metadata:
            audio_file.tags['TRCK'] = TRCK(encoding=3, text=str(metadata['tracknumber']))
        
        # Use album.nfo metadata if available
        if album_metadata:
            if album_metadata.get('album') and not metadata.get('album'):
                audio_file.tags['TALB'] = TALB(encoding=3, text=album_metadata['album'])
            
            if album_metadata.get('albumartist'):
                audio_file.tags['TPE2'] = TPE2(encoding=3, text=album_metadata['albumartist'])
            
            if album_metadata.get('year'):
                audio_file.tags['TDRC'] = TDRC(encoding=3, text=album_metadata['year'])
            
            if album_metadata.get('genre'):
                audio_file.tags['TCON'] = TCON(encoding=3, text=album_metadata['genre'])
            
            # Update track title from album.nfo if available
            if 'tracknumber' in metadata:
                track_num = metadata['tracknumber']
                if track_num in album_metadata.get('tracks', {}):
                    audio_file.tags['TIT2'] = TIT2(encoding=3, text=album_metadata['tracks'][track_num])
        
        # Embed album art if provided
        if album_art:
            # Detect MIME type from image data
            mime_type = 'image/jpeg'
            if album_art.startswith(b'\x89PNG'):
                mime_type = 'image/png'
            elif album_art.startswith(b'GIF'):
                mime_type = 'image/gif'
            elif album_art.startswith(b'RIFF') and b'WEBP' in album_art[:12]:
                mime_type = 'image/webp'
            embed_album_art_mp3(file_path, album_art, mime_type)
        
        audio_file.save()
        return True
    except Exception as e:
        print(f"Error repairing {file_path}: {e}")
        return False


def repair_flac_metadata(file_path: Path, metadata: Dict, album_metadata: Optional[Dict] = None, album_art: Optional[bytes] = None):
    """Repair metadata for FLAC files."""
    try:
        audio_file = FLAC(str(file_path))
        
        # Set metadata from parsed filename
        if 'title' in metadata:
            audio_file['TITLE'] = metadata['title']
        
        if 'artist' in metadata:
            audio_file['ARTIST'] = metadata['artist']
        
        if 'album' in metadata:
            audio_file['ALBUM'] = metadata['album']
        
        if 'tracknumber' in metadata:
            audio_file['TRACKNUMBER'] = str(metadata['tracknumber'])
        
        # Use album.nfo metadata if available
        if album_metadata:
            if album_metadata.get('album') and not metadata.get('album'):
                audio_file['ALBUM'] = album_metadata['album']
            
            if album_metadata.get('albumartist'):
                audio_file['ALBUMARTIST'] = album_metadata['albumartist']
            
            if album_metadata.get('year'):
                audio_file['DATE'] = album_metadata['year']
            
            if album_metadata.get('genre'):
                audio_file['GENRE'] = album_metadata['genre']
            
            # Update track title from album.nfo if available
            if 'tracknumber' in metadata:
                track_num = metadata['tracknumber']
                if track_num in album_metadata.get('tracks', {}):
                    audio_file['TITLE'] = album_metadata['tracks'][track_num]
        
        # Embed album art if provided
        if album_art:
            # Detect MIME type from image data
            mime_type = 'image/jpeg'
            if album_art.startswith(b'\x89PNG'):
                mime_type = 'image/png'
            elif album_art.startswith(b'GIF'):
                mime_type = 'image/gif'
            elif album_art.startswith(b'RIFF') and b'WEBP' in album_art[:12]:
                mime_type = 'image/webp'
            embed_album_art_flac(file_path, album_art, mime_type)
        
        audio_file.save()
        return True
    except Exception as e:
        print(f"Error repairing {file_path}: {e}")
        return False


def repair_audio_file(file_path: Path, base_dir: Path, album_art_cache: Dict[str, Optional[bytes]], 
                      log_data: Dict, log_file: Path) -> Tuple[bool, Optional[Dict]]:
    """
    Repair metadata for a single audio file.
    
    Returns:
        tuple: (success: bool, metadata: Optional[Dict]) where metadata contains
               album directory path, album metadata, and track info for nfo generation
    """
    # Check if file has already been processed
    if is_file_processed(file_path, log_data):
        print(f"  ⊘ Already processed (skipping)")
        return True, None
    
    # Check if album.nfo exists in the same directory
    album_nfo_path = file_path.parent / 'album.nfo'
    album_metadata = None
    if album_nfo_path.exists():
        album_metadata = parse_album_nfo(album_nfo_path)
    
    # Parse filename to extract metadata
    filename_metadata = parse_filename(file_path.name)
    
    if not filename_metadata:
        print(f"Warning: Could not parse filename: {file_path.name}")
        return False, None
    
    # Merge metadata (filename takes precedence for track-specific info)
    metadata = filename_metadata.copy()
    
    # Get album art (download once per album)
    album_art = None
    artist = metadata.get('artist') or (album_metadata.get('artist') if album_metadata else None)
    album = metadata.get('album') or (album_metadata.get('album') if album_metadata else None)
    
    if artist and album:
        album_key = f"{artist}||{album}"
        
        # Check log first to see if we've already tried to download art for this album
        if has_album_art_downloaded(artist, album, log_data):
            # Check if we have it in cache from this session
            if album_key in album_art_cache:
                album_art = album_art_cache[album_key]
                if album_art:
                    print(f"  ✓ Using cached album art")
                else:
                    print(f"  ⊘ Album art download previously failed (skipping)")
            else:
                # We tried before but don't have it cached, so skip download
                print(f"  ⊘ Album art already attempted (skipping download)")
                album_art = None
        else:
            # Check cache first (in case we downloaded it earlier in this session)
            if album_key not in album_art_cache:
                print(f"  Downloading album art for: {artist} - {album}")
                musicbrainz_id = album_metadata.get('musicbrainz_release_group_id') if album_metadata else None
                album_art_data, found_mb_id = get_album_art(artist, album, musicbrainz_id)
                album_art_cache[album_key] = album_art_data
                # Mark in log that we attempted download, store MusicBrainz ID if found
                mark_album_art_downloaded(artist, album, log_data, album_art_data is not None, found_mb_id)
                # Save log after each album art download attempt
                save_log(log_data, log_file)
                # Be polite to the API
                time.sleep(0.5)
                album_art = album_art_data
            else:
                album_art = album_art_cache[album_key]
            
            if album_art:
                print(f"  ✓ Found album art")
            else:
                print(f"  ⚠ No album art found")
    
    # Repair based on file type
    success = False
    if file_path.suffix.lower() == '.mp3':
        success = repair_mp3_metadata(file_path, metadata, album_metadata, album_art)
    elif file_path.suffix.lower() == '.flac':
        success = repair_flac_metadata(file_path, metadata, album_metadata, album_art)
    else:
        print(f"Unsupported file type: {file_path.suffix}")
        return False, None
    
    # Mark file as processed if successful
    if success:
        mark_file_processed(file_path, log_data, has_art=(album_art is not None))
        save_log(log_data, log_file)
        
        # Return metadata for nfo generation if we have album info
        if artist and album:
            return success, {
                'album_dir': file_path.parent,
                'album_metadata': {
                    'album': album,
                    'artist': artist,
                    'albumartist': album_metadata.get('albumartist', artist) if album_metadata else artist,
                    'year': album_metadata.get('year', '') if album_metadata else '',
                    'genre': album_metadata.get('genre', '') if album_metadata else '',
                    'musicbrainz_release_group_id': album_metadata.get('musicbrainz_release_group_id', '') if album_metadata else ''
                },
                'track_number': metadata.get('tracknumber'),
                'track_title': metadata.get('title', '')
            }
    
    return success, None

