#!/usr/bin/env python3
"""
Audio Metadata Repair Tool - Windows Desktop Application
Desktop GUI for repairing metadata for MP3 and FLAC files.
"""

# Standard library imports
import json
import sys
import time
from datetime import datetime
from pathlib import Path

# Third-party imports
from mutagen.flac import FLAC
from mutagen.mp3 import MP3
from PySide6.QtCore import Qt, QThread, Signal, QTimer
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QApplication, QComboBox, QDialog, QFileDialog, QGroupBox,
    QHeaderView, QHBoxLayout, QInputDialog, QLabel, QLineEdit,
    QMainWindow, QMessageBox, QProgressBar, QPushButton, QCheckBox,
    QTableWidget, QTableWidgetItem, QTextEdit, QVBoxLayout, QWidget
)

# Local imports
from utils import (
    audio_repair,
    generate_csv_report,
    generate_html_report,
    generate_text_report,
)

# Constants
LOGS_DIR = Path('logs')
LOGS_DIR.mkdir(exist_ok=True)
DEFAULT_LOG_FILE = LOGS_DIR / 'metadata_repair_log.json'
LIBRARIES_CONFIG_FILE = Path('music_libraries.json')


class ProcessingThread(QThread):
    """Thread for processing audio files in the background."""
    
    progress_updated = Signal(int, str)  # progress percentage, current file
    finished = Signal(dict)  # results dictionary
    error_occurred = Signal(str)  # error message
    
    def __init__(self, target_dir, options):
        super().__init__()
        self.target_dir = target_dir
        self.options = options
        self.processing_results = {
            'total_files': 0,
            'success_count': 0,
            'fail_count': 0,
            'skipped_count': 0,
            'nfo_generated': 0,
            'filenames_fixed': 0
        }
    
    def run(self):
        """Process audio files."""
        try:
            if not self.target_dir.exists():
                self.error_occurred.emit(f"Directory '{self.target_dir}' does not exist!")
                return
            
            # Load processing log
            log_file = DEFAULT_LOG_FILE
            log_data = audio_repair.load_log(log_file)
            
            # Find all supported audio files
            audio_files = []
            for ext in audio_repair.SUPPORTED_EXTENSIONS:
                audio_files.extend(self.target_dir.rglob(f'*{ext}'))
            
            if not audio_files:
                self.error_occurred.emit('No supported audio files found!')
                return
            
            total_files = len(audio_files)
            self.processing_results['total_files'] = total_files
            
            # Repair each file
            album_art_cache = {}
            album_info = {}
            
            for idx, audio_file in enumerate(sorted(audio_files)):
                progress = int((idx + 1) / total_files * 100)
                current_file = str(audio_file.relative_to(self.target_dir))
                self.progress_updated.emit(progress, current_file)
                
                was_already_processed = audio_repair.is_file_processed(audio_file, log_data)
                
                # Fix filename if requested and file doesn't match format
                if self.options.get('fix_filenames', False):
                    filename_metadata = audio_repair.parse_filename(audio_file.name)
                    if not filename_metadata or not filename_metadata.get('album'):
                        # Try to get metadata from file tags or album.nfo
                        album_nfo_path = audio_file.parent / 'album.nfo'
                        album_metadata = None
                        if album_nfo_path.exists():
                            album_metadata = audio_repair.parse_album_nfo(album_nfo_path)
                        
                        # Get metadata from file tags if needed
                        file_metadata = {}
                        suffix = audio_file.suffix.lower()
                        try:
                            if suffix == '.mp3':
                                mp3_file = MP3(str(audio_file))
                                file_metadata = {
                                    'artist': mp3_file.get('TPE1', [''])[0] or mp3_file.get('TPE2', [''])[0],
                                    'album': mp3_file.get('TALB', [''])[0],
                                    'title': mp3_file.get('TIT2', [''])[0],
                                    'tracknumber': int(mp3_file.get('TRCK', ['0'])[0].split('/')[0]) if mp3_file.get('TRCK') else 0
                                }
                            elif suffix == '.flac':
                                flac_file = FLAC(str(audio_file))
                                file_metadata = {
                                    'artist': flac_file.get('ARTIST', [''])[0] or flac_file.get('ALBUMARTIST', [''])[0],
                                    'album': flac_file.get('ALBUM', [''])[0],
                                    'title': flac_file.get('TITLE', [''])[0],
                                    'tracknumber': int(flac_file.get('TRACKNUMBER', ['0'])[0].split('/')[0]) if flac_file.get('TRACKNUMBER') else 0
                                }
                            elif suffix in ('.ogg', '.opus'):
                                from mutagen import File as MutagenFile
                                ogg_file = MutagenFile(str(audio_file))
                                if ogg_file:
                                    file_metadata = {
                                        'artist': ogg_file.get('ARTIST', [''])[0] or ogg_file.get('ALBUMARTIST', [''])[0],
                                        'album': ogg_file.get('ALBUM', [''])[0],
                                        'title': ogg_file.get('TITLE', [''])[0],
                                        'tracknumber': int(ogg_file.get('TRACKNUMBER', ['0'])[0].split('/')[0]) if ogg_file.get('TRACKNUMBER') else 0
                                    }
                            elif suffix in ('.m4a', '.mp4'):
                                from mutagen.mp4 import MP4
                                m4a_file = MP4(str(audio_file))
                                file_metadata = {
                                    'artist': m4a_file.get('\xa9ART', [''])[0] or m4a_file.get('aART', [''])[0],
                                    'album': m4a_file.get('\xa9alb', [''])[0],
                                    'title': m4a_file.get('\xa9nam', [''])[0],
                                    'tracknumber': m4a_file.get('trkn', [(0, 0)])[0][0] if m4a_file.get('trkn') else 0
                                }
                        except:
                            pass
                        
                        # Try to fix filename
                        if audio_repair.fix_filename(audio_file, file_metadata, album_metadata):
                            # File was renamed, need to find the new path
                            # The fix_filename function renames the file, so we need to reconstruct the new name
                            artist = file_metadata.get('artist', '') or (album_metadata.get('artist', '') if album_metadata else '')
                            album = file_metadata.get('album', '') or (album_metadata.get('album', '') if album_metadata else '')
                            track_num = file_metadata.get('tracknumber', 0)
                            title = file_metadata.get('title', '')
                            
                            if artist and album and track_num and title:
                                # Clean filename (same logic as fix_filename)
                                def clean_filename(s: str) -> str:
                                    invalid_chars = '<>:"/\\|?*'
                                    for char in invalid_chars:
                                        s = s.replace(char, '')
                                    s = ' '.join(s.split())
                                    return s.strip()
                                
                                artist = clean_filename(artist)
                                album = clean_filename(album)
                                title = clean_filename(title)
                                new_name = f"{artist} - {album} - {track_num:02d} - {title}{audio_file.suffix}"
                                audio_file = audio_file.parent / new_name
                                self.processing_results['filenames_fixed'] = self.processing_results.get('filenames_fixed', 0) + 1
                
                # Process based on options
                if self.options.get('repair_metadata', True):
                    art_cache = album_art_cache if self.options.get('download_art', True) else {}
                    result, metadata = audio_repair.repair_audio_file(
                        audio_file, 
                        self.target_dir, 
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
                        
                        # Download and embed art if requested
                        if artist and album and self.options.get('download_art', True):
                            album_key = f"{artist}||{album}"
                            if album_key not in album_art_cache:
                                album_art, _ = audio_repair.get_album_art(artist, album)
                                album_art_cache[album_key] = album_art
                                if album_art:
                                    suffix = audio_file.suffix.lower()
                                    if suffix == '.mp3':
                                        audio_repair.embed_album_art_mp3(audio_file, album_art)
                                    elif suffix == '.flac':
                                        audio_repair.embed_album_art_flac(audio_file, album_art)
                                    elif suffix in ('.ogg', '.opus'):
                                        audio_repair.embed_album_art_ogg(audio_file, album_art)
                                    elif suffix in ('.m4a', '.mp4'):
                                        audio_repair.embed_album_art_mp4(audio_file, album_art)
                                time.sleep(0.5)
                            else:
                                album_art = album_art_cache[album_key]
                                if album_art:
                                    suffix = audio_file.suffix.lower()
                                    if suffix == '.mp3':
                                        audio_repair.embed_album_art_mp3(audio_file, album_art)
                                    elif suffix == '.flac':
                                        audio_repair.embed_album_art_flac(audio_file, album_art)
                                    elif suffix in ('.ogg', '.opus'):
                                        audio_repair.embed_album_art_ogg(audio_file, album_art)
                                    elif suffix in ('.m4a', '.mp4'):
                                        audio_repair.embed_album_art_mp4(audio_file, album_art)
                        
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
                        self.processing_results['skipped_count'] += 1
                    else:
                        self.processing_results['success_count'] += 1
                    
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
                    self.processing_results['fail_count'] += 1
            
            # Generate album.nfo files if enabled
            if self.options.get('generate_nfo', True):
                nfo_generated = 0
                for album_dir, info in album_info.items():
                    nfo_path = album_dir / 'album.nfo'
                    if not nfo_path.exists():
                        if audio_repair.generate_album_nfo(nfo_path, info['metadata'], info['tracks']):
                            nfo_generated += 1
                self.processing_results['nfo_generated'] = nfo_generated
            
            # Final log save
            if self.options.get('repair_metadata', True):
                audio_repair.save_log(log_data, log_file)
            
            self.finished.emit(self.processing_results)
            
        except Exception as e:
            self.error_occurred.emit(str(e))


class MainWindow(QMainWindow):
    """Main application window."""
    
    def __init__(self):
        super().__init__()
        self.processing_thread = None
        self.libraries = {}  # Dictionary: nickname -> path
        self.init_ui()
    
    def init_ui(self):
        """Initialize the user interface."""
        self.setWindowTitle('Audio Metadata Repair Tool')
        self.setGeometry(100, 100, 800, 700)
        
        # Central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        layout.setSpacing(20)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # Header
        header = QLabel('🎵 Audio Metadata Repair Tool')
        header_font = QFont()
        header_font.setPointSize(18)
        header_font.setBold(True)
        header.setFont(header_font)
        header.setAlignment(Qt.AlignCenter)
        layout.addWidget(header)
        
        subtitle = QLabel('Repair metadata, download album art, and generate NFO files for your music collection')
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setStyleSheet('color: #666;')
        layout.addWidget(subtitle)
        
        # Music Library selection
        lib_group = QGroupBox('Music Library')
        lib_layout = QVBoxLayout()
        
        # Library selector
        lib_selector_layout = QHBoxLayout()
        lib_label = QLabel('Library:')
        self.library_combo = QComboBox()
        self.library_combo.setEditable(False)
        self.library_combo.currentIndexChanged.connect(self.on_library_selected)
        lib_selector_layout.addWidget(lib_label)
        lib_selector_layout.addWidget(self.library_combo, 1)
        
        manage_libs_btn = QPushButton('Manage Libraries...')
        manage_libs_btn.clicked.connect(self.manage_libraries)
        lib_selector_layout.addWidget(manage_libs_btn)
        lib_layout.addLayout(lib_selector_layout)
        
        # Directory input (for manual entry or when no library selected)
        dir_input_layout = QHBoxLayout()
        dir_label = QLabel('Path:')
        self.dir_input = QLineEdit()
        self.dir_input.setPlaceholderText('e.g., Z:\\Audio\\Music')
        browse_btn = QPushButton('Browse...')
        browse_btn.clicked.connect(self.browse_directory)
        dir_input_layout.addWidget(dir_label)
        dir_input_layout.addWidget(self.dir_input, 1)
        dir_input_layout.addWidget(browse_btn)
        lib_layout.addLayout(dir_input_layout)
        
        dir_hint = QLabel('Select a saved library or enter/browse a directory path')
        dir_hint.setStyleSheet('color: #666; font-size: 10pt;')
        lib_layout.addWidget(dir_hint)
        
        lib_group.setLayout(lib_layout)
        layout.addWidget(lib_group)
        
        # Load saved libraries
        self.libraries = self.load_libraries()
        self.update_library_combo()
        
        # Options
        options_group = QGroupBox('Processing Options')
        options_layout = QVBoxLayout()
        
        self.repair_metadata_cb = QCheckBox('Repair Metadata')
        self.repair_metadata_cb.setChecked(True)
        self.repair_metadata_cb.setToolTip('Update ID3 tags and Vorbis comments from filenames')
        options_layout.addWidget(self.repair_metadata_cb)
        
        self.download_art_cb = QCheckBox('Download Album Art')
        self.download_art_cb.setChecked(True)
        self.download_art_cb.setToolTip('Download and embed album covers from MusicBrainz')
        options_layout.addWidget(self.download_art_cb)
        
        self.generate_nfo_cb = QCheckBox('Generate NFO Files')
        self.generate_nfo_cb.setChecked(True)
        self.generate_nfo_cb.setToolTip('Create album.nfo files for albums without one')
        options_layout.addWidget(self.generate_nfo_cb)
        
        self.fix_filenames_cb = QCheckBox('Fix Filenames')
        self.fix_filenames_cb.setChecked(False)
        self.fix_filenames_cb.setToolTip('Rename files to match format: Artist - Album - TrackNumber - Title.ext')
        options_layout.addWidget(self.fix_filenames_cb)
        
        options_group.setLayout(options_layout)
        layout.addWidget(options_group)
        
        # Buttons layout
        buttons_layout = QHBoxLayout()
        
        self.start_btn = QPushButton('Start Processing')
        self.start_btn.setStyleSheet('''
            QPushButton {
                background-color: #667eea;
                color: white;
                font-size: 14pt;
                font-weight: bold;
                padding: 15px;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #5568d3;
            }
            QPushButton:disabled {
                background-color: #ccc;
            }
        ''')
        self.start_btn.clicked.connect(self.start_processing)
        buttons_layout.addWidget(self.start_btn)
        
        self.report_btn = QPushButton('Generate Report')
        self.report_btn.setStyleSheet('''
            QPushButton {
                background-color: #6c757d;
                color: white;
                font-size: 12pt;
                font-weight: bold;
                padding: 15px;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #5a6268;
            }
        ''')
        self.report_btn.clicked.connect(self.show_report_dialog)
        buttons_layout.addWidget(self.report_btn)
        
        self.retry_art_btn = QPushButton('Retry Failed Albums')
        self.retry_art_btn.setStyleSheet('''
            QPushButton {
                background-color: #17a2b8;
                color: white;
                font-size: 12pt;
                font-weight: bold;
                padding: 15px;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #138496;
            }
        ''')
        self.retry_art_btn.clicked.connect(self.show_retry_dialog)
        buttons_layout.addWidget(self.retry_art_btn)
        
        layout.addLayout(buttons_layout)
        
        # Progress section
        progress_group = QGroupBox('Progress')
        progress_layout = QVBoxLayout()
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(100)
        self.progress_bar.setValue(0)
        progress_layout.addWidget(self.progress_bar)
        
        self.current_file_label = QLabel('Ready to process...')
        self.current_file_label.setStyleSheet('color: #666; font-style: italic;')
        progress_layout.addWidget(self.current_file_label)
        
        progress_group.setLayout(progress_layout)
        layout.addWidget(progress_group)
        
        # Results section
        results_group = QGroupBox('Results')
        results_layout = QVBoxLayout()
        
        self.results_text = QTextEdit()
        self.results_text.setReadOnly(True)
        self.results_text.setMaximumHeight(200)
        results_layout.addWidget(self.results_text)
        
        results_group.setLayout(results_layout)
        layout.addWidget(results_group)
        
        # Status bar
        self.statusBar().showMessage('Ready')
    
    def load_libraries(self) -> dict:
        """Load saved libraries from config file."""
        if LIBRARIES_CONFIG_FILE.exists():
            try:
                with open(LIBRARIES_CONFIG_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                QMessageBox.warning(self, 'Error', f'Could not load libraries: {e}')
        return {}
    
    def save_libraries(self):
        """Save libraries to config file."""
        try:
            with open(LIBRARIES_CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.libraries, f, indent=2, ensure_ascii=False)
        except Exception as e:
            QMessageBox.warning(self, 'Error', f'Could not save libraries: {e}')
    
    def update_library_combo(self):
        """Update the library combo box with current libraries."""
        self.library_combo.clear()
        self.library_combo.addItem('-- Select Library --', '')
        for nickname, path in sorted(self.libraries.items()):
            self.library_combo.addItem(f"{nickname} ({path})", path)
    
    def on_library_selected(self, index):
        """Handle library selection from combo box."""
        if index > 0:  # Skip the "-- Select Library --" item
            path = self.library_combo.itemData(index)
            if path:
                self.dir_input.setText(path)
    
    def manage_libraries(self):
        """Open library management dialog."""
        dialog = LibraryManagerDialog(self, self.libraries)
        if dialog.exec():
            self.libraries = dialog.libraries
            self.save_libraries()
            self.update_library_combo()
    
    def browse_directory(self):
        """Open directory selection dialog."""
        # Start from current directory if set, otherwise home
        start_dir = self.dir_input.text().strip() or str(Path.home())
        directory = QFileDialog.getExistingDirectory(
            self,
            'Select Music Directory',
            start_dir,
            QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks
        )
        if directory:
            self.dir_input.setText(directory)
            # Clear library selection if manually browsing
            self.library_combo.setCurrentIndex(0)
    
    def start_processing(self):
        """Start processing audio files."""
        target_dir = self.dir_input.text().strip()
        
        if not target_dir:
            QMessageBox.warning(self, 'Error', 'Please select or enter a target directory.')
            return
        
        target_path = Path(target_dir)
        if not target_path.exists():
            QMessageBox.warning(self, 'Error', f"Directory '{target_dir}' does not exist!")
            return
        
        # Disable start button
        self.start_btn.setEnabled(False)
        self.start_btn.setText('Processing...')
        
        # Clear previous results
        self.results_text.clear()
        self.progress_bar.setValue(0)
        self.current_file_label.setText('Initializing...')
        self.statusBar().showMessage('Processing...')
        
        # Get options
        options = {
            'repair_metadata': self.repair_metadata_cb.isChecked(),
            'download_art': self.download_art_cb.isChecked(),
            'generate_nfo': self.generate_nfo_cb.isChecked(),
            'fix_filenames': self.fix_filenames_cb.isChecked()
        }
        
        # Start processing thread
        self.processing_thread = ProcessingThread(target_path, options)
        self.processing_thread.progress_updated.connect(self.update_progress)
        self.processing_thread.finished.connect(self.processing_finished)
        self.processing_thread.error_occurred.connect(self.processing_error)
        self.processing_thread.start()
    
    def update_progress(self, progress, current_file):
        """Update progress bar and current file label."""
        self.progress_bar.setValue(progress)
        self.current_file_label.setText(f'Processing: {current_file}')
        self.statusBar().showMessage(f'Processing... {progress}%')
    
    def processing_finished(self, results):
        """Handle processing completion."""
        self.progress_bar.setValue(100)
        self.current_file_label.setText('Processing complete!')
        self.start_btn.setEnabled(True)
        self.start_btn.setText('Start Processing')
        self.statusBar().showMessage('Processing complete')
        
        # Display results
        results_text = f"""
═══════════════════════════════════════════════════════
Processing Complete!
═══════════════════════════════════════════════════════

Total Files:        {results['total_files']}
Successfully Processed: {results['success_count']}
Skipped:            {results['skipped_count']}
Failed:             {results['fail_count']}
NFO Files Generated: {results.get('nfo_generated', 0)}
Filenames Fixed:    {results.get('filenames_fixed', 0)}

═══════════════════════════════════════════════════════
"""
        self.results_text.setPlainText(results_text)
        
        QMessageBox.information(
            self,
            'Processing Complete',
            f"Processing finished!\n\n"
            f"Total: {results['total_files']}\n"
            f"Success: {results['success_count']}\n"
            f"Skipped: {results['skipped_count']}\n"
            f"Failed: {results['fail_count']}\n"
            f"NFO Generated: {results['nfo_generated']}"
        )
    
    def processing_error(self, error_message):
        """Handle processing error."""
        self.start_btn.setEnabled(True)
        self.start_btn.setText('Start Processing')
        self.statusBar().showMessage('Error occurred')
        self.current_file_label.setText('Error occurred')
        
        QMessageBox.critical(self, 'Processing Error', f'An error occurred:\n\n{error_message}')
    
    def show_report_dialog(self):
        """Show report generation dialog."""
        dialog = ReportDialog(self)
        dialog.exec()
    
    def show_retry_dialog(self):
        """Show retry failed albums dialog."""
        dialog = RetryAlbumArtDialog(self)
        dialog.exec()


class ReportDialog(QDialog):
    """Dialog for generating and viewing reports."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Generate Report')
        self.setGeometry(200, 200, 700, 600)
        self.init_ui()
        self.load_log_data()
    
    def init_ui(self):
        """Initialize the dialog UI."""
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # Title
        title = QLabel('Generate Processing Report')
        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)
        title.setFont(title_font)
        layout.addWidget(title)
        
        # Report format selection
        format_group = QGroupBox('Report Format')
        format_layout = QVBoxLayout()
        
        self.format_combo = QComboBox()
        self.format_combo.addItems(['Text Report (.txt)', 'HTML Report (.html)', 'CSV Report (.csv)'])
        self.format_combo.currentIndexChanged.connect(self.generate_preview)
        format_layout.addWidget(self.format_combo)
        
        format_group.setLayout(format_layout)
        layout.addWidget(format_group)
        
        # Preview area
        preview_group = QGroupBox('Report Preview')
        preview_layout = QVBoxLayout()
        
        self.preview_text = QTextEdit()
        self.preview_text.setReadOnly(True)
        self.preview_text.setMinimumHeight(300)
        preview_layout.addWidget(self.preview_text)
        
        preview_group.setLayout(preview_layout)
        layout.addWidget(preview_group)
        
        # Buttons
        buttons_layout = QHBoxLayout()
        
        self.generate_preview_btn = QPushButton('Generate Preview')
        self.generate_preview_btn.clicked.connect(self.generate_preview)
        buttons_layout.addWidget(self.generate_preview_btn)
        
        self.export_btn = QPushButton('Export Report...')
        self.export_btn.clicked.connect(self.export_report)
        self.export_btn.setEnabled(False)
        buttons_layout.addWidget(self.export_btn)
        
        close_btn = QPushButton('Close')
        close_btn.clicked.connect(self.accept)
        buttons_layout.addWidget(close_btn)
        
        layout.addLayout(buttons_layout)
        
        # Generate initial preview
        QTimer.singleShot(100, self.generate_preview)
    
    def load_log_data(self):
        """Load log data from file."""
        log_file = DEFAULT_LOG_FILE
        if log_file.exists():
            try:
                with open(log_file, 'r', encoding='utf-8') as f:
                    self.log_data = json.load(f)
            except Exception as e:
                QMessageBox.warning(self, 'Error', f'Could not load log file: {e}')
                self.log_data = {'processed_files': {}, 'album_art': {}}
        else:
            self.log_data = {'processed_files': {}, 'album_art': {}}
            QMessageBox.information(self, 'No Log File', 'No log file found. Process some files first to generate a report.')
    
    def generate_preview(self):
        """Generate preview of the report."""
        if not self.log_data:
            self.preview_text.setPlainText('No log data available.')
            return
        
        format_index = self.format_combo.currentIndex()
        
        if format_index == 0:  # Text
            report = generate_text_report(self.log_data)
            self.preview_text.setPlainText(report)
            self.current_format = 'text'
        elif format_index == 1:  # HTML
            report = generate_html_report(self.log_data)
            self.preview_text.setHtml(report)
            self.current_format = 'html'
        else:  # CSV
            # For CSV, show a sample
            processed_files = self.log_data.get('processed_files', {})
            sample = "CSV Report Preview (first 10 rows):\n\n"
            sample += "File Path,Last Processed,Has Album Art,File Modified Time\n"
            for file_path, file_info in list(processed_files.items())[:10]:
                sample += f"{file_path},{file_info.get('last_processed', '')},"
                sample += f"{'Yes' if file_info.get('has_art', False) else 'No'},"
                sample += f"{file_info.get('file_mtime', '')}\n"
            if len(processed_files) > 10:
                sample += f"\n... and {len(processed_files) - 10} more rows"
            self.preview_text.setPlainText(sample)
            self.current_format = 'csv'
        
        self.export_btn.setEnabled(True)
    
    def export_report(self):
        """Export report to file."""
        format_index = self.format_combo.currentIndex()
        
        if format_index == 0:  # Text
            file_filter = "Text Files (*.txt);;All Files (*.*)"
            default_name = f"metadata_repair_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        elif format_index == 1:  # HTML
            file_filter = "HTML Files (*.html);;All Files (*.*)"
            default_name = f"metadata_repair_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
        else:  # CSV
            file_filter = "CSV Files (*.csv);;All Files (*.*)"
            default_name = f"metadata_repair_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            'Save Report',
            str(Path.home() / default_name),
            file_filter
        )
        
        if file_path:
            try:
                if format_index == 0:  # Text
                    report = generate_text_report(self.log_data)
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write(report)
                elif format_index == 1:  # HTML
                    report = generate_html_report(self.log_data)
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write(report)
                else:  # CSV
                    generate_csv_report(self.log_data, Path(file_path))
                
                QMessageBox.information(self, 'Success', f'Report saved to:\n{file_path}')
            except Exception as e:
                QMessageBox.critical(self, 'Error', f'Could not save report:\n{e}')


class RetryAlbumArtDialog(QDialog):
    """Dialog for retrying failed album art downloads with MusicBrainz IDs."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Retry Failed Album Art Downloads')
        self.setGeometry(200, 200, 900, 600)
        self.log_data = None
        self.log_file = DEFAULT_LOG_FILE
        self.init_ui()
        self.load_failed_albums()
    
    def init_ui(self):
        """Initialize the dialog UI."""
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # Title
        title = QLabel('Retry Failed Album Art Downloads')
        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)
        title.setFont(title_font)
        layout.addWidget(title)
        
        info_label = QLabel('Albums that failed to download art. You can search for MusicBrainz IDs or enter them manually to retry.')
        info_label.setWordWrap(True)
        info_label.setStyleSheet('color: #666;')
        layout.addWidget(info_label)
        
        # Table for failed albums
        table_group = QGroupBox('Failed Albums')
        table_layout = QVBoxLayout()
        
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(['Artist', 'Album', 'MusicBrainz ID', 'Last Attempted', 'Actions'])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        table_layout.addWidget(self.table)
        
        table_group.setLayout(table_layout)
        layout.addWidget(table_group)
        
        # Buttons
        buttons_layout = QHBoxLayout()
        
        search_btn = QPushButton('Search Selected')
        search_btn.clicked.connect(self.search_selected_album)
        buttons_layout.addWidget(search_btn)
        
        batch_search_btn = QPushButton('Batch Search All')
        batch_search_btn.clicked.connect(self.batch_search_all)
        batch_search_btn.setStyleSheet('background-color: #17a2b8; color: white; font-weight: bold;')
        buttons_layout.addWidget(batch_search_btn)
        
        retry_btn = QPushButton('Retry Selected')
        retry_btn.clicked.connect(self.retry_selected)
        retry_btn.setStyleSheet('background-color: #28a745; color: white; font-weight: bold;')
        buttons_layout.addWidget(retry_btn)
        
        refresh_btn = QPushButton('Refresh List')
        refresh_btn.clicked.connect(self.load_failed_albums)
        buttons_layout.addWidget(refresh_btn)
        
        close_btn = QPushButton('Close')
        close_btn.clicked.connect(self.accept)
        buttons_layout.addWidget(close_btn)
        
        layout.addLayout(buttons_layout)
    
    def load_failed_albums(self):
        """Load and display failed albums."""
        # Load log data
        if self.log_file.exists():
            try:
                with open(self.log_file, 'r', encoding='utf-8') as f:
                    self.log_data = json.load(f)
            except Exception as e:
                QMessageBox.warning(self, 'Error', f'Could not load log file: {e}')
                self.log_data = {'processed_files': {}, 'album_art': {}}
        else:
            self.log_data = {'processed_files': {}, 'album_art': {}}
            QMessageBox.information(self, 'No Log File', 'No log file found.')
            return
        
        failed_albums = audio_repair.get_failed_albums(self.log_data)
        
        self.table.setRowCount(len(failed_albums))
        
        for row, album in enumerate(failed_albums):
            # Artist
            self.table.setItem(row, 0, QTableWidgetItem(album['artist']))
            
            # Album
            self.table.setItem(row, 1, QTableWidgetItem(album['album']))
            
            # MusicBrainz ID
            mb_id_item = QTableWidgetItem(album['musicbrainz_id'] or 'Not found')
            if not album['musicbrainz_id']:
                mb_id_item.setForeground(Qt.red)
            self.table.setItem(row, 2, mb_id_item)
            
            # Last attempted
            last_attempted = album['last_attempted']
            if last_attempted:
                try:
                    dt = datetime.fromisoformat(last_attempted)
                    last_attempted = dt.strftime('%Y-%m-%d %H:%M:%S')
                except:
                    pass
            self.table.setItem(row, 3, QTableWidgetItem(last_attempted or 'Unknown'))
            
            # Actions button
            action_btn = QPushButton('Edit ID')
            action_btn.clicked.connect(lambda checked, r=row: self.edit_mb_id(r))
            self.table.setCellWidget(row, 4, action_btn)
    
    def edit_mb_id(self, row):
        """Edit MusicBrainz ID for a specific album."""
        artist = self.table.item(row, 0).text()
        album = self.table.item(row, 1).text()
        current_id = self.table.item(row, 2).text()
        
        if current_id == 'Not found':
            current_id = ''
        
        mb_id, ok = QInputDialog.getText(
            self,
            'Edit MusicBrainz ID',
            f'Enter MusicBrainz Release Group ID for:\n{artist} - {album}',
            text=current_id
        )
        
        if ok and mb_id.strip():
            self.table.item(row, 2).setText(mb_id.strip())
            if mb_id.strip():
                self.table.item(row, 2).setForeground(Qt.black)
    
    def search_selected_album(self):
        """Search for MusicBrainz ID for selected album."""
        current_row = self.table.currentRow()
        if current_row < 0:
            QMessageBox.information(self, 'No Selection', 'Please select an album from the table.')
            return
        
        artist = self.table.item(current_row, 0).text()
        album = self.table.item(current_row, 1).text()
        
        # Show progress
        self.table.item(current_row, 2).setText('Searching...')
        self.table.item(current_row, 2).setForeground(Qt.blue)
        QApplication.processEvents()
        
        mb_id = audio_repair.search_musicbrainz_release_group(artist, album)
        
        if mb_id:
            self.table.item(current_row, 2).setText(mb_id)
            self.table.item(current_row, 2).setForeground(Qt.black)
            # Update log data
            album_key = f"{artist}||{album}"
            if 'album_art' not in self.log_data:
                self.log_data['album_art'] = {}
            if album_key not in self.log_data['album_art']:
                self.log_data['album_art'][album_key] = {}
            self.log_data['album_art'][album_key]['musicbrainz_release_group_id'] = mb_id
            audio_repair.save_log(self.log_data, self.log_file)
        else:
            self.table.item(current_row, 2).setText('Not found')
            self.table.item(current_row, 2).setForeground(Qt.red)
    
    def batch_search_all(self):
        """Batch search for MusicBrainz IDs for all albums without IDs."""
        failed_albums = audio_repair.get_failed_albums(self.log_data)
        albums_without_id = [a for a in failed_albums if not a.get('musicbrainz_id')]
        
        if not albums_without_id:
            QMessageBox.information(self, 'No Albums', 'All albums already have MusicBrainz IDs.')
            return
        
        reply = QMessageBox.question(
            self,
            'Batch Search',
            f'Search for MusicBrainz IDs for {len(albums_without_id)} album(s)?\n\nThis may take a while.',
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply != QMessageBox.Yes:
            return
        
        # Update table with progress
        def progress_callback(album_key, mb_id):
            # Find row and update
            for row in range(self.table.rowCount()):
                artist = self.table.item(row, 0).text()
                album = self.table.item(row, 1).text()
                if f"{artist}||{album}" == album_key:
                    if mb_id:
                        self.table.item(row, 2).setText(mb_id)
                        self.table.item(row, 2).setForeground(Qt.black)
                    else:
                        self.table.item(row, 2).setText('Not found')
                        self.table.item(row, 2).setForeground(Qt.red)
                    QApplication.processEvents()
                    break
        
        results = audio_repair.batch_search_musicbrainz_ids(albums_without_id, progress_callback)
        
        # Update log data
        for album_key, mb_id in results.items():
            if mb_id:
                if 'album_art' not in self.log_data:
                    self.log_data['album_art'] = {}
                if album_key not in self.log_data['album_art']:
                    self.log_data['album_art'][album_key] = {}
                self.log_data['album_art'][album_key]['musicbrainz_release_group_id'] = mb_id
        
        audio_repair.save_log(self.log_data, self.log_file)
        
        found_count = sum(1 for mb_id in results.values() if mb_id)
        QMessageBox.information(
            self,
            'Batch Search Complete',
            f'Search completed.\n\nFound: {found_count}\nNot found: {len(results) - found_count}'
        )
    
    def retry_selected(self):
        """Retry downloading art for selected albums."""
        selected_rows = set()
        for item in self.table.selectedItems():
            selected_rows.add(item.row())
        
        if not selected_rows:
            QMessageBox.information(self, 'No Selection', 'Please select one or more albums to retry.')
            return
        
        retry_count = 0
        success_count = 0
        
        for row in selected_rows:
            artist = self.table.item(row, 0).text()
            album = self.table.item(row, 1).text()
            mb_id = self.table.item(row, 2).text()
            
            if not mb_id or mb_id == 'Not found':
                QMessageBox.warning(self, 'Missing ID', f'Please provide a MusicBrainz ID for:\n{artist} - {album}')
                continue
            
            retry_count += 1
            success, art_data = audio_repair.retry_album_art_with_id(
                artist, album, mb_id, self.log_data, self.log_file
            )
            
            if success:
                success_count += 1
                # Update the row to show success
                self.table.item(row, 2).setForeground(Qt.green)
                # Embed art in files if we have them
                # Note: This would require finding the files, which we don't track here
                # For now, just mark as successful
        
        # Reload the list to reflect changes
        self.load_failed_albums()
        
        QMessageBox.information(
            self,
            'Retry Complete',
            f'Retried {retry_count} album(s).\n{success_count} successful, {retry_count - success_count} failed.'
        )


class LibraryManagerDialog(QDialog):
    """Dialog for managing music libraries."""
    
    def __init__(self, parent=None, libraries=None):
        super().__init__(parent)
        self.setWindowTitle('Manage Music Libraries')
        self.setGeometry(200, 200, 700, 500)
        self.libraries = libraries.copy() if libraries else {}
        self.init_ui()
    
    def init_ui(self):
        """Initialize the dialog UI."""
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # Title
        title = QLabel('Manage Music Libraries')
        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)
        title.setFont(title_font)
        layout.addWidget(title)
        
        info_label = QLabel('Add, edit, or remove saved music library paths with custom nicknames.')
        info_label.setWordWrap(True)
        info_label.setStyleSheet('color: #666;')
        layout.addWidget(info_label)
        
        # Libraries table
        table_group = QGroupBox('Saved Libraries')
        table_layout = QVBoxLayout()
        
        self.table = QTableWidget()
        self.table.setColumnCount(2)
        self.table.setHorizontalHeaderLabels(['Nickname', 'Path'])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        table_layout.addWidget(self.table)
        
        table_group.setLayout(table_layout)
        layout.addWidget(table_group)
        
        # Buttons
        buttons_layout = QHBoxLayout()
        
        add_btn = QPushButton('Add Library')
        add_btn.clicked.connect(self.add_library)
        buttons_layout.addWidget(add_btn)
        
        edit_btn = QPushButton('Edit Selected')
        edit_btn.clicked.connect(self.edit_library)
        buttons_layout.addWidget(edit_btn)
        
        delete_btn = QPushButton('Delete Selected')
        delete_btn.setStyleSheet('background-color: #dc3545; color: white;')
        delete_btn.clicked.connect(self.delete_library)
        buttons_layout.addWidget(delete_btn)
        
        buttons_layout.addStretch()
        
        close_btn = QPushButton('Close')
        close_btn.clicked.connect(self.accept)
        buttons_layout.addWidget(close_btn)
        
        layout.addLayout(buttons_layout)
        
        # Load libraries into table
        self.load_libraries_table()
    
    def load_libraries_table(self):
        """Load libraries into the table."""
        self.table.setRowCount(len(self.libraries))
        
        for row, (nickname, path) in enumerate(sorted(self.libraries.items())):
            self.table.setItem(row, 0, QTableWidgetItem(nickname))
            self.table.setItem(row, 1, QTableWidgetItem(path))
    
    def add_library(self):
        """Add a new library."""
        nickname, ok1 = QInputDialog.getText(
            self,
            'Add Library',
            'Enter a nickname for this library:',
            text=''
        )
        
        if not ok1 or not nickname.strip():
            return
        
        nickname = nickname.strip()
        
        # Check if nickname already exists
        if nickname in self.libraries:
            QMessageBox.warning(self, 'Duplicate', f'Library "{nickname}" already exists!')
            return
        
        # Get directory path
        directory = QFileDialog.getExistingDirectory(
            self,
            'Select Music Directory',
            str(Path.home()),
            QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks
        )
        
        if directory:
            self.libraries[nickname] = directory
            self.load_libraries_table()
    
    def edit_library(self):
        """Edit selected library."""
        current_row = self.table.currentRow()
        if current_row < 0:
            QMessageBox.information(self, 'No Selection', 'Please select a library to edit.')
            return
        
        old_nickname = self.table.item(current_row, 0).text()
        old_path = self.table.item(current_row, 1).text()
        
        # Get new nickname
        nickname, ok1 = QInputDialog.getText(
            self,
            'Edit Library',
            'Enter a new nickname:',
            text=old_nickname
        )
        
        if not ok1 or not nickname.strip():
            return
        
        nickname = nickname.strip()
        
        # Get new path
        directory = QFileDialog.getExistingDirectory(
            self,
            'Select Music Directory',
            old_path,
            QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks
        )
        
        if directory:
            # Remove old entry if nickname changed
            if nickname != old_nickname:
                del self.libraries[old_nickname]
                # Check if new nickname already exists
                if nickname in self.libraries:
                    QMessageBox.warning(self, 'Duplicate', f'Library "{nickname}" already exists!')
                    # Restore old entry
                    self.libraries[old_nickname] = old_path
                    return
            
            self.libraries[nickname] = directory
            self.load_libraries_table()
    
    def delete_library(self):
        """Delete selected library."""
        current_row = self.table.currentRow()
        if current_row < 0:
            QMessageBox.information(self, 'No Selection', 'Please select a library to delete.')
            return
        
        nickname = self.table.item(current_row, 0).text()
        path = self.table.item(current_row, 1).text()
        
        reply = QMessageBox.question(
            self,
            'Confirm Delete',
            f'Are you sure you want to delete library "{nickname}"?\n\nPath: {path}',
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            del self.libraries[nickname]
            self.load_libraries_table()


def main():
    """Main entry point."""
    app = QApplication(sys.argv)
    app.setStyle('Fusion')  # Modern look
    
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec())


if __name__ == '__main__':
    main()

