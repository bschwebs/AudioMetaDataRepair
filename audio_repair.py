#!/usr/bin/env python3
"""
Audio Metadata Repair Module

Contains all functions for repairing audio file metadata and downloading album art.
Supports MP3, FLAC, OGG, Opus, and M4A/MP4 formats.
"""

# Standard library imports
import base64
import json
import re
import time
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

# Third-party imports
import requests
from mutagen import File as MutagenFile
from mutagen.flac import FLAC, Picture
from mutagen.id3 import APIC, ID3, TALB, TCON, TDRC, TIT2, TPE1, TPE2, TRCK
from mutagen.mp3 import MP3
from mutagen.mp4 import MP4, MP4Cover

# Constants
MUSICBRAINZ_API_URL = "https://musicbrainz.org/ws/2"
COVER_ART_ARCHIVE_URL = "https://coverartarchive.org"
USER_AGENT = "AudioMetadataRepair/2.0 (https://github.com/bschwebs/AudioMetaDataRepair)"
API_TIMEOUT = 10
API_RATE_LIMIT_DELAY = 0.5

# Supported audio file extensions
SUPPORTED_EXTENSIONS = {'.mp3', '.flac', '.ogg', '.opus', '.m4a', '.mp4'}

# Image MIME type detection signatures
IMAGE_SIGNATURES = {
    b'\x89PNG': 'image/png',
    b'GIF87a': 'image/gif',
    b'GIF89a': 'image/gif',
    b'RIFF': 'image/webp',  # Checked with WEBP in header
}

# Default MIME type
DEFAULT_MIME_TYPE = 'image/jpeg'


# ============================================================================
# Logging Functions
# ============================================================================

