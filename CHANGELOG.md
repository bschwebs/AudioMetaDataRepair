# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.0.0] - 2024-12-XX

### Added
- Native Windows desktop application (`app_desktop.py`)
- Music library management with custom nicknames
- Report generation (Text, HTML, CSV formats)
- Retry failed albums dialog with MusicBrainz ID management
- Batch search for MusicBrainz IDs
- Filename fixing feature
- Real-time progress tracking in desktop app
- Comprehensive results display

### Changed
- Improved album art download tracking with MusicBrainz ID storage
- Enhanced error handling and user feedback
- Better UI/UX with modern interface design

### Removed
- Flask web application (`app.py` and related files)
- Web-based templates and static files

### Fixed
- Improved filename parsing reliability
- Better handling of edge cases in metadata extraction
- Enhanced error messages for troubleshooting

## [1.0.0] - Initial Release

### Added
- Command-line tool for metadata repair
- Filename-based metadata extraction
- Album art download from MusicBrainz
- Support for `album.nfo` files
- JSON logging system
- MP3 and FLAC file support
- ID3 and Vorbis comment support

[2.0.0]: https://github.com/bschwebs/AudioMetaDataRepair/releases/tag/v2.0.0
[1.0.0]: https://github.com/bschwebs/AudioMetaDataRepair/releases/tag/v1.0.0

