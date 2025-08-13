# gui/dialogs/file_preview.py
"""
Enhanced file preview dialog for CSV files with filtering options.
"""

import tkinter as tk
from tkinter import ttk, messagebox
import logging
from typing import Dict, Any, Callable, Optional
from core.data_processor import ParticleDataProcessor

logger = logging.getLogger(__name__)

class FilePreviewDialog:
    """Enhanced dialog for previewing CSV files with configurable filtering options and instrument type detection."""
    
    def __init__(self, parent, file_path: str, on_load_callback: Callable[[str, str, int], None]):
        """
        Initialize the file preview dialog.
        
        Args:
            parent: Parent window
            file_path: Path to the CSV file to preview
            on_load_callback: Callback function called when user chooses to load
                             Signature: callback(file_path, tag, skip_rows)
        """
        self.parent = parent
        self.file_path = file_path
        self.on_load_callback = on_load_callback
        self.dialog = None
        self.preview_data = None
        
        # UI variables
        self.preview_lines_var = None
        self.skip_var = None
        self.tag_var = None
        
        # UI widgets
        self.preview_text = None
        self.status_label = None
        self.instrument_type_label = None
        
    def show(self) -> None:
        """Show the preview dialog."""
        # Get initial preview data 
        temp_processor = ParticleDataProcessor()
        self.preview_data = temp_processor.preview_csv(self.file_path, preview_rows=15)
        
        if not self.preview_data['success']:
            messagebox.showerror(
                "Preview Error", 
                f"Failed to preview file:\n{self.preview_data['error']}"
            )
            return
        
        self._create_dialog()
        self._create_widgets()
        self._layout_widgets()
        self._populate_initial_data()
        self._setup_event_handlers()
        
    def _create_dialog(self) -> None:
        """Create the main dialog window."""
        self.dialog = tk.Toplevel(self.parent)
        self.dialog.title("CSV File Preview - Enhanced")
        self.dialog.geometry("950x750")
        self.dialog.grab_set()  # Make it modal
        
        # Center the dialog
        self.dialog.transient(self.parent)
        self.dialog.update_idletasks()
        x = (self.dialog.winfo_screenwidth() // 2) - (475)
        y = (self.dialog.winfo_screenheight() // 2) - (375)
        self.dialog.geometry(f"950x750+{x}+{y}")
        
        # Handle dialog close
        self.dialog.protocol("WM_DELETE_WINDOW", self._on_cancel)
        
    def _create_widgets(self) -> None:
        """Create all dialog widgets."""
        # File info header
        self.info_frame = ttk.LabelFrame(self.dialog, text="File Information", padding=5)
        
        filename = self.file_path.split('/')[-1].split('\\')[-1]  # Handle both path separators
        self.file_label = ttk.Label(
            self.info_frame, 
            text=f"File: {filename}", 
            font=('TkDefaultFont', 9, 'bold')
        )
        self.lines_label = ttk.Label(
            self.info_frame, 
            text=f"Total lines: {self.preview_data['total_lines']}"
        )
        self.columns_label = ttk.Label(
            self.info_frame, 
            text=f"Detected columns: {self.preview_data['detected_columns']}"
        )
        
        # NEW: Instrument type display
        instrument_type = self.preview_data.get('instrument_type', 'Unknown')
        instrument_color = 'green' if instrument_type != 'Unknown' else 'orange'
        self.instrument_type_label = ttk.Label(
            self.info_frame,
            text=f"Instrument Type: {instrument_type}",
            font=('TkDefaultFont', 9, 'bold'),
            foreground=instrument_color
        )
        
        # Preview controls section
        self.preview_control_frame = ttk.LabelFrame(self.dialog, text="Preview Controls", padding=5)
        self.controls_row = ttk.Frame(self.preview_control_frame)
        
        # Preview controls widgets
        self.preview_lines_label = ttk.Label(self.controls_row, text="Preview lines:")
        self.preview_lines_var = tk.IntVar(value=15)
        self.preview_lines_entry = ttk.Entry(self.controls_row, textvariable=self.preview_lines_var, width=8)
        self.refresh_button = ttk.Button(self.controls_row, text="🔄 Refresh Preview", command=self._refresh_preview)
        self.preview_hint_label = ttk.Label(self.controls_row, text="(1-1000 lines)", font=('TkDefaultFont', 8))
        self.status_label = ttk.Label(
            self.controls_row, 
            text=f"✓ Showing first {len(self.preview_data['preview_lines'])} lines", 
            foreground='green', 
            font=('TkDefaultFont', 8)
        )
        
        # Preview text section
        self.preview_section = ttk.LabelFrame(self.dialog, text="File Preview", padding=5)
        self.text_frame = ttk.Frame(self.preview_section)
        
        self.preview_text = tk.Text(self.text_frame, wrap='none', font=('Courier', 9))
        self.scrollbar_y = ttk.Scrollbar(self.text_frame, orient='vertical', command=self.preview_text.yview)
        self.scrollbar_x = ttk.Scrollbar(self.text_frame, orient='horizontal', command=self.preview_text.xview)
        self.preview_text.configure(yscrollcommand=self.scrollbar_y.set, xscrollcommand=self.scrollbar_x.set)
        
        # Filter controls section
        self.filter_frame = ttk.LabelFrame(self.dialog, text="Data Filtering Options", padding=10)
        self.filter_row = ttk.Frame(self.filter_frame)
        
        # Generate numeric tag from filename (improved logic)
        filename = self.file_path.split('/')[-1].split('\\')[-1]
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
        
        self.skip_label = ttk.Label(self.filter_row, text="Skip rows from top:")
        self.skip_var = tk.IntVar(value=0)
        self.skip_entry = ttk.Entry(self.filter_row, textvariable=self.skip_var, width=6)
        self.skip_hint_label = ttk.Label(
            self.filter_row, 
            text="(Use this to skip headers, metadata, or junk data)", 
            font=('TkDefaultFont', 8)
        )
        
        # Buttons section
        self.button_frame = ttk.Frame(self.dialog)
        self.load_button = ttk.Button(self.button_frame, text="📁 Load with Filter", command=self._on_load)
        self.cancel_button = ttk.Button(self.button_frame, text="❌ Cancel", command=self._on_cancel)
        
    def _layout_widgets(self) -> None:
        """Layout all widgets in the dialog."""
        # File info header
        self.info_frame.pack(fill='x', padx=10, pady=5)
        self.file_label.pack(anchor='w')
        self.lines_label.pack(anchor='w')
        self.columns_label.pack(anchor='w')
        self.instrument_type_label.pack(anchor='w')  # NEW: Display instrument type
        
        # Preview controls
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
        
        # Buttons
        self.button_frame.pack(fill='x', padx=10, pady=10)
        self.load_button.pack(side='left', padx=5)
        self.cancel_button.pack(side='left', padx=5)
        
    def _populate_initial_data(self) -> None:
        """Populate the dialog with initial preview data."""
        self._update_preview_text(self.preview_data['preview_lines'])
        
    def _setup_event_handlers(self) -> None:
        """Setup event handlers for the dialog."""
        # Allow Enter key to refresh preview
        self.preview_lines_entry.bind('<Return>', lambda e: self._refresh_preview())
        
        # Focus on tag entry for immediate editing
        self.tag_entry.focus_set()
        self.tag_entry.select_range(0, tk.END)
        
        # Escape key to cancel
        self.dialog.bind('<Escape>', lambda e: self._on_cancel())
        
    def _update_preview_text(self, preview_lines: list) -> None:
        """Update the preview text widget with new content."""
        self.preview_text.config(state='normal')
        self.preview_text.delete(1.0, tk.END)
        
        # Add preview content with row numbers
        for i, line in enumerate(preview_lines):
            self.preview_text.insert(tk.END, f"{i:3d}: {line}\n")
        
        self.preview_text.config(state='disabled')
        
    def _refresh_preview(self) -> None:
        """Refresh the preview with new line count and re-detect instrument type."""
        try:
            num_lines = self.preview_lines_var.get()
            if num_lines < 1:
                num_lines = 1
                self.preview_lines_var.set(1)
            elif num_lines > 1000:
                num_lines = 1000
                self.preview_lines_var.set(1000)
            
            # Get new preview data (includes re-detection of instrument type)
            temp_processor = ParticleDataProcessor()
            new_preview_data = temp_processor.preview_csv(self.file_path, preview_rows=num_lines)
            
            if new_preview_data['success']:
                self._update_preview_text(new_preview_data['preview_lines'])
                self.status_label.config(
                    text=f"✓ Showing first {len(new_preview_data['preview_lines'])} lines",
                    foreground='green'
                )
                
                # Update instrument type display
                instrument_type = new_preview_data.get('instrument_type', 'Unknown')
                instrument_color = 'green' if instrument_type != 'Unknown' else 'orange'
                self.instrument_type_label.config(
                    text=f"Instrument Type: {instrument_type}",
                    foreground=instrument_color
                )
                
                # Store updated preview data
                self.preview_data = new_preview_data
                
            else:
                messagebox.showerror(
                    "Preview Error", 
                    f"Failed to refresh preview:\n{new_preview_data['error']}"
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

            
    def _on_cancel(self) -> None:
        """Handle the cancel button click or dialog close."""
        self.dialog.destroy()