def load_log(log_file: Path) -> Dict:
    """
    Load the processing log from JSON file.

    Args:
        log_file: Path to the log file

    Returns:
        Dictionary containing log data with 'processed_files' and 'album_art' keys
    """
    if not log_file.exists():
        return {'processed_files': {}, 'album_art': {}}
    
    try:
        with open(log_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        print(f"Warning: Could not load log file: {e}")
        print("Starting with empty log.")
        return {'processed_files': {}, 'album_art': {}}


def save_log(log_data: Dict, log_file: Path) -> None:
    """
    Save the processing log to JSON file.

    Args:
        log_data: Dictionary containing log data
        log_file: Path to the log file
    """
    try:
        with open(log_file, 'w', encoding='utf-8') as f:
            json.dump(log_data, f, indent=2, ensure_ascii=False)
    except IOError as e:
        print(f"Warning: Could not save log file: {e}")


def is_file_processed(file_path: Path, log_data: Dict) -> bool:
    """
    Check if a file has already been processed and hasn't been modified since.

    Args:
        file_path: Path to the file to check
        log_data: Dictionary containing log data

    Returns:
        True if file was processed and hasn't been modified, False otherwise
    """
    file_str = str(file_path)
    processed_files = log_data.get('processed_files', {})
    
    if file_str not in processed_files:
        return False
    
    if not file_path.exists():
        return False
    
    try:
        file_info = processed_files[file_str]
        current_mtime = file_path.stat().st_mtime
        logged_mtime = file_info.get('file_mtime', 0)
        
        # File needs reprocessing if it was modified after last processing
        return current_mtime <= logged_mtime
    except OSError:
        return False


def mark_file_processed(file_path: Path, log_data: Dict, has_art: bool = False) -> None:
    """
    Mark a file as processed in the log.

    Args:
        file_path: Path to the processed file
        log_data: Dictionary containing log data
        has_art: Whether the file has album art embedded
    """
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
    """
    Check if album art has already been downloaded for this album.

    Args:
        artist: Artist name
        album: Album name
        log_data: Dictionary containing log data

    Returns:
        True if album art was successfully downloaded, False otherwise
    """
    album_key = f"{artist}||{album}"
    album_art_data = log_data.get('album_art', {})
    
    if album_key not in album_art_data:
        return False
    
    return album_art_data[album_key].get('downloaded', False)


def get_failed_albums(log_data: Dict) -> List[Dict[str, str]]:
    """
    Get list of albums that failed to download art.

    Args:
        log_data: Dictionary containing log data

    Returns:
        List of dictionaries with artist, album, musicbrainz_id, and last_attempted keys
    """
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


def retry_album_art_with_id(
    artist: str,
    album: str,
    musicbrainz_id: str,
    log_data: Dict,
    log_file: Path
) -> Tuple[bool, Optional[bytes]]:
    """
    Retry downloading album art using a specific MusicBrainz release group ID.

    Args:
        artist: Artist name
        album: Album name
        musicbrainz_id: MusicBrainz release group ID
        log_data: Dictionary containing log data
        log_file: Path to the log file

    Returns:
        Tuple of (success: bool, image_data: Optional[bytes])
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


def batch_search_musicbrainz_ids(
    failed_albums: List[Dict[str, str]],
    progress_callback: Optional[Callable[[str, str], None]] = None
) -> Dict[str, str]:
    """
    Batch search for MusicBrainz IDs for multiple albums.

    Args:
        failed_albums: List of dictionaries with 'artist' and 'album' keys
        progress_callback: Optional callback function(album_key, mb_id) for progress updates

    Returns:
        Dictionary mapping album_key (artist||album) to MusicBrainz ID or empty string
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
        
        # Respect API rate limits
        time.sleep(API_RATE_LIMIT_DELAY)
    
    return results


def mark_album_art_downloaded(
    artist: str,
    album: str,
    log_data: Dict,
    success: bool,
    musicbrainz_id: Optional[str] = None
) -> None:
    """
    Mark album art as downloaded (or attempted) in the log.

    Args:
        artist: Artist name
        album: Album name
        log_data: Dictionary containing log data
        success: Whether the download was successful
        musicbrainz_id: Optional MusicBrainz release group ID
    """
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

    Args:
        artist: Artist name
        album: Album name

    Returns:
        Release group ID if found, None otherwise
    """
    try:
        search_url = f"{MUSICBRAINZ_API_URL}/release-group"
        params = {
            'query': f'artist:"{artist}" AND release:"{album}"',
            'fmt': 'json',
            'limit': 1
        }
        
        headers = {'User-Agent': USER_AGENT}
        
        response = requests.get(
            search_url,
            params=params,
            headers=headers,
            timeout=API_TIMEOUT
        )
        response.raise_for_status()
        data = response.json()
        
        release_groups = data.get('release-groups', [])
        if not release_groups:
            return None
        
        return release_groups[0]['id']
    except Exception as e:
        print(f"  Warning: Could not search MusicBrainz: {e}")
        return None


def get_album_art(
    artist: str,
    album: str,
    musicbrainz_release_group_id: Optional[str] = None
) -> Tuple[Optional[bytes], Optional[str]]:
    """
    Download album art from Cover Art Archive (MusicBrainz).

    Args:
        artist: Artist name
        album: Album name
        musicbrainz_release_group_id: Optional MusicBrainz release group ID

    Returns:
        Tuple of (image data as bytes, release_group_id) or (None, release_group_id) if not found
    """
    try:
        # Use provided ID or search for it
        release_group_id = musicbrainz_release_group_id
        if not release_group_id:
            release_group_id = search_musicbrainz_release_group(artist, album)
            if not release_group_id:
                return None, None
        
        # Try to get cover art from release group
        cover_art_url = f"{COVER_ART_ARCHIVE_URL}/release-group/{release_group_id}/front"
        headers = {'User-Agent': USER_AGENT}
        
        response = requests.get(
            cover_art_url,
            headers=headers,
            timeout=API_TIMEOUT,
            allow_redirects=True
        )
        
        if response.status_code == 200:
            return response.content, release_group_id
        
        if response.status_code == 404:
            # Fallback: try individual releases
            return _try_release_art(release_group_id, headers)
        
        return None, release_group_id
    except Exception as e:
        print(f"  Warning: Could not download album art: {e}")
        return None, None


def _try_release_art(release_group_id: str, headers: Dict[str, str]) -> Tuple[Optional[bytes], Optional[str]]:
    """
    Try to get album art from individual releases as fallback.

    Args:
        release_group_id: MusicBrainz release group ID
        headers: HTTP headers to use

    Returns:
        Tuple of (image data, release_group_id) or (None, release_group_id)
    """
    try:
        releases_url = f"{MUSICBRAINZ_API_URL}/release-group/{release_group_id}"
        params = {'inc': 'releases', 'fmt': 'json'}
        
        response = requests.get(
            releases_url,
            params=params,
            headers=headers,
            timeout=API_TIMEOUT
        )
        
        if response.status_code != 200:
            return None, release_group_id
        
        data = response.json()
        releases = data.get('releases', [])
        if not releases:
            return None, release_group_id
        
        # Try first release
        release_id = releases[0]['id']
        cover_art_url = f"{COVER_ART_ARCHIVE_URL}/release/{release_id}/front"
        
        response = requests.get(
            cover_art_url,
            headers=headers,
            timeout=API_TIMEOUT,
            allow_redirects=True
        )
        
        if response.status_code == 200:
            return response.content, release_group_id
        
        return None, release_group_id
    except Exception:
        return None, release_group_id


def detect_mime_type(image_data: bytes) -> str:
    """
    Detect MIME type from image data signature.

    Args:
        image_data: Image file data as bytes

    Returns:
        MIME type string (defaults to 'image/jpeg')
    """
    # Check PNG signature
    if image_data[:4] == b'\x89PNG':
        return 'image/png'
    
    # Check GIF signatures
    if image_data[:6] in (b'GIF87a', b'GIF89a'):
        return 'image/gif'
    
    # Check WebP signature (RIFF header with WEBP in bytes 8-12)
    if image_data[:4] == b'RIFF' and b'WEBP' in image_data[8:12]:
        return 'image/webp'
    
    return DEFAULT_MIME_TYPE


def embed_album_art_mp3(file_path: Path, image_data: bytes, mime_type: str = DEFAULT_MIME_TYPE):
    """
    Embed album art into an MP3 file.

    Args:
        file_path: Path to the MP3 file
        image_data: Image data as bytes
        mime_type: MIME type of the image

    Returns:
        True if successful, False otherwise
    """
    try:
        audio_file = MP3(str(file_path), ID3=ID3)
        
        if audio_file.tags is None:
            audio_file.add_tags()
        
        # Remove existing album art
        if 'APIC:' in audio_file.tags:
            del audio_file.tags['APIC:']
        
        # Add new album art (type 3 = Cover front)
        audio_file.tags.add(
            APIC(
                encoding=3,
                mime=mime_type,
                type=3,
                desc='Cover',
                data=image_data
            )
        )
        
        audio_file.save()
        return True
    except Exception as e:
        print(f"  Error embedding album art: {e}")
        return False


def embed_album_art_flac(file_path: Path, image_data: bytes, mime_type: str = DEFAULT_MIME_TYPE):
    """
    Embed album art into a FLAC file.

    Args:
        file_path: Path to the FLAC file
        image_data: Image data as bytes
        mime_type: MIME type of the image

    Returns:
        True if successful, False otherwise
    """
    try:
        audio_file = FLAC(str(file_path))
        audio_file.clear_pictures()
        
        # Create picture block (type 3 = Cover front)
        picture = Picture()
        picture.type = 3
        picture.mime = mime_type
        picture.data = image_data
        
        audio_file.add_picture(picture)
        audio_file.save()
        return True
    except Exception as e:
        print(f"  Error embedding album art: {e}")
        return False


def embed_album_art_ogg(file_path: Path, image_data: bytes, mime_type: str = DEFAULT_MIME_TYPE):
    """
    Embed album art into an OGG Vorbis or Opus file.

    Args:
        file_path: Path to the OGG file
        image_data: Image data as bytes
        mime_type: MIME type of the image

    Returns:
        True if successful, False otherwise
    """
    try:
        audio_file = MutagenFile(str(file_path))
        if audio_file is None:
            return False
        
        # Remove existing cover art
        for key in ('metadata_block_picture', 'METADATA_BLOCK_PICTURE'):
            if key in audio_file:
                del audio_file[key]
        
        # Create picture block (same format as FLAC, type 3 = Cover front)
        picture = Picture()
        picture.type = 3
        picture.mime = mime_type
        picture.data = image_data
        
        # Encode picture as base64 for OGG format
        picture_data = picture.write()
        encoded = base64.b64encode(picture_data).decode('ascii')
        
        audio_file['metadata_block_picture'] = [encoded]
        audio_file.save()
        return True
    except Exception as e:
        print(f"  Error embedding album art: {e}")
        return False


def embed_album_art_mp4(file_path: Path, image_data: bytes, mime_type: str = DEFAULT_MIME_TYPE):
    """
    Embed album art into an MP4/M4A file.

    Args:
        file_path: Path to the MP4/M4A file
        image_data: Image data as bytes
        mime_type: MIME type of the image

    Returns:
        True if successful, False otherwise
    """
    try:
        audio_file = MP4(str(file_path))
        
        # Remove existing cover art
        if 'covr' in audio_file:
            del audio_file['covr']
        
        # Determine image format
        if 'png' in mime_type:
            image_format = MP4Cover.FORMAT_PNG
        else:
            image_format = MP4Cover.FORMAT_JPEG  # Default to JPEG
        
        cover = MP4Cover(image_data, imageformat=image_format)
        audio_file['covr'] = [cover]
        audio_file.save()
        return True
    except Exception as e:
        print(f"  Error embedding album art: {e}")
        return False


# ============================================================================
# Parsing Functions
# ============================================================================

def parse_album_nfo(nfo_path: Path) -> Optional[Dict]:
    """
    Parse album.nfo file and extract metadata.

    Args:
        nfo_path: Path to the album.nfo file

    Returns:
        Dictionary containing album metadata and tracks, or None if parsing fails
    """
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

    Returns:
        True if successful, False otherwise
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

    Args:
        filename: Filename to parse (with or without extension)

    Returns:
        Dictionary with artist, album, tracknumber, and title keys, or None if parsing fails

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
            suffix = file_path.suffix.lower()
            try:
                if suffix == '.mp3':
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
                elif suffix == '.flac':
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
                elif suffix in ('.ogg', '.opus'):
                    audio_file = MutagenFile(str(file_path))
                    if audio_file:
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
                elif suffix in ('.m4a', '.mp4'):
                    audio_file = MP4(str(file_path))
                    if not artist:
                        artist = audio_file.get('\xa9ART', [''])[0] or audio_file.get('aART', [''])[0]
                    if not album:
                        album = audio_file.get('\xa9alb', [''])[0]
                    if not track_number:
                        track_list = audio_file.get('trkn', [(0, 0)])
                        if track_list:
                            track_number = track_list[0][0]
                    if not title:
                        title = audio_file.get('\xa9nam', [''])[0]
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

def repair_mp3_metadata(
    file_path: Path,
    metadata: Dict,
    album_metadata: Optional[Dict] = None,
    album_art: Optional[bytes] = None
) -> bool:
    """
    Repair metadata for MP3 files.

    Args:
        file_path: Path to the MP3 file
        metadata: Dictionary containing track metadata
        album_metadata: Optional album-level metadata
        album_art: Optional album art image data

    Returns:
        True if successful, False otherwise
    """
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
            mime_type = detect_mime_type(album_art)
            embed_album_art_mp3(file_path, album_art, mime_type)
        
        audio_file.save()
        return True
    except Exception as e:
        print(f"Error repairing {file_path}: {e}")
        return False


def repair_flac_metadata(
    file_path: Path,
    metadata: Dict,
    album_metadata: Optional[Dict] = None,
    album_art: Optional[bytes] = None
) -> bool:
    """
    Repair metadata for FLAC files.

    Args:
        file_path: Path to the FLAC file
        metadata: Dictionary containing track metadata
        album_metadata: Optional album-level metadata
        album_art: Optional album art image data

    Returns:
        True if successful, False otherwise
    """
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
            mime_type = detect_mime_type(album_art)
            embed_album_art_flac(file_path, album_art, mime_type)
        
        audio_file.save()
        return True
    except Exception as e:
        print(f"Error repairing {file_path}: {e}")
        return False


def repair_ogg_metadata(
    file_path: Path,
    metadata: Dict,
    album_metadata: Optional[Dict] = None,
    album_art: Optional[bytes] = None
) -> bool:
    """
    Repair metadata for OGG Vorbis or Opus files.

    Args:
        file_path: Path to the OGG file
        metadata: Dictionary containing track metadata
        album_metadata: Optional album-level metadata
        album_art: Optional album art image data

    Returns:
        True if successful, False otherwise
    """
    try:
        audio_file = MutagenFile(str(file_path))
        
        if audio_file is None:
            return False
        
        # Set metadata tags (OGG uses Vorbis comment format)
        if 'title' in metadata:
            audio_file['TITLE'] = metadata['title']
        
        if 'artist' in metadata:
            audio_file['ARTIST'] = metadata['artist']
        
        if 'album' in metadata:
            audio_file['ALBUM'] = metadata['album']
        
        if 'tracknumber' in metadata:
            audio_file['TRACKNUMBER'] = str(metadata['tracknumber'])
        
        # Use album metadata if available
        if album_metadata:
            if album_metadata.get('album') and not metadata.get('album'):
                audio_file['ALBUM'] = album_metadata['album']
            
            if album_metadata.get('albumartist'):
                audio_file['ALBUMARTIST'] = album_metadata['albumartist']
            elif album_metadata.get('artist'):
                audio_file['ALBUMARTIST'] = album_metadata['artist']
            
            if album_metadata.get('year'):
                audio_file['DATE'] = album_metadata['year']
            
            if album_metadata.get('genre'):
                audio_file['GENRE'] = album_metadata['genre']
            
            # Update track title from album.nfo if available
            if 'tracknumber' in metadata:
                track_num = metadata['tracknumber']
                if track_num in album_metadata.get('tracks', {}):
                    audio_file['TITLE'] = album_metadata['tracks'][track_num]
        
        audio_file.save()
        
        # Embed album art if provided
        if album_art:
            mime_type = detect_mime_type(album_art)
            embed_album_art_ogg(file_path, album_art, mime_type)
        return True
    except Exception as e:
        print(f"Error repairing {file_path}: {e}")
        return False


def repair_mp4_metadata(
    file_path: Path,
    metadata: Dict,
    album_metadata: Optional[Dict] = None,
    album_art: Optional[bytes] = None
) -> bool:
    """
    Repair metadata for MP4/M4A files.

    Args:
        file_path: Path to the MP4/M4A file
        metadata: Dictionary containing track metadata
        album_metadata: Optional album-level metadata
        album_art: Optional album art image data

    Returns:
        True if successful, False otherwise
    """
    try:
        audio_file = MP4(str(file_path))
        
        # Set metadata tags
        if 'title' in metadata:
            audio_file['\xa9nam'] = metadata['title']  # Title
        
        if 'artist' in metadata:
            audio_file['\xa9ART'] = metadata['artist']  # Artist
        
        if 'album' in metadata:
            audio_file['\xa9alb'] = metadata['album']  # Album
        
        if 'tracknumber' in metadata:
            audio_file['trkn'] = [(metadata['tracknumber'], 0)]  # Track number, total tracks
        
        # Use album metadata if available
        if album_metadata:
            if album_metadata.get('album') and not metadata.get('album'):
                audio_file['\xa9alb'] = album_metadata['album']
            
            if album_metadata.get('albumartist'):
                audio_file['aART'] = album_metadata['albumartist']  # Album Artist
            elif album_metadata.get('artist'):
                audio_file['aART'] = album_metadata['artist']
            
            if album_metadata.get('year'):
                audio_file['\xa9day'] = album_metadata['year']  # Date/Year
            
            if album_metadata.get('genre'):
                audio_file['\xa9gen'] = album_metadata['genre']  # Genre
            
            # Update track title from album.nfo if available
            if 'tracknumber' in metadata:
                track_num = metadata['tracknumber']
                if track_num in album_metadata.get('tracks', {}):
                    audio_file['\xa9nam'] = album_metadata['tracks'][track_num]
        
        audio_file.save()
        
        # Embed album art if provided
        if album_art:
            embed_album_art_mp4(file_path, album_art)
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
                # Respect API rate limits
                time.sleep(API_RATE_LIMIT_DELAY)
                album_art = album_art_data
            else:
                album_art = album_art_cache[album_key]
            
            if album_art:
                print(f"  ✓ Found album art")
            else:
                print(f"  ⚠ No album art found")
    
    # Repair based on file type
    success = False
    suffix = file_path.suffix.lower()
    
    if suffix == '.mp3':
        success = repair_mp3_metadata(file_path, metadata, album_metadata, album_art)
    elif suffix == '.flac':
        success = repair_flac_metadata(file_path, metadata, album_metadata, album_art)
    elif suffix in ('.ogg', '.opus'):
        success = repair_ogg_metadata(file_path, metadata, album_metadata, album_art)
    elif suffix in ('.m4a', '.mp4'):
        success = repair_mp4_metadata(file_path, metadata, album_metadata, album_art)
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

