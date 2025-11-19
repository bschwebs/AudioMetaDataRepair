"""
Audio Metadata Repair Utilities

This package contains utility functions for audio metadata repair,
including file processing, album art downloading, and report generation.
"""

from .audio_repair import (
    # Constants
    SUPPORTED_EXTENSIONS,
    DEFAULT_MIME_TYPE,
    API_TIMEOUT,
    API_RATE_LIMIT_DELAY,
    
    # Logging functions
    load_log,
    save_log,
    is_file_processed,
    mark_file_processed,
    has_album_art_downloaded,
    get_failed_albums,
    retry_album_art_with_id,
    batch_search_musicbrainz_ids,
    mark_album_art_downloaded,
    
    # Album art functions
    search_musicbrainz_release_group,
    get_album_art,
    embed_album_art_mp3,
    embed_album_art_flac,
    embed_album_art_ogg,
    embed_album_art_mp4,
    detect_mime_type,
    
    # Parsing functions
    parse_album_nfo,
    generate_album_nfo,
    parse_filename,
    fix_filename,
    
    # Repair functions
    repair_mp3_metadata,
    repair_flac_metadata,
    repair_ogg_metadata,
    repair_mp4_metadata,
    repair_audio_file,
    
    # Report generation functions
    generate_text_report,
    generate_html_report,
    generate_csv_report,
)

__all__ = [
    'SUPPORTED_EXTENSIONS',
    'DEFAULT_MIME_TYPE',
    'API_TIMEOUT',
    'API_RATE_LIMIT_DELAY',
    'load_log',
    'save_log',
    'is_file_processed',
    'mark_file_processed',
    'has_album_art_downloaded',
    'get_failed_albums',
    'retry_album_art_with_id',
    'batch_search_musicbrainz_ids',
    'mark_album_art_downloaded',
    'search_musicbrainz_release_group',
    'get_album_art',
    'embed_album_art_mp3',
    'embed_album_art_flac',
    'embed_album_art_ogg',
    'embed_album_art_mp4',
    'detect_mime_type',
    'parse_album_nfo',
    'generate_album_nfo',
    'parse_filename',
    'fix_filename',
    'repair_mp3_metadata',
    'repair_flac_metadata',
    'repair_ogg_metadata',
    'repair_mp4_metadata',
    'repair_audio_file',
    'generate_text_report',
    'generate_html_report',
    'generate_csv_report',
]

