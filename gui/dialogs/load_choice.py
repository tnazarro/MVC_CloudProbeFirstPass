# gui/dialogs/load_choice.py
"""
Modal dialog for choosing between single and multiple file loading in verification mode.
"""

import tkinter as tk
from tkinter import ttk
import logging
from typing import Callable, Literal

logger = logging.getLogger(__name__)

LoadChoice = Literal['single', 'multiple', 'cancel']

class LoadChoiceDialog:
    """Dialog for choosing between single or multiple file loading in verification mode."""
    
    def __init__(self, parent, on_choice_callback: Callable[[LoadChoice], None]):
        """
        Initialize the load choice dialog.
        
        Args:
            parent: Parent window
            on_choice_callback: Callback function called when user makes a choice
                               Signature: callback(choice) where choice is 'single', 'multiple', or 'cancel'
        """
        self.parent = parent
        self.on_choice_callback = on_choice_callback
        self.dialog = None
        self.choice_made = False
        
    def show(self) -> None:
        """Show the load choice dialog."""
        self._create_dialog()
        self._create_widgets()
        self._layout_widgets()
        self._setup_event_handlers()
        
        # Wait for dialog to close
        self.dialog.wait_window()
        
        # If no choice was made (dialog was closed), call callback with 'cancel'
        if not self.choice_made:
            self.on_choice_callback('cancel')
    
    def _create_dialog(self) -> None:
        """Create the main dialog window."""
        self.dialog = tk.Toplevel(self.parent)
        self.dialog.title("Load Data Files")
        self.dialog.geometry("450x450")
        self.dialog.grab_set()  # Make it modal
        self.dialog.resizable(True, True)  # Allow resizing
        
        # Center the dialog
        self.dialog.transient(self.parent)
        self.dialog.update_idletasks()
        x = (self.dialog.winfo_screenwidth() // 2) - (225)
        y = (self.dialog.winfo_screenheight() // 2) - (225)
        self.dialog.geometry(f"450x450+{x}+{y}")
        
        # Handle dialog close
        self.dialog.protocol("WM_DELETE_WINDOW", self._on_cancel)
        
    def _create_widgets(self) -> None:
        """Create all dialog widgets."""
        # Main frame
        self.main_frame = ttk.Frame(self.dialog, padding=20)
        
        # Title
        self.title_label = ttk.Label(
            self.main_frame, 
            text="Choose Loading Method", 
            font=('TkDefaultFont', 12, 'bold')
        )
        
        # Description
        self.desc_label = ttk.Label(
            self.main_frame,
            text="Verification mode supports both single and multiple file analysis:",
            font=('TkDefaultFont', 9),
            foreground='gray'
        )
        
        # Button frame
        self.button_frame = ttk.Frame(self.main_frame)
        
        # === SINGLE FILE SECTION ===
        self.single_frame = ttk.LabelFrame(self.button_frame, text="Single File", padding=15)
        
        # Single file description
        self.single_desc = ttk.Label(
            self.single_frame, 
            text="Load one CSV file with preview and filtering options",
            font=('TkDefaultFont', 8),
            foreground='blue'
        )
        
        # Single file button with shortcut indicator
        self.single_btn = ttk.Button(
            self.single_frame, 
            text="📄 Load Single File (1 or Enter)",
            command=self._choice_single_file,
            width=25
        )
        # === MULTIPLE FILES SECTION ===
        self.multi_frame = ttk.LabelFrame(self.button_frame, text="Multiple Files", padding=15)
        
        # Multiple files description
        self.multi_desc = ttk.Label(
            self.multi_frame, 
            text="Load multiple CSV files for comparison analysis",
            font=('TkDefaultFont', 8),
            foreground='green'
        )
        
        # Multiple files button with shortcut indicator
        self.multi_btn = ttk.Button(
            self.multi_frame, 
            text="📁 Load Multiple Files (2)",
            command=self._choice_multiple_files,
            width=25
        )
        
        # === CANCEL BUTTON ===
        self.cancel_btn = ttk.Button(
            self.main_frame, 
            text="Cancel", 
            command=self._on_cancel
        )
        
    def _layout_widgets(self) -> None:
        """Layout all widgets in the dialog."""
        self.main_frame.pack(fill='both', expand=True)
        
        # Title and description
        self.title_label.pack(pady=(0, 15))
        self.desc_label.pack(pady=(0, 20))
        
        # Button frame
        self.button_frame.pack(fill='both', expand=True, pady=10)
        
        # Single file section
        self.single_frame.pack(fill='x', pady=(0, 15))
        self.single_desc.pack(anchor='w')
        self.single_btn.pack(pady=(10, 0), anchor='w')
        
        # Multiple files section
        self.multi_frame.pack(fill='x', pady=(0, 15))
        self.multi_desc.pack(anchor='w')
        self.multi_btn.pack(pady=(10, 0), anchor='w')
        
        # Cancel button
        self.cancel_btn.pack(pady=(20, 0))
        
    def _setup_event_handlers(self) -> None:
        """Setup event handlers for the dialog."""
        # Set focus and bind keyboard shortcuts
        self.dialog.focus_set()
        self.dialog.bind('<Escape>', lambda e: self._on_cancel())
        self.dialog.bind('<1>', lambda e: self._choice_single_file())  # Key '1' for single
        self.dialog.bind('<2>', lambda e: self._choice_multiple_files())  # Key '2' for multiple
        self.dialog.bind('<Return>', lambda e: self._choice_single_file())  # Enter defaults to single
        
        # Focus on single file button by default
        self.single_btn.focus_set()
        
    def _choice_single_file(self) -> None:
        """Handle single file choice."""
        self.choice_made = True
        self.dialog.destroy()
        self.on_choice_callback('single')
        
    def _choice_multiple_files(self) -> None:
        """Handle multiple files choice."""
        self.choice_made = True
        self.dialog.destroy()
        self.on_choice_callback('multiple')
        
    def _on_cancel(self) -> None:
        """Handle cancel or dialog close."""
        self.choice_made = True
        self.dialog.destroy()
        self.on_choice_callback('cancel')

