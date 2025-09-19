# gui/dialogs/file_preview.py
"""
Enhanced file preview dialog for CSV files with instrument type detection, filtering options,
and support for both calibration and verification modes.
"""

import tkinter as tk
from tkinter import ttk, messagebox
import logging
from typing import Dict, Any, Callable, Optional, Literal
from core.data_processor import ParticleDataProcessor
from config.constants import (FONT_FILE_NAME, FONT_INSTRUMENT_TYPE, FONT_HINT_TEXT, 
                             FONT_STATUS, FONT_PREVIEW_TEXT, FONT_PROGRESS,
                             INSTRUMENT_PREVIEW_DEFAULTS, DEFAULT_PREVIEW_LINES)

logger = logging.getLogger(__name__)

class FilePreviewDialog:
    """Enhanced dialog for previewing CSV files with configurable filtering options, 
    instrument type detection, and support for both calibration and verification modes."""
    
    def __init__(self, 
                 parent, 
                 file_path: str, 
                 on_load_callback: Callable[[str, str, int], None],
                 mode: Literal['calibration', 'verification'] = 'calibration',
                 queue_context: Optional[Dict[str, Any]] = None):
        """
        Initialize the file preview dialog.
        
        Args:
            parent: Parent window
            file_path: Path to the CSV file to preview
            on_load_callback: Callback function called when user chooses to load
                             Signature: callback(file_path, tag, skip_rows)
            mode: 'calibration' for single file loading, 'verification' for queue processing
            queue_context: Optional context for verification mode (progress info, callbacks, etc.)
        """
        self.parent = parent
        self.file_path = file_path
        self.on_load_callback = on_load_callback
        self.mode = mode
        self.queue_context = queue_context or {}
        self.dialog = None
        
        # OPTIMIZED: Create single processor instance for dialog lifetime
        self.data_processor = ParticleDataProcessor()
        
        self.cached_instrument_type = None
        self.cached_file_metadata = None
        self.preview_data = None
        
        # UI variables
        self.preview_lines_var = None
        self.skip_var = None
        self.tag_var = None
        
        # UI widgets
        self.preview_text = None
        self.status_label = None
        self.instrument_type_label = None
        self.instrument_hint_label = None
        self.preview_lines_entry = None
        self.refresh_button = None
        
        # Queue-specific widgets (only for verification mode)
        self.queue_progress_frame = None
        self.queue_progress_label = None
        
    def show(self) -> None:
        """Show the preview dialog with optimized data loading."""
        try:
            self._load_file_metadata()
            
            if not self.cached_file_metadata['success']:
                messagebox.showerror(
                    "Preview Error", 
                    f"Failed to preview file:\n{self.cached_file_metadata['error']}"
                )
                return
            
            # Get optimal preview lines based on detected instrument type
            optimal_lines = self._get_optimal_preview_lines()
            
            # Load initial preview with optimal line count
            self._load_preview_content(optimal_lines)
            
            if not self.preview_data:
                messagebox.showerror("Preview Error", "Failed to load preview content")
                return
                
        except Exception as e:
            logger.error(f"Error during preview initialization: {e}")
            messagebox.showerror("Preview Error", f"Failed to initialize preview: {str(e)}")
            return
        
        self._create_dialog()
        self._create_widgets()
        self._layout_widgets()
        self._populate_initial_data()
        self._setup_event_handlers()
        
    def _load_file_metadata(self) -> None:
        """Load file metadata and detect instrument type once."""
        # Use the data processor's metadata parsing method
        self.cached_file_metadata = self.data_processor._parse_csv_metadata(self.file_path)
        
        if self.cached_file_metadata['success']:
            # Cache the detected instrument type to avoid re-detection
            self.cached_instrument_type = self.cached_file_metadata.get('instrument_type', 'Unknown')
            logger.info(f"Cached instrument type: {self.cached_instrument_type}")
        else:
            self.cached_instrument_type = 'Unknown'
            logger.warning(f"Failed to detect instrument type: {self.cached_file_metadata.get('error', 'Unknown error')}")
    
    def _get_optimal_preview_lines(self) -> int:
        """Get optimal preview lines using cached instrument type."""
        return INSTRUMENT_PREVIEW_DEFAULTS.get(self.cached_instrument_type, DEFAULT_PREVIEW_LINES)
    
    def _load_preview_content(self, num_lines: int) -> None:
        """Load preview content using cached metadata."""
        try:
            if not self.cached_file_metadata['success']:
                self.preview_data = None
                return
            
            # Use the cached encoding instead of re-detecting
            encoding = self.cached_file_metadata['encoding']
            
            # Read preview lines directly without full CSV parsing
            preview_lines = []
            with open(self.file_path, 'r', encoding=encoding) as f:
                for i, line in enumerate(f):
                    if i >= num_lines:
                        break
                    preview_lines.append(line.strip())
            
            # Construct preview data using cached metadata
            self.preview_data = {
                'success': True,
                'preview_lines': preview_lines,
                'total_lines': self.cached_file_metadata['total_lines'],
                'detected_columns': self.cached_file_metadata.get('detected_columns', len(self.cached_file_metadata.get('sample_columns', []))),
                'column_names': self.cached_file_metadata.get('sample_columns', []),
                'encoding_used': encoding,
                'instrument_type': self.cached_instrument_type
            }
            
            logger.info(f"Loaded {len(preview_lines)} preview lines using cached metadata")
            
        except Exception as e:
            logger.error(f"Error loading preview content: {e}")
            self.preview_data = {
                'success': False,
                'error': str(e),
                'instrument_type': self.cached_instrument_type or 'Unknown'
            }
        
    def _create_dialog(self) -> None:
        """Create the main dialog window with mode-aware sizing."""
        self.dialog = tk.Toplevel(self.parent)
        
        # Mode-aware dialog title and sizing
        if self.mode == 'calibration':
            self.dialog.title("CSV File Preview - Calibration Mode")
            self.dialog.geometry("950x850")
        else:  # verification mode
            self.dialog.title("CSV File Preview - Verification Queue")
            self.dialog.geometry("950x900")  # Slightly larger for queue info
        
        self.dialog.grab_set()  # Make it modal
        
        # Center the dialog
        self.dialog.transient(self.parent)
        self.dialog.update_idletasks()
        x = (self.dialog.winfo_screenwidth() // 2) - (475)
        y = (self.dialog.winfo_screenheight() // 2) - (375 if self.mode == 'calibration' else 400)
        dialog_geometry = f"950x850+{x}+{y}" if self.mode == 'calibration' else f"950x900+{x}+{y}"
        self.dialog.geometry(dialog_geometry)
        
        # Handle dialog close
        self.dialog.protocol("WM_DELETE_WINDOW", self._on_cancel)
        
    def _create_widgets(self) -> None:
        """Create all dialog widgets with mode and preview control support."""
        # Queue progress frame (only for verification mode)
        if self.mode == 'verification' and self.queue_context:
            self.queue_progress_frame = ttk.LabelFrame(self.dialog, text="Queue Progress", padding=5)
            self._create_queue_progress_widgets()
        
        # File info header
        self.info_frame = ttk.LabelFrame(self.dialog, text="Current File Information", padding=5)
        
        filename = self.file_path.split('/')[-1].split('\\')[-1]  # Handle both path separators
        self.file_label = ttk.Label(
            self.info_frame, 
            text=f"File: {filename}", 
            font=FONT_FILE_NAME
        )
        
        total_lines = self.cached_file_metadata.get('total_lines', 'Unknown') if self.cached_file_metadata else 'Unknown'
        detected_columns = len(self.cached_file_metadata.get('sample_columns', [])) if self.cached_file_metadata else 0
        
        self.lines_label = ttk.Label(
            self.info_frame, 
            text=f"Total lines: {total_lines}"
        )
        self.columns_label = ttk.Label(
            self.info_frame, 
            text=f"Detected columns: {detected_columns}"
        )
        
        #Use cached instrument type
        instrument_color = 'green' if self.cached_instrument_type != 'Unknown' else 'orange'
        
        self.instrument_type_label = ttk.Label(
            self.info_frame,
            text=f"Instrument Type: {self.cached_instrument_type}",
            font=FONT_INSTRUMENT_TYPE,
            foreground=instrument_color
        )
        
        # Instrument preview hint using cached type
        default_lines = INSTRUMENT_PREVIEW_DEFAULTS.get(self.cached_instrument_type, DEFAULT_PREVIEW_LINES)
        self.instrument_hint_label = ttk.Label(
            self.info_frame,
            text=f"Default preview for {self.cached_instrument_type}: {default_lines} lines",
            font=FONT_HINT_TEXT,
            foreground='blue'
        )
        
        # Preview controls section
        self.preview_control_frame = ttk.LabelFrame(self.dialog, text="Preview Controls", padding=5)
        self.controls_row = ttk.Frame(self.preview_control_frame)
        
        # Preview lines controls
        self.preview_lines_label = ttk.Label(self.controls_row, text="Preview lines:")
        
        # Initialize with current preview line count
        initial_lines = len(self.preview_data.get('preview_lines', [])) if self.preview_data else default_lines
        self.preview_lines_var = tk.IntVar(value=initial_lines)
        
        self.preview_lines_entry = ttk.Entry(self.controls_row, textvariable=self.preview_lines_var, width=8)
        self.refresh_button = ttk.Button(self.controls_row, text="🔄 Refresh Preview", command=self._refresh_preview)
        self.preview_hint_label = ttk.Label(self.controls_row, text="(1-1000 lines)", font=FONT_HINT_TEXT)
        
        # Status label for preview feedback
        preview_count = len(self.preview_data.get('preview_lines', [])) if self.preview_data else 0
        self.status_label = ttk.Label(
            self.controls_row, 
            text=f"✓ Showing first {preview_count} lines", 
            foreground='green', 
            font=FONT_STATUS
        )
        
        # Preview text section
        self.preview_section = ttk.LabelFrame(self.dialog, text="File Preview", padding=5)
        self.text_frame = ttk.Frame(self.preview_section)
        
        self.preview_text = tk.Text(self.text_frame, wrap='none', font=FONT_PREVIEW_TEXT)
        self.scrollbar_y = ttk.Scrollbar(self.text_frame, orient='vertical', command=self.preview_text.yview)
        self.scrollbar_x = ttk.Scrollbar(self.text_frame, orient='horizontal', command=self.preview_text.xview)
        self.preview_text.configure(yscrollcommand=self.scrollbar_y.set, xscrollcommand=self.scrollbar_x.set)
        
        # Filter controls section
        self.filter_frame = ttk.LabelFrame(self.dialog, text="Data Filtering Options", padding=10)
        self.filter_row = ttk.Frame(self.filter_frame)
        
        # Enhanced tag generation (mode-aware)
        filename = self.file_path.split('/')[-1].split('\\')[-1]
        if self.mode == 'verification' and 'auto_tag' in self.queue_context:
            default_tag = self.queue_context['auto_tag']
        else:
            default_tag = self._generate_auto_numeric_tag(filename)
        
        self.tag_label = ttk.Label(self.filter_row, text="Bead Size (μm):")
        self.tag_var = tk.StringVar(value=default_tag)
        
        # Register float validation function
        self.validate_float = self.dialog.register(self._validate_float_input)
        
        # Create tag entry with float validation
        self.tag_entry = ttk.Entry(
            self.filter_row, 
            textvariable=self.tag_var, 
            width=30,
            validate='key',
            validatecommand=(self.validate_float, '%P')
        )
        
        # Skip rows initialization (queue-aware)
        skip_default = self.preview_lines_var.get()  # Default to current preview lines
            
        self.skip_label = ttk.Label(self.filter_row, text="Skip rows from top:")
        self.skip_var = tk.IntVar(value=skip_default)
        self.skip_entry = ttk.Entry(self.filter_row, textvariable=self.skip_var, width=6)
        self.skip_hint_label = ttk.Label(
            self.filter_row, 
            text="(Use this to skip headers, metadata, or junk data)", 
            font=FONT_STATUS
        )
        
        # Mode-aware buttons section
        self.button_frame = ttk.Frame(self.dialog)
        
        if self.mode == 'calibration':
            self.load_button = ttk.Button(self.button_frame, text="📁 Load with Filter", command=self._on_load)
            self.cancel_button = ttk.Button(self.button_frame, text="❌ Cancel", command=self._on_cancel)
        else:  # verification mode
            self.load_button = ttk.Button(self.button_frame, text="📁 Load This File", command=self._on_load)
            self.skip_button = ttk.Button(self.button_frame, text="⭐️ Skip This File", command=self._on_skip)
            self.cancel_button = ttk.Button(self.button_frame, text="❌ Cancel Queue", command=self._on_cancel)
    
    def _create_queue_progress_widgets(self) -> None:
        """Create queue progress widgets for verification mode."""
        if not self.queue_context:
            return
            
        # Extract queue information
        current_index = self.queue_context.get('current_index', 0)
        total_files = self.queue_context.get('total_files', 1)
        processed_count = self.queue_context.get('processed_count', 0)
        failed_count = self.queue_context.get('failed_count', 0)
        skipped_count = self.queue_context.get('skipped_count', 0)
        
        # Build progress text
        progress_text = f"File {current_index + 1} of {total_files}"
        if processed_count > 0 or failed_count > 0 or skipped_count > 0:
            progress_text += f" | Processed: {processed_count}"
            if failed_count > 0:
                progress_text += f" | Failed: {failed_count}"
            if skipped_count > 0:
                progress_text += f" | Skipped: {skipped_count}"
        
        self.queue_progress_label = ttk.Label(
            self.queue_progress_frame, 
            text=progress_text, 
            font=FONT_PROGRESS
        )
        
    def _layout_widgets(self) -> None:
        """Layout all widgets with support for queue progress and preview controls."""
        # Queue progress section (verification mode only)
        if self.mode == 'verification' and self.queue_progress_frame:
            self.queue_progress_frame.pack(fill='x', padx=10, pady=5)
            self.queue_progress_label.pack(anchor='w')
        
        # File info header
        self.info_frame.pack(fill='x', padx=10, pady=5)
        self.file_label.pack(anchor='w')
        self.lines_label.pack(anchor='w')
        self.columns_label.pack(anchor='w')
        self.instrument_type_label.pack(anchor='w')
        self.instrument_hint_label.pack(anchor='w')
        
        # Preview controls (now in both modes)
        self.preview_control_frame.pack(fill='x', padx=10, pady=5)
        self.controls_row.pack(fill='x')
        
        self.preview_lines_label.grid(row=0, column=0, sticky='w', padx=(0,5))
        self.preview_lines_entry.grid(row=0, column=1, padx=5)
        self.refresh_button.grid(row=0, column=2, padx=10)
        self.preview_hint_label.grid(row=0, column=3, sticky='w', padx=(5,0))
        self.status_label.grid(row=0, column=4, sticky='w', padx=(20,0))
        
        # Preview text
        self.preview_section.pack(fill='both', expand=True, padx=10, pady=5)
        self.text_frame.pack(fill='both', expand=True)
        
        self.preview_text.grid(row=0, column=0, sticky='nsew')
        self.scrollbar_y.grid(row=0, column=1, sticky='ns')
        self.scrollbar_x.grid(row=1, column=0, sticky='ew')
        
        self.text_frame.grid_rowconfigure(0, weight=1)
        self.text_frame.grid_columnconfigure(0, weight=1)
        
        # Filter controls
        self.filter_frame.pack(fill='x', padx=10, pady=5)
        self.filter_row.pack(fill='x')
        
        self.tag_label.grid(row=0, column=0, sticky='w', padx=(0,5))
        self.tag_entry.grid(row=0, column=1, sticky='w', padx=5)
        
        self.skip_label.grid(row=1, column=0, sticky='w', pady=(10,0), padx=(0,5))
        self.skip_entry.grid(row=1, column=1, sticky='w', padx=5, pady=(10,0))
        self.skip_hint_label.grid(row=1, column=2, sticky='w', padx=(10,0), pady=(10,0))
        
        # Mode-aware buttons layout
        self.button_frame.pack(fill='x', padx=10, pady=10)
        
        self.load_button.pack(side='left', padx=5)
        if self.mode == 'verification':
            self.skip_button.pack(side='left', padx=5)
        self.cancel_button.pack(side='left', padx=5)
        
    def _populate_initial_data(self) -> None:
        """Populate the dialog with initial preview data."""
        if self.preview_data and self.preview_data.get('success'):
            self._update_preview_text(self.preview_data['preview_lines'])
        
    def _setup_event_handlers(self) -> None:
        """Setup event handlers."""
        # Enhanced keyboard shortcuts
        self.dialog.bind('<Control-r>', lambda e: self._refresh_preview())
        self.dialog.bind('<Return>', self._handle_enter_key)
        self.dialog.bind('<Escape>', lambda e: self._on_cancel())
        
        # Tab navigation between key fields
        self.preview_lines_entry.bind('<Tab>', lambda e: self.tag_entry.focus_set())
        self.tag_entry.bind('<Tab>', lambda e: self.skip_entry.focus_set())
        self.skip_entry.bind('<Tab>', lambda e: self.load_button.focus_set())
        
        # Focus on tag entry for immediate editing
        self.tag_entry.focus_set()
        self.tag_entry.select_range(0, tk.END)
        
    def _handle_enter_key(self, event):
        """Handle Enter key - load if not in preview lines entry."""
        focused_widget = self.dialog.focus_get()
        
        # If focus is on preview lines entry, refresh instead of loading
        if focused_widget == self.preview_lines_entry:
            self._refresh_preview()
        else:
            # Otherwise, load the file
            self._on_load()
        
        return 'break'
        
    def _update_preview_text(self, preview_lines: list) -> None:
        """Update the preview text widget with new content."""
        self.preview_text.config(state='normal')
        self.preview_text.delete(1.0, tk.END)
        
        # Add preview content with row numbers
        for i, line in enumerate(preview_lines):
            self.preview_text.insert(tk.END, f"{i:3d}: {line}\n")
        
        self.preview_text.config(state='disabled')
        
    def _refresh_preview(self) -> None:
        """Refresh preview using cached data processor and minimal re-detection."""
        try:
            num_lines = self.preview_lines_var.get()
            if num_lines < 1:
                num_lines = 1
                self.preview_lines_var.set(1)
            elif num_lines > 1000:
                num_lines = 1000
                self.preview_lines_var.set(1000)
            
            # Check if we need to re-detect instrument type (if preview lines significantly increased)
            current_preview_lines = len(self.preview_data.get('preview_lines', [])) if self.preview_data else 0
            
            if num_lines > current_preview_lines * 2:
                # Significant increase - re-detect instrument type in case more header info is revealed
                logger.info(f"Significant preview line increase ({current_preview_lines} → {num_lines}) - re-detecting instrument type")
                self._load_file_metadata()  # Re-detect instrument type
                
                # Update instrument type display if it changed
                new_instrument_type = self.cached_instrument_type
                if hasattr(self, 'instrument_type_label'):
                    instrument_color = 'green' if new_instrument_type != 'Unknown' else 'orange'
                    self.instrument_type_label.config(
                        text=f"Instrument Type: {new_instrument_type}",
                        foreground=instrument_color
                    )
                    
                    # Update instrument hint
                    default_lines = INSTRUMENT_PREVIEW_DEFAULTS.get(new_instrument_type, DEFAULT_PREVIEW_LINES)
                    self.instrument_hint_label.config(
                        text=f"Default preview for {new_instrument_type}: {default_lines} lines"
                    )
            
            # Load new preview content using optimized method
            self._load_preview_content(num_lines)
            
            if self.preview_data and self.preview_data.get('success'):
                self._update_preview_text(self.preview_data['preview_lines'])
                self.status_label.config(
                    text=f"✓ Showing first {len(self.preview_data['preview_lines'])} lines",
                    foreground='green'
                )
                
                logger.info(f"Preview refreshed efficiently: {num_lines} lines")
                
            else:
                error_msg = self.preview_data.get('error', 'Unknown error') if self.preview_data else 'Failed to load preview'
                messagebox.showerror(
                    "Preview Error", 
                    f"Failed to refresh preview:\n{error_msg}"
                )
                self.status_label.config(
                    text="✗ Preview refresh failed",
                    foreground='red'
                )
                
        except tk.TclError:
            messagebox.showerror("Error", "Please enter a valid number of lines to preview.")

    def _validate_float_input(self, value_if_allowed):
        """
        Validate that input is a valid float or empty.
        
        Args:
            value_if_allowed: The value that would be in the entry if the keystroke is allowed
            
        Returns:
            bool: True if input is valid, False otherwise
        """
        if value_if_allowed == "":
            return True  # Allow empty string (for clearing)
        
        # Allow negative sign at the beginning
        if value_if_allowed == "-":
            return True
        
        # Allow single decimal point
        if value_if_allowed.count('.') <= 1:
            try:
                float(value_if_allowed)
                return True
            except ValueError:
                return False
        
        return False

    def _generate_auto_numeric_tag(self, filename: str) -> str:
        """Generate a numeric tag from filename or use default."""
        import re
        from pathlib import Path
        
        # Remove extension
        base_name = Path(filename).stem
        
        # Try to extract numbers from filename
        numbers = re.findall(r'-?\d+\.?\d*', base_name)
        
        if numbers:
            try:
                # Use the first number found
                return str(float(numbers[0]))
            except ValueError:
                pass
        
        # Default to 1.0 if no number found
        return "1.0"

    def _on_load(self) -> None:
        """Handle the load button click with float validation."""
        try:
            skip_rows = self.skip_var.get()
            if skip_rows < 0:
                skip_rows = 0
                
            tag_str = self.tag_var.get().strip()
            if not tag_str:
                messagebox.showerror("Error", "Please enter a numeric bead size value.")
                return
            
            # Validate float
            try:
                tag_float = float(tag_str)
                normalized_tag = str(tag_float)  # Normalize the display
            except ValueError:
                messagebox.showerror("Error", "Bead size must be a valid number (e.g., 1.5, -2.0, 42)")
                return
            
            # Close dialog and call the callback
            self.dialog.destroy()
            self.on_load_callback(self.file_path, normalized_tag, skip_rows)
            
        except tk.TclError:
            messagebox.showerror("Error", "Please enter a valid number for rows to skip.")
    
    def _on_skip(self) -> None:
        """Handle the skip button click (verification mode only)."""
        if self.mode != 'verification':
            return
            
        # Close dialog and call skip callback
        self.dialog.destroy()
        # Call skip callback if provided in queue context
        if 'skip_callback' in self.queue_context:
            self.queue_context['skip_callback']()
         
    def _on_cancel(self) -> None:
        """Handle cancel with mode-aware callback support."""
        # Call cancel callback if provided in queue context (verification mode)
        if self.mode == 'verification' and 'cancel_callback' in self.queue_context:
            self.dialog.destroy()
            self.queue_context['cancel_callback']()
        else:
            # Standard cancel (calibration mode)
            self.dialog.destroy()