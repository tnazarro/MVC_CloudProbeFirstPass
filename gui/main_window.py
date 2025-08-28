"""
Main GUI window for the Particle Data Analyzer with Dataset Manager integration and Analysis Mode Selection.
Updated with compact dataset panel and inline tag editing - saving vertical space.
LAYOUT UPDATE: Moved "Loaded Datasets" frame to left column (column 0) above dataset management.
Uses ScrollableFrame for proper vertical scrolling.
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
import logging
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
import matplotlib.pyplot as plt
import numpy as np

from core.data_processor import ParticleDataProcessor
from core.dataset_manager import DatasetManager
from core.plotter import ParticlePlotter
from config.constants import (SUPPORTED_FILE_TYPES, MIN_BIN_COUNT, MAX_BIN_COUNT, DEFAULT_BIN_COUNT,
                             FONT_PROGRESS, FONT_INSTRUMENT_TYPE, FONT_HINT_TEXT, FONT_STATUS, FONT_FILE_NAME, FONT_PREVIEW_TEXT, FONT_STATUS_LARGE)
from core.file_queue import FileQueue
from gui.dialogs.file_preview import FilePreviewDialog
from gui.dialogs.load_choice import LoadChoiceDialog


# Try to import report generation (now required dependency)
try:
    from reports.templates import StandardReportTemplate
    REPORTS_AVAILABLE = True
except ImportError:
    REPORTS_AVAILABLE = False

logger = logging.getLogger(__name__)


class ScrollableFrame(ttk.Frame):
    """A scrollable frame that can contain other widgets."""
    
    def __init__(self, parent, *args, **kwargs):
        super().__init__(parent, *args, **kwargs)
        
        # Create canvas and scrollbars
        self.canvas = tk.Canvas(self, highlightthickness=0)
        self.v_scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.h_scrollbar = ttk.Scrollbar(self, orient="horizontal", command=self.canvas.xview)
        
        # Create the scrollable frame
        self.scrollable_frame = ttk.Frame(self.canvas)
        
        # Configure canvas
        self.canvas.configure(yscrollcommand=self.v_scrollbar.set,
                            xscrollcommand=self.h_scrollbar.set)
        
        # Layout scrollbars and canvas
        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.v_scrollbar.grid(row=0, column=1, sticky="ns")
        self.h_scrollbar.grid(row=1, column=0, sticky="ew")
        
        # Configure grid weights
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)
        
        # Create window in canvas
        self.canvas_window = self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")

        # Bind events
        self.scrollable_frame.bind("<Configure>", self._on_frame_configure)
        self.canvas.bind("<Configure>", self._on_canvas_configure)
        self.bind_all("<MouseWheel>", self._on_mousewheel)

    def update_scroll_region(self):
        """Manually update the scroll region - useful when content changes."""
        self.canvas.update_idletasks()  # Make sure all pending layout updates are processed
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        
        # Force scrollbar visibility update
        self.canvas.update()
        
        # Debug info
        scroll_region = self.canvas.cget('scrollregion')
        canvas_height = self.canvas.winfo_height()
        if scroll_region:
            region_parts = scroll_region.split()
            if len(region_parts) >= 4:
                content_height = float(region_parts[3]) - float(region_parts[1])
                print(f"ScrollableFrame: Content height: {content_height}, Canvas height: {canvas_height}")
                if content_height > canvas_height:
                    print("ScrollableFrame: Content should be scrollable")
                else:
                    print("ScrollableFrame: Content fits in canvas")

    def _on_frame_configure(self, event):
        """Update scroll region when frame size changes."""
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        
    def _on_canvas_configure(self, event):
        """Update canvas window size when canvas size changes."""
        canvas_width = event.width
        frame_width = self.scrollable_frame.winfo_reqwidth()
        
        if frame_width < canvas_width:
            # Frame is smaller than canvas, center it
            self.canvas.itemconfig(self.canvas_window, width=canvas_width)
        else:
            # Frame is larger than canvas, use frame width
            self.canvas.itemconfig(self.canvas_window, width=frame_width)
            
    def _on_mousewheel(self, event):
        """Handle mouse wheel scrolling."""
        self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")


class MainWindow:
    """Main application window with dataset management and analysis mode selection."""
    
    def __init__(self, root):
        self.root = root
        self.root.title("Particle Data Analyzer")
        self.root.geometry("1400x900")  # Slightly larger to accommodate dataset list
        
        # Set minimum window size for better usability
        self.root.minsize(800, 600)

        # Set up proper close handling
        self.root.protocol("WM_DELETE_WINDOW", self._on_closing)
        
        # Create scrollable frame for left column content
        self.scrollable_frame = ScrollableFrame(self.root)

        # Create scrollable frame for plot area
        self.plot_scrollable_frame = ScrollableFrame(self.root)

        # Initialize core components
        self.dataset_manager = DatasetManager()
        self.plotter = ParticlePlotter()
        self.file_queue = FileQueue()
        
        # GUI variables
        self.bin_count_var = tk.IntVar(value=DEFAULT_BIN_COUNT)
        self.size_column_var = tk.StringVar()
        self.frequency_column_var = tk.StringVar()
        self.show_stats_lines_var = tk.BooleanVar(value=True)
        self.data_mode_var = tk.StringVar(value='raw_measurements')  # 'pre_aggregated' or 'raw_measurements'
        self.skip_rows_var = tk.IntVar(value=0)
        

        # New variable for gaussian fit
        self.show_gaussian_fit_var = tk.BooleanVar(value=True)

        # Analysis mode selection variable (calibration vs verification)
        self.analysis_mode_var = tk.StringVar(value='calibration')
        
        # NEW: Inline tag editing variable
        self.current_tag_var = tk.StringVar()
        self._updating_tag = False  # Flag to prevent recursive updates
        
        # Track current figure for proper cleanup
        self.current_figure = None

        # Drag-and-drop support
        self.drag_item = None
        self.drag_start_y = None
        
        # Report generation
        if REPORTS_AVAILABLE:
            self.report_template = StandardReportTemplate()
        else:
            self.report_template = None
        
        self._create_widgets()
        self._create_layout()
        
        # Initialize UI state
        self._update_data_mode_ui()
        self._update_dataset_ui()
        self._update_analysis_mode_ui()
    
    def _create_widgets(self):
        """Create all GUI widgets."""
        # Main frame (no longer needed - keeping for compatibility but not used)
        self.main_frame = ttk.Frame(self.root)
        
        # Control frame (left side) - now goes inside scrollable frame
        self.control_frame = ttk.LabelFrame(self.scrollable_frame.scrollable_frame, text="Controls", padding=10)
        
        self.load_buttons_frame = ttk.LabelFrame(self.control_frame, text="Analysis Mode", padding=5)
        self.load_buttons_frame.grid(row=0, column=0, columnspan=3, sticky='ew', pady=(0,10))
        
        # Two direct load buttons
        buttons_container = ttk.Frame(self.load_buttons_frame)
        buttons_container.pack(fill='x', pady=(0,5))
        
        self.calibration_load_button = ttk.Button(
            buttons_container, 
            text="Load for Calibration", 
            command=self._load_for_calibration
        )
        self.calibration_load_button.pack(side='left', padx=(0,10), fill='x', expand=True)
        
        self.verification_load_button = ttk.Button(
            buttons_container, 
            text="Load for Verification", 
            command=self._load_for_verification
        )
        self.verification_load_button.pack(side='left', fill='x', expand=True)
        
        # Mode description label
        self.mode_description = ttk.Label(
            self.load_buttons_frame, 
            text="Current Mode: Calibration (Single dataset analysis)",
            font=FONT_HINT_TEXT,
            foreground='blue'
        )
        self.mode_description.pack(anchor='w', pady=(5,0))
        
        # Queue status display
        self.queue_status_frame = ttk.Frame(self.control_frame)
        self.queue_status_frame.grid(row=1, column=0, columnspan=3, sticky='ew', pady=2)
        
        self.queue_status_label = ttk.Label(self.queue_status_frame, text="", font=FONT_STATUS)
        self.queue_status_label.pack(anchor='w')
        
        # === LOADED DATASETS FRAME ===
        self.dataset_list_frame = ttk.LabelFrame(self.control_frame, text="Loaded Datasets", padding=5)
        self.dataset_list_frame.grid(row=2, column=0, columnspan=3, sticky='ew', pady=(10,10)) 
        
        # Dataset treeview with scrollbar - REDUCED HEIGHT to 8 rows with separate columns
        list_container = ttk.Frame(self.dataset_list_frame)
        list_container.pack(fill='x', pady=(0,5))  # Changed from fill='both', expand=True
        
        # Create Treeview with columns for Tag and Filename
        self.dataset_treeview = ttk.Treeview(
            list_container, 
            columns=('tag', 'filename'), 
            show='tree headings',  # Show both tree and headings
            height=8,  # REDUCED to 8 rows (was 10) to fit in left column
            selectmode='browse'  # Single selection
        )
        
        # Configure columns
        self.dataset_treeview.heading('#0', text='')  # Hide the tree column header
        self.dataset_treeview.heading('tag', text='Bead Size (μm)')
        self.dataset_treeview.heading('filename', text='Filename')
        
        # Set column widths - adjusted for narrower left column
        self.dataset_treeview.column('#0', width=15, minwidth=15, stretch=False)  # Smaller tree column for bullet
        self.dataset_treeview.column('tag', width=80, minwidth=60, stretch=True)  # Narrower tag column
        self.dataset_treeview.column('filename', width=120, minwidth=80, stretch=True)  # Narrower filename column
        
        # Scrollbars
        dataset_scrollbar_y = ttk.Scrollbar(list_container, orient='vertical', command=self.dataset_treeview.yview)
        dataset_scrollbar_x = ttk.Scrollbar(list_container, orient='horizontal', command=self.dataset_treeview.xview)
        
        self.dataset_treeview.configure(yscrollcommand=dataset_scrollbar_y.set, xscrollcommand=dataset_scrollbar_x.set)
        self.dataset_treeview.bind('<ButtonPress-1>', self._on_treeview_button_press)
        self.dataset_treeview.bind('<B1-Motion>', self._on_treeview_drag_motion)
        self.dataset_treeview.bind('<ButtonRelease-1>', self._on_treeview_button_release)
        self.dataset_treeview.bind('<<TreeviewSelect>>', self._on_dataset_select)
        
        # Grid layout for treeview and scrollbars
        self.dataset_treeview.grid(row=0, column=0, sticky='nsew')
        dataset_scrollbar_y.grid(row=0, column=1, sticky='ns')
        dataset_scrollbar_x.grid(row=1, column=0, sticky='ew')
        
        list_container.grid_rowconfigure(0, weight=1)
        list_container.grid_columnconfigure(0, weight=1)
        
        # === INLINE TAG EDITOR (still in dataset list frame) ===
        tag_editor_frame = ttk.LabelFrame(self.dataset_list_frame, text="Bead Size (μm)", padding=5)
        tag_editor_frame.pack(fill='x', pady=(0,5))

        # Tag entry with label
        tag_entry_container = ttk.Frame(tag_editor_frame)
        tag_entry_container.pack(fill='x')

        ttk.Label(tag_entry_container, text="Bead Size (μm):").pack(side='left', padx=(0,5))

        # Register validation function for float-only input
        self.validate_float = self.root.register(self._validate_float_input)

        self.tag_entry = ttk.Entry(
            tag_entry_container, 
            textvariable=self.current_tag_var,
            state='disabled',  # Start disabled until dataset is selected
            validate='key',    # Validate on every keystroke
            validatecommand=(self.validate_float, '%P')  # %P = new value after keystroke
        )
        self.tag_entry.pack(side='left', fill='x', expand=True, padx=(0,5))

        # Bind tag entry events (keep existing bindings)
        self.current_tag_var.trace('w', self._on_tag_var_change)
        self.tag_entry.bind('<Return>', self._on_tag_entry_return)
        self.tag_entry.bind('<FocusOut>', self._on_tag_entry_focusout)

        # Quick save button (keep existing)
        self.tag_save_btn = ttk.Button(
            tag_entry_container, 
            text="💾", 
            width=3,
            command=self._save_current_tag,
            state='disabled'
        )
        self.tag_save_btn.pack(side='right')
        
        # === COMPACT DATASET INFO (still in dataset list frame) ===
        compact_info_frame = ttk.LabelFrame(self.dataset_list_frame, text="Dataset Info", padding=5)
        compact_info_frame.pack(fill='x')
        
        # Compact info display - single label with key info
        self.compact_info_label = ttk.Label(
            compact_info_frame, 
            text="No datasets loaded", 
            font=FONT_STATUS,
            wraplength=250,  # Adjusted for left column width
            justify='left'
        )
        self.compact_info_label.pack(anchor='w', fill='x')
        
        # === DATA ANALYSIS CONTROLS ===
        ttk.Separator(self.control_frame, orient='horizontal').grid(row=3, column=0, columnspan=3, sticky='ew', pady=5)
        
        # Data mode selection
        ttk.Label(self.control_frame, text="Data Type:").grid(row=4, column=0, sticky='w', pady=2) 
        
        data_mode_frame = ttk.Frame(self.control_frame)
        data_mode_frame.grid(row=4, column=1, columnspan=2, sticky='ew', pady=2)
        
        self.pre_agg_radio = ttk.Radiobutton(data_mode_frame, text="Pre-aggregated (Size + Frequency)", 
                                           variable=self.data_mode_var, value='pre_aggregated',
                                           command=self._on_data_mode_change)
        self.pre_agg_radio.grid(row=0, column=0, sticky='w')
        
        self.raw_radio = ttk.Radiobutton(data_mode_frame, text="Raw Measurements (Size only)", 
                                       variable=self.data_mode_var, value='raw_measurements',
                                       command=self._on_data_mode_change)
        self.raw_radio.grid(row=1, column=0, sticky='w')
        
        #Column selection
        ttk.Label(self.control_frame, text="Size Column:").grid(row=5, column=0, sticky='w', pady=2)
        self.size_combo = ttk.Combobox(self.control_frame, textvariable=self.size_column_var, 
                                    state='readonly')
        self.size_combo.grid(row=5, column=1, sticky='ew', pady=2)
        self.size_combo.bind('<<ComboboxSelected>>', self._on_column_change)

        self.frequency_label = ttk.Label(self.control_frame, text="Frequency Column:")
        self.frequency_label.grid(row=6, column=0, sticky='w', pady=2)
        self.frequency_combo = ttk.Combobox(self.control_frame, textvariable=self.frequency_column_var, 
                                        state='readonly')
        self.frequency_combo.grid(row=6, column=1, sticky='ew', pady=2)
        self.frequency_combo.bind('<<ComboboxSelected>>', self._on_column_change)

        # Bin count control
        ttk.Label(self.control_frame, text="Bins:").grid(row=7, column=0, sticky='w', pady=2)

        # Create frame for bin controls
        bin_frame = ttk.Frame(self.control_frame)
        bin_frame.grid(row=7, column=1, columnspan=2, sticky='ew', pady=2)

        # Bin count entry field only (remove slider)
        self.bin_entry = ttk.Entry(bin_frame, textvariable=self.bin_count_var, width=8)
        self.bin_entry.grid(row=0, column=0, sticky='w')
        self.bin_entry.bind('<Return>', self._on_bin_entry_change)
        self.bin_entry.bind('<FocusOut>', self._on_bin_entry_change)

        # Optional: Add a label showing the valid range
        bin_hint_label = ttk.Label(bin_frame, text=f"({MIN_BIN_COUNT}-{MAX_BIN_COUNT})", 
                                font=FONT_HINT_TEXT, foreground='gray')
        bin_hint_label.grid(row=0, column=1, sticky='w', padx=(5,0))

        # Configure bin frame column weights (optional, for consistent spacing)
        bin_frame.columnconfigure(0, weight=0)  # Entry field doesn't need to expand
        bin_frame.columnconfigure(1, weight=1)  # Hint label can expand if needed
        
        # Statistical lines toggle
        self.stats_lines_check = ttk.Checkbutton(self.control_frame, 
                                                text="Show Mean & Std Dev Lines", 
                                                variable=self.show_stats_lines_var,
                                                command=self._on_stats_toggle)
        self.stats_lines_check.grid(row=8, column=0, columnspan=2, sticky='w', pady=2)
        
        # Gaussian curve fitting toggle
        self.gaussian_fit_check = ttk.Checkbutton(
            self.control_frame, 
            text="Show Gaussian Curve Fit", 
            variable=self.show_gaussian_fit_var,
            command=self._on_gaussian_toggle
        )
        self.gaussian_fit_check.grid(row=9, column=0, columnspan=2, sticky='w', pady=2)

        # Gaussian fit info button
        self.gaussian_info_btn = ttk.Button(
            self.control_frame, 
            text="📊 Fit Info", 
            command=self.show_gaussian_info, 
            state='disabled',
            width=10
        )
        self.gaussian_info_btn.grid(row=9, column=2, sticky='w', padx=(10,0), pady=2)

        # Plot button (all row numbers updated)
        self.plot_button = ttk.Button(self.control_frame, text="Create Plot", 
                                     command=self.create_plot, state='disabled')
        self.plot_button.grid(row=10, column=0, columnspan=2, sticky='ew', pady=10)
        
        # Report generation button - will be mode-restricted
        self.report_button = ttk.Button(self.control_frame, text="Generate Report", 
                                       command=self.generate_report, state='disabled')
        self.report_button.grid(row=11, column=0, columnspan=2, sticky='ew', pady=5)
        
        # Show/hide report button based on availability
        if not REPORTS_AVAILABLE:
            self.report_button.config(state='disabled', text="Generate Report (ReportLab not installed)")
        
        # === DATASET MANAGEMENT CONTROLS ===
        ttk.Separator(self.control_frame, orient='horizontal').grid(row=12, column=0, columnspan=3, sticky='ew', pady=10)
        
        # Dataset management frame (navigation buttons moved to plot frame)
        self.dataset_mgmt_frame = ttk.LabelFrame(self.control_frame, text="Dataset Management", padding=5)
        self.dataset_mgmt_frame.grid(row=13, column=0, columnspan=3, sticky='ew', pady=5)
        
        # Dataset actions (navigation buttons moved to plot frame)
        actions_frame = ttk.Frame(self.dataset_mgmt_frame)
        actions_frame.pack(fill='x', pady=5)
        
        self.edit_notes_btn = ttk.Button(actions_frame, text="Edit Notes", 
                                        command=self.edit_dataset_notes, state='disabled')
        self.edit_notes_btn.pack(side='left', padx=(0,5))
        
        self.remove_dataset_btn = ttk.Button(actions_frame, text="Remove", 
                                            command=self.remove_dataset, state='disabled')
        self.remove_dataset_btn.pack(side='left', padx=(0,5))
        
        # Help button
        self.help_btn = ttk.Button(actions_frame, text="?", width=3,
                                  command=self.show_help_dialog)
        self.help_btn.pack(side='right')
        
        # Stats display
        self.stats_frame = ttk.LabelFrame(self.control_frame, text="Data Info", padding=5)
        self.stats_frame.grid(row=14, column=0, columnspan=3, sticky='ew', pady=5)
        
        self.stats_text = tk.Text(self.stats_frame, height=8, width=30)
        self.stats_text.pack(fill='both', expand=True)
        
        # === PLOT FRAME (Right side - now inside its own scrollable frame) ===
        self.plot_frame = ttk.LabelFrame(self.plot_scrollable_frame.scrollable_frame, text="Plot", padding=10)
        
        # Add navigation controls to plot frame (moved from dataset management)
        plot_nav_frame = ttk.Frame(self.plot_frame)
        plot_nav_frame.pack(fill='x', pady=(0, 10))
        
        # Dataset navigation buttons (moved here from dataset management frame)
        self.prev_dataset_btn = ttk.Button(plot_nav_frame, text="◀ Previous Dataset", 
                                          command=self.previous_dataset, state='disabled')
        self.prev_dataset_btn.pack(side='left', padx=(0,10))
        
        self.next_dataset_btn = ttk.Button(plot_nav_frame, text="Next Dataset ▶", 
                                          command=self.next_dataset, state='disabled')
        self.next_dataset_btn.pack(side='left')
        
        # Configure column weights
        self.control_frame.columnconfigure(1, weight=1)
    
    def _create_layout(self):
        # Pack the left scrollable frame, and right plot scrollable frame
        self.scrollable_frame.pack(side='left', fill='y', padx=(5,5), pady=5)
        self.plot_scrollable_frame.pack(side='left', fill='both', expand=True, padx=(0,5), pady=5)
        
        # Pack the control frame inside the left scrollable frame
        self.control_frame.pack(fill='both', expand=True, padx=5, pady=5)
        
        # Pack the plot frame inside the right scrollable frame
        self.plot_frame.pack(fill='both', expand=True, padx=5, pady=5)
        
        # Create placeholder for plot content (will be filled when plot is created)
        plot_content_frame = ttk.Frame(self.plot_frame)
        plot_content_frame.pack(fill='both', expand=True)
        
        # Initially show a message when no plot exists
        self.no_plot_label = ttk.Label(plot_content_frame, 
                                      text="No plot to display\nLoad data and click 'Create Plot' to begin",
                                      font=('TkDefaultFont', 10),
                                      foreground='gray',
                                      justify='center')
        self.no_plot_label.pack(expand=True)
    
    # === DIRECT LOAD METHODS ===
    
    def _load_for_calibration(self):
        """Direct calibration loading - sets mode and loads single file."""
        # Check if we need to clear existing datasets
        if not self._confirm_clear_datasets_if_needed():
            return  # User cancelled
            
        self.analysis_mode_var.set('calibration')
        self._update_analysis_mode_ui()
        self._load_single_file_with_preview()
        
    def _load_for_verification(self):
        """Direct verification loading - sets mode and loads multiple files."""
        if not self._confirm_clear_datasets_if_needed():
            return  # User cancelled
     
        self.analysis_mode_var.set('verification') 
        self._update_analysis_mode_ui()
        self.load_multiple_files()
    
    def _confirm_clear_datasets_if_needed(self):
        """
        Returns:
            bool: True if user confirmed or no datasets to clear, False if cancelled
        """
        if not self.dataset_manager.has_datasets():
            return True  # No datasets to clear, proceed
        
        dataset_count = self.dataset_manager.get_dataset_count()
        dataset_names = [dataset['tag'] for dataset in self.dataset_manager.get_all_datasets()]
        
        # Create confirmation message
        if dataset_count == 1:
            message = f"This will remove the currently loaded dataset:\n• {dataset_names[0]}\n\nContinue?"
        else:
            dataset_list = '\n'.join([f"• {name}" for name in dataset_names[:5]])  # Show first 5
            if dataset_count > 5:
                dataset_list += f"\n• ... and {dataset_count - 5} more"
            message = f"This will remove all {dataset_count} currently loaded datasets:\n\n{dataset_list}\n\nContinue?"
        
        result = messagebox.askyesno(
            "Clear Current Datasets", 
            message,
            icon='warning'
        )
        
        if result:
            # Clear all datasets
            self.dataset_manager.clear_all_datasets()
            self._clear_ui_for_no_datasets()
            logger.info(f"Cleared {dataset_count} datasets before loading new data")
            
        return result

    # === TAG EDITING METHODS ===
    
    def _on_tag_var_change(self, *args):
        """Handle tag variable changes (real-time typing)."""
        if self._updating_tag:
            return  # Prevent recursive updates
        
        # Enable save button when tag is modified
        active_dataset = self.dataset_manager.get_active_dataset()
        if active_dataset:
            current_saved_tag = active_dataset['tag']
            current_entry_tag = self.current_tag_var.get()
            
            # Enable save button if tag has changed
            if current_entry_tag != current_saved_tag:
                self.tag_save_btn.config(state='normal')
            else:
                self.tag_save_btn.config(state='disabled')
    
    def _on_tag_entry_return(self, event):
        """Handle Enter key in tag entry - save immediately."""
        self._save_current_tag()
        self.tag_entry.selection_clear()  # Clear selection after save
        return 'break'  # Prevent default behavior
    
    def _on_tag_entry_focusout(self, event):
        """Handle focus leaving tag entry - save automatically."""
        self._save_current_tag()
    
    def _save_current_tag(self):
        """Save the current tag value to the active dataset."""
        active_dataset = self.dataset_manager.get_active_dataset()
        if not active_dataset:
            return
        
        tag_str = self.current_tag_var.get().strip()
        
        # Validate float input
        if not tag_str:
            # Don't allow empty tags - revert to current
            self._updating_tag = True
            self.current_tag_var.set(str(active_dataset['tag']))
            self._updating_tag = False
            return
        
        try:
            # Convert to float to validate, then store as string representation
            tag_float = float(tag_str)
            tag_display = str(tag_float)  # This normalizes the display (e.g., "1.0" instead of "1.")
            
            # Only update if tag actually changed
            if tag_display != str(active_dataset['tag']):
                self.dataset_manager.update_dataset_tag(active_dataset['id'], tag_display)
                self._update_dataset_ui()  # Refresh UI to show changes
                
                # Visual feedback and update display
                self.tag_save_btn.config(state='disabled')
                self._updating_tag = True
                self.current_tag_var.set(tag_display)  # Update display with normalized format
                self._updating_tag = False
                
                logger.info(f"Updated dataset tag to: {tag_display}")
                
        except ValueError:
            # Invalid float - revert to current tag
            self._updating_tag = True
            self.current_tag_var.set(str(active_dataset['tag']))
            self._updating_tag = False
            
            # Show error message
            messagebox.showerror("Invalid Bead Size", "Bead size must be a valid number (e.g., 1.5, -2.0, 42)")
    
    def _update_tag_editor(self):
        """Update the tag editor with the active dataset's tag."""
        active_dataset = self.dataset_manager.get_active_dataset()
        
        self._updating_tag = True  # Prevent recursive updates
        
        if active_dataset:
            self.current_tag_var.set(active_dataset['tag'])
            self.tag_entry.config(state='normal')
            self.tag_save_btn.config(state='disabled')  # Start with save disabled
        else:
            self.current_tag_var.set("")
            self.tag_entry.config(state='disabled')
            self.tag_save_btn.config(state='disabled')
        
        self._updating_tag = False
    
    
    def _on_analysis_mode_change(self):
        """This method is no longer called by radio buttons, but kept for internal mode changes."""
        mode = self.analysis_mode_var.get()
        logger.info(f"Analysis mode changed to: {mode}")
        
        # Update mode description
        if mode == 'calibration':
            self.mode_description.config(
                text="Current Mode: Calibration (Single dataset analysis)",
                foreground='blue'
            )
        else:  # verification
            self.mode_description.config(
                text="Current Mode: Verification (Multi-dataset comparison)",
                foreground='green'
            )
        
        # Update UI elements based on mode
        self._update_analysis_mode_ui()
    
    def _update_analysis_mode_ui(self):
        """Update UI elements based on the current analysis mode."""
        mode = self.analysis_mode_var.get()
        is_calibration = (mode == 'calibration')
        
        if is_calibration:
            self.mode_description.config(
                text="Current Mode: Calibration (Single dataset analysis)",
                foreground='blue'
            )
        else:
            self.mode_description.config(
                text="Current Mode: Verification (Multi-dataset comparison)",
                foreground='green'
            )
        
        # Update other UI elements based on mode
        self._update_report_button_state_for_mode()
        self._update_navigation_buttons_for_mode()
        
        logger.info(f"UI updated for {mode} mode")
    
    def _update_report_button_state_for_mode(self):
        """Update report button state based on mode and data availability."""
        mode = self.analysis_mode_var.get()
        
        if not REPORTS_AVAILABLE:
            self.report_button.config(state='disabled', text="Generate Report (ReportLab not installed)")
            return
        
        if mode == 'calibration':
            # In calibration mode, disable report generation
            self.report_button.config(
                state='disabled',
                text="Generate Report (Verification mode only)"
            )
        else:  # verification mode
            # In verification mode, enable if we have data and plot
            if hasattr(self, 'canvas') and self.current_figure:
                self.report_button.config(state='normal', text="Generate Report")
            else:
                self.report_button.config(state='disabled', text="Generate Report")
    
    def _update_navigation_buttons_for_mode(self):
        """Update navigation buttons based on mode."""
        mode = self.analysis_mode_var.get()
        has_datasets = self.dataset_manager.has_datasets()
        has_multiple = self.dataset_manager.get_dataset_count() > 1
        
        if mode == 'calibration':
            # In calibration mode, navigation is less relevant but still functional
            self.prev_dataset_btn.config(state='normal' if has_multiple else 'disabled')
            self.next_dataset_btn.config(state='normal' if has_multiple else 'disabled')
        else:  # verification mode
            # In verification mode, navigation is fully functional
            self.prev_dataset_btn.config(state='normal' if has_multiple else 'disabled')
            self.next_dataset_btn.config(state='normal' if has_multiple else 'disabled')
    
    def _keep_only_active_dataset(self):
        """Remove all datasets except the active one (for calibration mode)."""
        active_id = self.dataset_manager.active_dataset_id
        if not active_id:
            return
        
        # Get list of all dataset IDs except the active one
        all_ids = list(self.dataset_manager.datasets.keys())
        to_remove = [id for id in all_ids if id != active_id]
        
        # Remove the datasets
        for dataset_id in to_remove:
            self.dataset_manager.remove_dataset(dataset_id)
        
        # Update UI
        self._update_dataset_ui()
        self._update_analysis_mode_ui()
        
        messagebox.showinfo(
            "Calibration Mode", 
            f"Removed {len(to_remove)} dataset(s). Keeping only the active dataset for calibration analysis."
        )
    
    # === FILE LOADING METHODS ===

    def _load_single_file_with_preview(self):
        """Load a single file with enhanced preview dialog."""
        file_path = filedialog.askopenfilename(
            title="Select CSV file",
            filetypes=SUPPORTED_FILE_TYPES
        )
        
        if file_path:
            #Create and show the enhanced preview dialog with mode specification
            preview_dialog = FilePreviewDialog(
                parent=self.root, 
                file_path=file_path, 
                on_load_callback=self._handle_file_load,
                mode='calibration'  # ADDED: Specify calibration mode
            )
            preview_dialog.show()

    def _handle_file_load(self, file_path: str, tag: str, skip_rows: int):
        """Handle file loading from the preview dialog callback."""
        try:
            # Add dataset to manager
            dataset_id = self.dataset_manager.add_dataset(
                file_path=file_path,
                tag=tag,
                notes="",
                skip_rows=skip_rows
            )
            
            if dataset_id:
                # Set as active dataset
                self.dataset_manager.set_active_dataset(dataset_id)
                
                # Update UI
                self._update_dataset_ui()
                self._load_active_dataset_settings()
                self._update_column_combos()
                self._update_stats_display()
                self.plot_button.config(state='normal')
                self._update_report_button_state()
                
                # Update scroll region after adding dataset
                self.scrollable_frame.update_scroll_region()
                
                if skip_rows > 0:
                    messagebox.showinfo("Success", f"Dataset '{tag}' loaded successfully!\nSkipped {skip_rows} rows.")
                else:
                    messagebox.showinfo("Success", f"Dataset '{tag}' loaded successfully!")
            else:
                messagebox.showerror("Error", "Failed to load file. Please check the file format.")
                
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load file: {str(e)}")

    def load_multiple_files(self):
        """Load multiple CSV files using file queue system (removed mode restriction)."""
        file_paths = filedialog.askopenfilenames(
            title="Select CSV files",
            filetypes=SUPPORTED_FILE_TYPES
        )
        
        if file_paths:
            # Clear any existing queue
            self.file_queue.clear_queue()
            
            # Add files to queue
            added_count = self.file_queue.add_files(list(file_paths))
            
            if added_count > 0:
                self._update_queue_status()
                messagebox.showinfo("Files Selected", 
                                f"Added {added_count} files to processing queue.\n"
                                f"Processing will begin with enhanced preview for each file.")
                
                # Start the queue processing workflow
                self._start_queue_processing()
            else:
                messagebox.showerror("Error", "No valid files were added to the queue.")
    
    # === FILE QUEUE PROCESSING METHODS ===
    
    def _start_queue_processing(self):
        """Start the queue processing workflow."""
        if not self.file_queue.has_more_files():
            messagebox.showinfo("Queue Complete", "No files to process.")
            return
        
        # Process the first file
        self._process_current_queue_file()

    def _process_current_queue_file(self):
        """Process the current file in the queue using enhanced FilePreviewDialog."""
        current_file = self.file_queue.get_current_file()
        
        if not current_file:
            # Queue is complete
            self._finish_queue_processing()
            return
        
        self._update_queue_status()
        
        # CHANGED: Use enhanced FilePreviewDialog instead of custom dialog
        self._show_unified_queue_preview(current_file)

    def _show_unified_queue_preview(self, file_info):
        """Show preview using unified FilePreviewDialog with queue context."""
        # Prepare queue context for the dialog
        queue_info = self.file_queue.get_current_file_info()
        queue_context = {
            'auto_tag': file_info['auto_tag'],
            'skip_rows': file_info['skip_rows'],
            'current_index': queue_info['current_index'],
            'total_files': queue_info['total_files'],
            'processed_count': queue_info['processed_count'],
            'failed_count': queue_info['failed_count'],
            'skipped_count': queue_info['skipped_count'],
            'skip_callback': self._on_queue_skip,
            'cancel_callback': self._cancel_queue_processing
        }
        
        # Create and show the unified preview dialog
        preview_dialog = FilePreviewDialog(
            parent=self.root, 
            file_path=file_info['file_path'], 
            on_load_callback=self._handle_queue_file_load,
            mode='verification',  #Specify verification mode
            queue_context=queue_context  #Pass queue context
        )
        preview_dialog.show()

    def _handle_queue_file_load(self, file_path: str, tag: str, skip_rows: int):
        """Handle queue file loading (simplified using unified dialog)."""
        try:
            dataset_id = self.dataset_manager.add_dataset(
                file_path=file_path,
                tag=tag,
                notes="",
                skip_rows=skip_rows
            )
            
            if dataset_id:
                self.file_queue.mark_current_processed(dataset_id)
                self.dataset_manager.set_active_dataset(dataset_id)
                
                # Update UI
                self._update_dataset_ui()
                self._load_active_dataset_settings()
                self._update_column_combos()
                self._update_stats_display()
                self.plot_button.config(state='normal')
                self._update_report_button_state()
                
                # Update scroll region after adding dataset
                self.scrollable_frame.update_scroll_region()
                
                logger.info(f"Successfully loaded queue file: {tag}")
                self._process_current_queue_file()  # Continue with next file
                
            else:
                self.file_queue.mark_current_failed("Failed to load file into dataset manager")
                result = messagebox.askyesno(
                    "Load Failed", 
                    f"Failed to load {tag}.\n\nContinue with remaining files?"
                )
                
                if result:
                    self._process_current_queue_file()
                else:
                    self._cancel_queue_processing()
                    
        except Exception as e:
            error_msg = f"Error loading file: {str(e)}"
            self.file_queue.mark_current_failed(error_msg)
            
            result = messagebox.askyesno(
                "Load Error", 
                f"Error loading {tag}:\n{error_msg}\n\nContinue with remaining files?"
            )
            
            if result:
                self._process_current_queue_file()
            else:
                self._cancel_queue_processing()

    def _on_queue_skip(self):
        """Handle skip button in queue processing."""
        self.file_queue.skip_current_file("User skipped during preview")
        self._process_current_queue_file()

    def _finish_queue_processing(self):
        """Finish queue processing and show summary."""
        summary = self.file_queue.get_summary()
        
        summary_text = f"Queue Processing Complete!\n\n"
        summary_text += f"Total files: {summary['total_files']}\n"
        summary_text += f"Successfully loaded: {summary['processed']}\n"
        summary_text += f"Failed: {summary['failed']}\n"
        summary_text += f"Skipped: {summary['skipped']}\n"
        summary_text += f"Success rate: {summary['success_rate']:.1f}%"
        
        messagebox.showinfo("Queue Complete", summary_text)
        self._update_queue_status()

    def _cancel_queue_processing(self):
        """Cancel queue processing."""
        self.file_queue.clear_queue()
        self._update_queue_status()
        messagebox.showinfo("Cancelled", "Queue processing was cancelled.")

    def _update_queue_status(self):
        """Update the queue status display."""
        if not self.file_queue.has_more_files() and len(self.file_queue.files) == 0:
            self.queue_status_label.config(text="")
            return
        
        info = self.file_queue.get_current_file_info()
        
        if info['is_complete']:
            self.queue_status_label.config(text="Queue processing complete")
        elif info['has_current_file']:
            current_file = self.file_queue.get_current_file()
            status_text = f"Queue: {info['current_index'] + 1}/{info['total_files']} - {current_file['filename']}"
            if info['processed_count'] > 0 or info['failed_count'] > 0 or info['skipped_count'] > 0:
                status_text += f" (P:{info['processed_count']} F:{info['failed_count']} S:{info['skipped_count']})"
            self.queue_status_label.config(text=status_text)
        else:
            self.queue_status_label.config(text=f"Queue ready: {info['total_files']} files")
    
    # REMOVED: _show_enhanced_queue_preview_dialog() method - ~80 lines deleted
    # REMOVED: _validate_float_input_for_dialog() method - ~15 lines deleted
    
    # === DATASET MANAGEMENT METHODS (MOSTLY UNCHANGED) ===
    
    def _update_dataset_ui(self):
        """Update all dataset-related UI elements."""
        self._update_dataset_treeview()
        self._update_compact_dataset_info()
        self._update_navigation_buttons()
        self._update_tag_editor()
    
    def _update_dataset_treeview(self):
        """Update the dataset treeview with current datasets in manager order."""
        # Clear existing items
        for item in self.dataset_treeview.get_children():
            self.dataset_treeview.delete(item)
        
        # Use the manager's internal order (not get_all_datasets which might sort)
        datasets_in_order = list(self.dataset_manager.datasets.values())
        active_id = self.dataset_manager.active_dataset_id
        
        for i, dataset in enumerate(datasets_in_order):
            # Determine filename display
            if dataset['filename'] != 'Generated Data':
                filename_display = dataset['filename']
            else:
                filename_display = "Generated Data"
            
            # Insert item with tag and filename in separate columns
            item_id = self.dataset_treeview.insert(
                '', 'end',
                text='●',  # Bullet point in the tree column
                values=(dataset['tag'], filename_display),
                tags=('dataset',)
            )
            
            # Select and show active dataset
            if dataset['id'] == active_id:
                self.dataset_treeview.selection_set(item_id)
                self.dataset_treeview.see(item_id)
        
        # Configure tag styling
        self.dataset_treeview.tag_configure('dataset', foreground='black')
    
    def _update_compact_dataset_info(self):
        """Update the compact dataset info display."""
        active_dataset = self.dataset_manager.get_active_dataset()
        
        if active_dataset:
            # Build compact info string
            info_parts = []
            
            # Filename
            if active_dataset['filename'] != 'Generated Data':
                info_parts.append(f"File: {active_dataset['filename']}")
            else:
                info_parts.append("File: Generated Data")
            
            instrument_type = active_dataset['data_processor'].get_instrument_type()
            info_parts.append(f"Instrument: {instrument_type}")
            
            # Notes preview (first 50 chars if present)
            if active_dataset['notes']:
                notes_preview = active_dataset['notes'][:50]
                if len(active_dataset['notes']) > 50:
                    notes_preview += "..."
                info_parts.append(f"Notes: {notes_preview}")
            
            # Data counts
            stats = active_dataset['data_processor'].get_data_stats()
            if 'total_rows' in stats:
                info_parts.append(f"Rows: {stats['total_rows']}")
            
            info_text = "\n".join(info_parts)
            self.compact_info_label.config(text=info_text)
        else:
            self.compact_info_label.config(text="No datasets loaded")

    def _update_navigation_buttons(self):
        """Update the state of navigation and action buttons."""
        has_datasets = self.dataset_manager.has_datasets()
        
        # Mode-aware navigation button updates
        self._update_navigation_buttons_for_mode()
        
        # Action buttons
        self.edit_notes_btn.config(state='normal' if has_datasets else 'disabled')
        self.remove_dataset_btn.config(state='normal' if has_datasets else 'disabled')
    
    def _on_dataset_select(self, event):
        """Handle dataset selection from treeview."""
        selection = self.dataset_treeview.selection()
        if selection:
            # Get the selected item
            selected_item = selection[0]
            
            # Get all datasets and find the matching one by index
            datasets = self.dataset_manager.get_all_datasets()
            
            # Get the index of the selected item in the treeview
            all_items = self.dataset_treeview.get_children()
            try:
                selected_index = all_items.index(selected_item)
                
                if selected_index < len(datasets):
                    selected_dataset = datasets[selected_index]
                    self.dataset_manager.set_active_dataset(selected_dataset['id'])
                    
                    self._load_active_dataset_settings()
                    self._update_compact_dataset_info()
                    self._update_tag_editor()
                    self._update_column_combos()
                    self._update_stats_display()
                    
                    # Update plot if canvas exists and we have data
                    if hasattr(self, 'canvas') and self.dataset_manager.get_active_dataset():
                        self._update_plot()
            
            except (ValueError, IndexError) as e:
                logger.error(f"Error handling dataset selection: {e}")

    def previous_dataset(self):
        """Navigate to previous dataset."""
        prev_id = self.dataset_manager.get_previous_dataset_id()
        if prev_id:
            self.dataset_manager.set_active_dataset(prev_id)
            self._load_active_dataset_settings()
            self._update_dataset_ui()
            self._update_column_combos()
            self._update_stats_display()
            
            if hasattr(self, 'canvas'):
                self._update_plot()
    
    def next_dataset(self):
        """Navigate to next dataset."""
        next_id = self.dataset_manager.get_next_dataset_id()
        if next_id:
            self.dataset_manager.set_active_dataset(next_id)
            self._load_active_dataset_settings()
            self._update_dataset_ui()
            self._update_column_combos()
            self._update_stats_display()
            
            if hasattr(self, 'canvas'):
                self._update_plot()
    
    def edit_dataset_notes(self):
        """Edit the notes of the active dataset."""
        active_dataset = self.dataset_manager.get_active_dataset()
        if not active_dataset:
            return
        
        # Create a dialog for multi-line notes editing
        self._show_notes_editor(active_dataset)
    
    def _show_notes_editor(self, dataset):
        """Show a dialog for editing dataset notes."""
        notes_window = tk.Toplevel(self.root)
        notes_window.title(f"Edit Notes - {dataset['tag']}")
        notes_window.geometry("500x300")
        notes_window.grab_set()
        
        # Notes text area
        ttk.Label(notes_window, text="Dataset Notes:").pack(anchor='w', padx=10, pady=(10,5))
        
        text_frame = ttk.Frame(notes_window)
        text_frame.pack(fill='both', expand=True, padx=10, pady=5)
        
        notes_text = tk.Text(text_frame, wrap='word')
        scrollbar = ttk.Scrollbar(text_frame, orient='vertical', command=notes_text.yview)
        notes_text.configure(yscrollcommand=scrollbar.set)
        
        notes_text.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')
        
        # Insert current notes
        notes_text.insert(1.0, dataset['notes'])
        
        # Buttons
        button_frame = ttk.Frame(notes_window)
        button_frame.pack(fill='x', padx=10, pady=10)
        
        def save_notes():
            new_notes = notes_text.get(1.0, tk.END).strip()
            self.dataset_manager.update_dataset_notes(dataset['id'], new_notes)
            self._update_dataset_ui()
            notes_window.destroy()
        
        ttk.Button(button_frame, text="Save", command=save_notes).pack(side='right', padx=(5,0))
        ttk.Button(button_frame, text="Cancel", command=notes_window.destroy).pack(side='right')
        
        # Focus on text area
        notes_text.focus_set()
    
    def _on_gaussian_toggle(self):
        """Handle Gaussian curve fitting toggle change."""
        # Save settings to active dataset
        self._save_active_dataset_settings()
        
        # If we have a current plot, update it
        if hasattr(self, 'canvas') and self.dataset_manager.get_active_dataset():
            self._update_plot()

    def show_gaussian_info(self):
        """Show detailed Gaussian fit information in a dialog."""
        if not hasattr(self.plotter, 'get_last_gaussian_fit'):
            messagebox.showinfo("Info", "Gaussian fitting not available in current plotter.")
            return
        
        fit_result = self.plotter.get_last_gaussian_fit()
        if not fit_result or not fit_result.get('success'):
            messagebox.showinfo("No Fit Data", "No successful Gaussian fit available.\n\nCreate a plot with Gaussian fitting enabled first.")
            return
        
        self._show_gaussian_fit_dialog(fit_result)

    def _show_gaussian_fit_dialog(self, fit_result: dict):
        """Show detailed Gaussian fit results in a dialog window."""
        dialog = tk.Toplevel(self.root)
        dialog.title("Gaussian Fit Results")
        dialog.geometry("500x600")
        dialog.grab_set()  # Make it modal
        
        # Center the dialog
        dialog.transient(self.root)
        dialog.update_idletasks()
        x = (dialog.winfo_screenwidth() // 2) - 250
        y = (dialog.winfo_screenheight() // 2) - 300
        dialog.geometry(f"500x600+{x}+{y}")
        
        # Main frame with padding
        main_frame = ttk.Frame(dialog, padding=20)
        main_frame.pack(fill='both', expand=True)
        
        # Title
        title_label = ttk.Label(main_frame, text="Gaussian Curve Fit Analysis", 
                            font=('TkDefaultFont', 12, 'bold'))
        title_label.pack(anchor='w', pady=(0, 15))
        
        # Create notebook for organized display
        notebook = ttk.Notebook(main_frame)
        notebook.pack(fill='both', expand=True, pady=(0, 15))
        
        # === Parameters Tab ===
        params_frame = ttk.Frame(notebook, padding=10)
        notebook.add(params_frame, text="Parameters")
        
        params = fit_result['fitted_params']
        param_errors = fit_result['param_errors']
        
        # Parameters with uncertainties
        params_data = [
            ['Peak Location (μ)', f"{params['mean']:.4f} ± {param_errors['mean_error']:.4f}"],
            ['Standard Deviation (σ)', f"{params['stddev']:.4f} ± {param_errors['stddev_error']:.4f}"],
            ['Peak Height (A)', f"{params['amplitude']:.2f} ± {param_errors['amplitude_error']:.2f}"],
            ['Full Width Half Max', f"{fit_result['statistics']['fwhm']:.4f}"],
            ['Area Under Curve', f"{fit_result['statistics']['area_under_curve']:.2f}"],
            ['Mode Bin Center', f"{fit_result['statistics']['mode_bin_center']:.4f}"],
            ['Mode Bin Index', f"{fit_result['statistics']['mode_bin_index']}"]
        ]
        
        for i, (param_name, param_value) in enumerate(params_data):
            ttk.Label(params_frame, text=f"{param_name}:", 
                    font=FONT_INSTRUMENT_TYPE).grid(row=i, column=0, sticky='w', pady=2)
            ttk.Label(params_frame, text=param_value, 
                    font=FONT_PREVIEW_TEXT).grid(row=i, column=1, sticky='w', padx=(20, 0), pady=2)
        
        # === Quality Tab ===
        quality_frame = ttk.Frame(notebook, padding=10)
        notebook.add(quality_frame, text="Fit Quality")
        
        quality = fit_result['fit_quality']
        
        # UPDATED: Determine three-tier fit quality assessment
        if hasattr(self.plotter.gaussian_fitter, 'get_fit_quality_category'):
            quality_category = self.plotter.gaussian_fitter.get_fit_quality_category()
            
            if quality_category == 'good':
                quality_status = "✓ Good Fit"
                status_color = 'green'
                explanation = "Excellent agreement between data and Gaussian model"
            elif quality_category == 'okay':
                quality_status = "~ Okay Fit"  
                status_color = 'orange'
                explanation = "Reasonable agreement with some deviations"
            else:  # poor
                quality_status = "⚠ Poor Fit"
                status_color = 'red'
                explanation = "Significant deviations from Gaussian model"
        else:
            # Fallback to old two-tier system
            is_good_fit = (quality['r_squared'] >= 0.80 and 
                        quality['reduced_chi_squared'] <= 2.0)
            quality_status = "✓ Good Fit" if is_good_fit else "⚠ Poor Fit"
            status_color = 'green' if is_good_fit else 'red'
            explanation = ""
        
        # Display status with color
        status_label = tk.Label(quality_frame, text=quality_status,
                            font=FONT_STATUS_LARGE,
                            fg=status_color)
        status_label.pack(anchor='w', pady=(0, 5))
        
        # Add explanation text
        if explanation:
            explanation_label = tk.Label(quality_frame, text=explanation,
                                    font=('TkDefaultFont', 9),
                                    fg='gray')
            explanation_label.pack(anchor='w', pady=(0, 10))
        
        quality_data = [
            ['R-squared (R²)', f"{quality['r_squared']:.6f}"],
            ['Root Mean Square Error', f"{quality['rmse']:.4f}"],
            ['Mean Absolute Error', f"{quality['mae']:.4f}"],
            ['Normalized RMSE (%)', f"{quality['nrmse_percent']:.2f}%"],
            ['Chi-squared (χ²)', f"{quality['chi_squared']:.4f}"],
            ['Reduced Chi-squared', f"{quality['reduced_chi_squared']:.4f}"],
            ['Degrees of Freedom', f"{quality['degrees_of_freedom']}"]
        ]
        
        for i, (metric_name, metric_value) in enumerate(quality_data):
            ttk.Label(quality_frame, text=f"{metric_name}:", 
                    font=FONT_FILE_NAME).grid(row=i+1, column=0, sticky='w', pady=2)
            ttk.Label(quality_frame, text=metric_value, 
                    font=FONT_PREVIEW_TEXT).grid(row=i+1, column=1, sticky='w', padx=(20, 0), pady=2)
        
        # === Data Tab ===
        data_frame = ttk.Frame(notebook, padding=10)
        notebook.add(data_frame, text="Data Summary")
        
        # Data summary
        original_data = fit_result['original_data']
        data_info = [
            ['Data Points Used', f"{len(original_data['x'])}"],
            ['X Range', f"{np.min(original_data['x']):.3f} to {np.max(original_data['x']):.3f}"],
            ['Y Range', f"{np.min(original_data['y']):.3f} to {np.max(original_data['y']):.3f}"],
            ['Peak X Location', f"{original_data['x'][np.argmax(original_data['y'])]:.3f}"],
            ['Peak Y Value', f"{np.max(original_data['y']):.3f}"]
        ]
        
        for i, (info_name, info_value) in enumerate(data_info):
            ttk.Label(data_frame, text=f"{info_name}:", 
                    font=FONT_FILE_NAME).grid(row=i, column=0, sticky='w', pady=2)
            ttk.Label(data_frame, text=info_value, 
                    font=FONT_PREVIEW_TEXT).grid(row=i, column=1, sticky='w', padx=(20, 0), pady=2)
        
        # === Equation Tab ===
        equation_frame = ttk.Frame(notebook, padding=10)
        notebook.add(equation_frame, text="Equation")
        
        # Gaussian equation with fitted parameters
        equation_text = f"""Fitted Gaussian Equation:

    y = A × exp(-((x - μ)² / (2σ²)))

    Where:
    A = {params['amplitude']:.4f}  (amplitude)
    μ = {params['mean']:.4f}      (mean)
    σ = {params['stddev']:.4f}     (standard deviation)

    Substituted:
    y = {params['amplitude']:.4f} × exp(-((x - {params['mean']:.4f})² / (2 × {params['stddev']:.4f}²)))

    68% of data lies within μ ± σ = [{params['mean'] - params['stddev']:.3f}, {params['mean'] + params['stddev']:.3f}]
    95% of data lies within μ ± 2σ = [{params['mean'] - 2*params['stddev']:.3f}, {params['mean'] + 2*params['stddev']:.3f}]"""
        
        equation_label = tk.Text(equation_frame, wrap='word', height=15, width=60, 
                                font=FONT_PREVIEW_TEXT)
        equation_label.insert(1.0, equation_text)
        equation_label.config(state='disabled')
        equation_label.pack(fill='both', expand=True)
        
        # Close button
        close_button = ttk.Button(main_frame, text="Close", command=dialog.destroy)
        close_button.pack(anchor='e')
        
        # Focus on the dialog
        dialog.focus_set()

    def show_help_dialog(self):
        """Show help dialog with usage information."""
        help_window = tk.Toplevel(self.root)
        help_window.title("Dataset Management Help")
        help_window.geometry("600x500")
        help_window.grab_set()  # Make it modal
        
        # Center the dialog
        help_window.transient(self.root)
        help_window.update_idletasks()
        x = (help_window.winfo_screenwidth() // 2) - 300
        y = (help_window.winfo_screenheight() // 2) - 250
        help_window.geometry(f"600x500+{x}+{y}")
        
        # Create main frame with padding
        main_frame = ttk.Frame(help_window)
        main_frame.pack(fill='both', expand=True, padx=20, pady=20)
        
        # Title
        title_label = ttk.Label(main_frame, text="Dataset Management Help", 
                               font=('TkDefaultFont', 14, 'bold'))
        title_label.pack(anchor='w', pady=(0, 15))
        
        # Create scrollable text area for help content
        text_frame = ttk.Frame(main_frame)
        text_frame.pack(fill='both', expand=True, pady=(0, 15))
        
        help_text = tk.Text(text_frame, wrap='word', font=('TkDefaultFont', 10))
        scrollbar = ttk.Scrollbar(text_frame, orient='vertical', command=help_text.yview)
        help_text.configure(yscrollcommand=scrollbar.set)
        
        help_text.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')
        
        # Help content
        help_content = """DATASET MANAGEMENT OVERVIEW

This section helps you manage multiple datasets in the Particle Data Analyzer.

LOADING DATA:
• Use "Load for Calibration" for single file analysis
• Use "Load for Verification" for multiple file comparison
• The enhanced file preview dialog now includes dynamic preview line controls
• Preview lines automatically adjust based on detected instrument type
• Each dataset gets a unique color and appears in the "Loaded Datasets" list

PREVIEW ENHANCEMENTS:
• Preview line controls work in both Calibration and Verification modes
• Instrument-aware defaults
• Real-time instrument type detection and hints
• Refresh preview button updates content and re-detects instrument type

DATASET LIST:
• Shows all loaded datasets with bead size and filename
• Click any dataset to make it active
• The active dataset is highlighted and used for analysis

BEAD SIZE EDITING:
• Edit the bead size directly in the text field
• Press Enter or click the save button (💾) to save changes
• Only numeric values are accepted

DATASET NAVIGATION:
• Use "Previous Dataset" and "Next Dataset" buttons in the plot area
• These buttons help you quickly switch between datasets

DATASET ACTIONS:
• Edit Notes: Add detailed information about each dataset
• Remove: Delete a dataset from the collection (cannot be undone)

ANALYSIS MODES:
• Calibration Mode: Optimized for single dataset analysis
• Verification Mode: Supports multiple datasets for comparison

DATA TYPES:
• Pre-aggregated: Data with size and frequency columns
• Raw Measurements: Individual size measurements only

TIPS:
• Preview lines automatically set based on instrument type
• Use meaningful bead sizes to identify your datasets
• Add notes to remember important details about each dataset
• In Verification mode, you can compare multiple datasets
• The plot updates automatically when you switch datasets

KEYBOARD SHORTCUTS:
• Enter: Save bead size changes or refresh preview
• Escape: Close dialogs

For more detailed help, please refer to the user manual or contact support."""
        
        help_text.insert(1.0, help_content)
        help_text.config(state='disabled')  # Make it read-only
        
        # Close button
        close_button = ttk.Button(main_frame, text="Close", command=help_window.destroy)
        close_button.pack(anchor='e')
        
        # Focus on the help window
        help_window.focus_set()
    
    def remove_dataset(self):
        """Remove the active dataset."""
        active_dataset = self.dataset_manager.get_active_dataset()
        if not active_dataset:
            return
        
        # Confirm removal
        result = messagebox.askyesno(
            "Remove Dataset",
            f"Are you sure you want to remove dataset '{active_dataset['tag']}'?\n\nThis action cannot be undone."
        )
        
        if result:
            self.dataset_manager.remove_dataset(active_dataset['id'])
            
            # Update UI
            self._update_dataset_ui()
            
            # Update scroll region after removing dataset
            self.scrollable_frame.update_scroll_region()
            
            # Load new active dataset if available
            if self.dataset_manager.has_datasets():
                self._load_active_dataset_settings()
                self._update_column_combos()
                self._update_stats_display()
                
                # Update plot if one exists
                if hasattr(self, 'canvas'):
                    self._update_plot()
            else:
                # No datasets left
                self._clear_ui_for_no_datasets()
    
    def _clear_ui_for_no_datasets(self):
        """Clear UI elements when no datasets are available."""
        # Clear column combos
        self.size_combo['values'] = []
        self.frequency_combo['values'] = []
        self.size_column_var.set('')
        self.frequency_column_var.set('')
        
        # Clear stats
        self.stats_text.delete(1.0, tk.END)
        self.stats_text.insert(1.0, "No datasets loaded")
        
        # Clear tag editor
        self._update_tag_editor()
        
        # Clear treeview
        for item in self.dataset_treeview.get_children():
            self.dataset_treeview.delete(item)
        
        # Disable plot button
        self.plot_button.config(state='disabled')
        self._update_report_button_state()
        
        # Clear plot if exists
        if hasattr(self, 'canvas'):
            for widget in self.plot_frame.winfo_children():
                # Only destroy plot content, keep navigation buttons
                if widget != self.plot_frame.winfo_children()[0]:  # Keep nav frame
                    widget.destroy()
            if self.current_figure:
                plt.close(self.current_figure)
                self.current_figure = None
            
            # Show the no plot message again
            if not hasattr(self, 'no_plot_label') or not self.no_plot_label.winfo_exists():
                plot_content_frame = ttk.Frame(self.plot_frame)
                plot_content_frame.pack(fill='both', expand=True)
                self.no_plot_label = ttk.Label(plot_content_frame, 
                                              text="No plot to display\nLoad data and click 'Create Plot' to begin",
                                              font=('TkDefaultFont', 10),
                                              foreground='gray',
                                              justify='center')
                self.no_plot_label.pack(expand=True)
        
        # Update plot scroll region after clearing content
        if hasattr(self, 'plot_scrollable_frame'):
            self.root.update_idletasks()  # Ensure widgets are updated
            self.plot_scrollable_frame.update_scroll_region()
        
        # Update scroll region after clearing
        self.scrollable_frame.update_scroll_region()
    
    def _load_active_dataset_settings(self):
        """Load settings from the active dataset."""
        active_dataset = self.dataset_manager.get_active_dataset()
        if not active_dataset:
            return
        
        settings = active_dataset['analysis_settings']
        
        # Load settings into UI variables
        self.data_mode_var.set(settings['data_mode'])
        self.bin_count_var.set(settings['bin_count'])
        self.size_column_var.set(settings['size_column'] or '')
        self.frequency_column_var.set(settings['frequency_column'] or '')
        self.show_stats_lines_var.set(settings['show_stats_lines'])
        self.show_gaussian_fit_var.set(settings.get('show_gaussian_fit', True))

        # Update data processor mode
        data_processor = active_dataset['data_processor']
        data_processor.set_data_mode(settings['data_mode'])
        
        # Update UI elements
        self._update_data_mode_ui()
    
    def _save_active_dataset_settings(self):
        """Save current UI settings to the active dataset."""
        active_dataset = self.dataset_manager.get_active_dataset()
        if not active_dataset:
            return
        
        settings = {
            'data_mode': self.data_mode_var.get(),
            'bin_count': self.bin_count_var.get(),
            'size_column': self.size_column_var.get(),
            'frequency_column': self.frequency_column_var.get(),
            'show_stats_lines': self.show_stats_lines_var.get(),
            'show_gaussian_fit': self.show_gaussian_fit_var.get()
        }

        self.dataset_manager.update_analysis_settings(active_dataset['id'], settings)
    
    
    def _on_data_mode_change(self):
        """Handle data mode change (pre-aggregated vs raw measurements)."""
        active_dataset = self.dataset_manager.get_active_dataset()
        if not active_dataset:
            return
        
        mode = self.data_mode_var.get()
        
        # Update data processor
        active_dataset['data_processor'].set_data_mode(mode)
        
        # Update UI
        self._update_data_mode_ui()
        
        # Save settings
        self._save_active_dataset_settings()
        
        # Update stats display
        self._update_stats_display()
        
        # If we have a current plot, update it
        if hasattr(self, 'canvas') and active_dataset:
            self._update_plot()
    
    def _on_column_change(self, event=None):
        """Handle column selection changes."""
        active_dataset = self.dataset_manager.get_active_dataset()
        if not active_dataset:
            return
        
        # Update data processor with new column selections
        mode = self.data_mode_var.get()
        if mode == 'pre_aggregated':
            active_dataset['data_processor'].set_columns(
                self.size_column_var.get(),
                self.frequency_column_var.get()
            )
        else:  # raw_measurements
            active_dataset['data_processor'].set_columns(
                self.size_column_var.get()
            )
        
        # Save settings
        self._save_active_dataset_settings()
        
        # Update stats
        self._update_stats_display()
        
        # Update plot if one exists
        if hasattr(self, 'canvas'):
            self._update_plot()
    
    def _update_data_mode_ui(self):
        """Update UI elements based on current data mode."""
        mode = self.data_mode_var.get()
        
        if mode == 'raw_measurements':
            # Hide frequency column selector for raw measurements
            self.frequency_label.grid_remove()
            self.frequency_combo.grid_remove()
            # Clear frequency column selection
            self.frequency_column_var.set('')
        else:
            # Show frequency column selector for pre-aggregated data
            self.frequency_label.grid()
            self.frequency_combo.grid()
    
    def _update_column_combos(self):
        """Update the column selection comboboxes."""
        active_dataset = self.dataset_manager.get_active_dataset()
        if not active_dataset:
            self.size_combo['values'] = []
            self.frequency_combo['values'] = []
            return
        
        columns = active_dataset['data_processor'].get_columns()
        
        self.size_combo['values'] = columns
        self.frequency_combo['values'] = columns
        
        # Set default selections if auto-detected
        data_processor = active_dataset['data_processor']
        if data_processor.size_column:
            self.size_column_var.set(data_processor.size_column)
        if data_processor.frequency_column:
            self.frequency_column_var.set(data_processor.frequency_column)
    
    def _update_stats_display(self):
        """Update the statistics display."""
        active_dataset = self.dataset_manager.get_active_dataset()
        if not active_dataset:
            self.stats_text.delete(1.0, tk.END)
            self.stats_text.insert(1.0, "No active dataset")
            return
        
        stats = active_dataset['data_processor'].get_data_stats()
        
        self.stats_text.delete(1.0, tk.END)
        
        # Dataset info
        stats_str = f"Dataset: {active_dataset['tag']}\n"
        stats_str += f"File: {active_dataset['filename']}\n"
        stats_str += f"Instrument: {stats.get('instrument_type', 'Unknown')}\n"
        stats_str += f"Rows: {stats.get('total_rows', 'N/A')}\n"
        stats_str += f"Columns: {stats.get('total_columns', 'N/A')}\n"
        stats_str += f"Mode: {stats.get('data_mode', 'N/A')}\n"
        
        if 'size_min' in stats:
            stats_str += f"\nSize Range:\n"
            stats_str += f"  Min: {stats['size_min']:.3f}\n"
            stats_str += f"  Max: {stats['size_max']:.3f}\n"
            stats_str += f"  Mean: {stats['size_mean']:.3f}\n"
            
            # Add mode-specific stats
            if stats.get('data_mode') == 'raw_measurements':
                if 'unique_measurements' in stats:
                    stats_str += f"\nMeasurements:\n"
                    stats_str += f"  Total: {stats['total_measurements']}\n"
                    stats_str += f"  Unique: {stats['unique_measurements']}\n"
            elif stats.get('data_mode') == 'pre_aggregated':
                if 'total_frequency' in stats:
                    stats_str += f"\nFrequency:\n"
                    stats_str += f"  Total: {stats['total_frequency']:.0f}\n"
                    stats_str += f"  Mean: {stats['frequency_mean']:.2f}\n"
        
        self.stats_text.insert(1.0, stats_str)
    
    def _on_bin_entry_change(self, event):
        """Handle bin count entry field changes."""
        try:
            bin_count = int(self.bin_count_var.get())
            
            # Validate and constrain the value
            if bin_count < MIN_BIN_COUNT:
                bin_count = MIN_BIN_COUNT
                self.bin_count_var.set(bin_count)
            elif bin_count > MAX_BIN_COUNT:
                bin_count = MAX_BIN_COUNT
                self.bin_count_var.set(bin_count)
            
            # Save settings
            self._save_active_dataset_settings()
            
            # Update plot if we have data
            if hasattr(self, 'canvas') and self.dataset_manager.get_active_dataset():
                self._update_plot()
                
        except (ValueError, tk.TclError):
            # Invalid entry - reset to current slider value or default
            self.bin_count_var.set(DEFAULT_BIN_COUNT)
    
    def _on_stats_toggle(self):
        """Handle statistical lines toggle change."""
        # Save settings
        self._save_active_dataset_settings()
        
        # If we have a current plot, update it
        if hasattr(self, 'canvas') and self.dataset_manager.get_active_dataset():
            self._update_plot()
    
    def create_plot(self):
        """Create and display the histogram plot."""
        active_dataset = self.dataset_manager.get_active_dataset()
        if not active_dataset:
            messagebox.showerror("Error", "No active dataset to plot.")
            return
        
        data_processor = active_dataset['data_processor']
        
        # Update data processor with current settings
        mode = self.data_mode_var.get()
        data_processor.set_data_mode(mode)
        
        # Update column selections
        if mode == 'pre_aggregated':
            data_processor.set_columns(
                self.size_column_var.get(),
                self.frequency_column_var.get()
            )
        else:  # raw_measurements
            data_processor.set_columns(
                self.size_column_var.get()
            )
        
        size_data = data_processor.get_size_data()
        frequency_data = data_processor.get_frequency_data()
        
        if size_data is None:
            messagebox.showerror("Error", "Please select a valid size column.")
            return
        
        # Create plot title with dataset info
        plot_title = f"Particle Size Distribution - {active_dataset['tag']}"
        
        # Create the plot
        figure = self.plotter.create_histogram(
            size_data, frequency_data, self.bin_count_var.get(),
            title=plot_title,
            show_stats_lines=self.show_stats_lines_var.get(),
            data_mode=mode,
            show_gaussian_fit=self.show_gaussian_fit_var.get()
        )
        
        if figure is not None:
            self.current_figure = figure  # Store reference to current figure
            self._display_plot(figure)
            self._update_report_button_state()  # Enable report button when plot is created
            
            # Save settings
            self._save_active_dataset_settings()
        else:
            messagebox.showerror("Error", "Failed to create plot.")
    
    def _update_plot(self):
        """Update the existing plot with new bin count or settings."""
        if not hasattr(self, 'canvas'):
            return
        
        active_dataset = self.dataset_manager.get_active_dataset()
        if not active_dataset:
            return
        
        data_processor = active_dataset['data_processor']
        size_data = data_processor.get_size_data()
        frequency_data = data_processor.get_frequency_data()
        
        if size_data is not None:
            mode = self.data_mode_var.get()
            plot_title = f"Particle Size Distribution - {active_dataset['tag']}"
            
            figure = self.plotter.create_histogram(
                size_data, frequency_data, self.bin_count_var.get(),
                title=plot_title,
                show_stats_lines=self.show_stats_lines_var.get(),
                data_mode=mode,
                show_gaussian_fit=self.show_gaussian_fit_var.get()
            )
            
            if figure is not None:
                self._display_plot(figure)
                self._update_report_button_state()  # Update report button after plot update
    
    def _display_plot(self, figure):
        """Display the plot in the GUI."""
        # Clear existing plot widgets completely (but keep navigation buttons)
        for widget in self.plot_frame.winfo_children():
            # Only destroy widgets that aren't the navigation frame
            if widget != self.plot_frame.winfo_children()[0]:  # Keep the first child (nav frame)
                widget.destroy()
        
        # Hide the no plot label if it exists
        if hasattr(self, 'no_plot_label'):
            self.no_plot_label.destroy()
        
        # Clear any existing matplotlib figures
        if hasattr(self, 'canvas'):
            if self.current_figure and self.current_figure != figure:
                # Only close if it's a different figure than the one we're displaying
                plt.close(self.current_figure)
            del self.canvas
        
        # Create new canvas with the figure
        self.canvas = FigureCanvasTkAgg(figure, self.plot_frame)
        self.current_figure = figure  # Update our reference
        self.canvas.draw()
        
        # Pack the canvas widget
        canvas_widget = self.canvas.get_tk_widget()
        canvas_widget.pack(fill='both', expand=True)
        
        # Add toolbar
        toolbar = NavigationToolbar2Tk(self.canvas, self.plot_frame)
        toolbar.update()
        
        # Force update of scroll region after matplotlib content is added
        self.root.update_idletasks()  # Ensure all widgets are rendered
        self.plot_scrollable_frame.update_scroll_region()
        
        # Debug: Print scroll region info
        canvas = self.plot_scrollable_frame.canvas
        scroll_region = canvas.cget('scrollregion')
        canvas_height = canvas.winfo_height()
        logger.info(f"Plot scroll region: {scroll_region}, canvas height: {canvas_height}")
    
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

    def generate_report(self):
        """Generate a PDF report with current analysis."""
        if not REPORTS_AVAILABLE:
            messagebox.showerror("Error", "ReportLab is not installed. Please install it with: pip install reportlab")
            return
        
        # Check mode restriction
        if self.analysis_mode_var.get() == 'calibration':
            messagebox.showwarning(
                "Mode Restriction", 
                "Report generation is only available in Verification mode.\n\n"
                "Switch to Verification mode to generate comprehensive analysis reports."
            )
            return
        
        if not hasattr(self, 'canvas') or not self.current_figure:
            messagebox.showerror("Error", "Please create a plot first before generating a report.")
            return
        
        active_dataset = self.dataset_manager.get_active_dataset()
        if not active_dataset:
            messagebox.showerror("Error", "No active dataset for report generation.")
            return
        
        # Get save location from user
        file_path = filedialog.asksaveasfilename(
            title="Save Report As",
            defaultextension=".pdf",
            filetypes=[("PDF files", "*.pdf"), ("All files", "*.*")]
        )
        
        if not file_path:
            return  # User cancelled
        
        try:
            # Collect current analysis data
            data_stats = active_dataset['data_processor'].get_data_stats()
            
            # Collect analysis parameters (including mode information)
            analysis_params = {
                'analysis_mode': self.analysis_mode_var.get(),
                'data_mode': self.data_mode_var.get(),
                'bin_count': self.bin_count_var.get(),
                'size_column': self.size_column_var.get(),
                'frequency_column': self.frequency_column_var.get(),
                'skip_rows': active_dataset['skip_rows'],
                'show_stats_lines': self.show_stats_lines_var.get()
            }
            
            # File information
            file_info = {
                'filename': active_dataset['filename'],
                'dataset_tag': active_dataset['tag'],
                'dataset_notes': active_dataset['notes'],
                'generated_at': self._get_current_timestamp()
            }
            
            # Generate the report
            success = self.report_template.create_report(
                output_path=file_path,
                plot_figure=self.current_figure,
                data_stats=data_stats,
                analysis_params=analysis_params,
                file_info=file_info
            )
            
            if success:
                messagebox.showinfo("Success", f"Report generated successfully!\nSaved to: {file_path}")
            else:
                messagebox.showerror("Error", "Failed to generate report. Check console for details.")
                
        except Exception as e:
            messagebox.showerror("Error", f"Failed to generate report: {str(e)}")
    
    def _get_current_timestamp(self):
        """Get current timestamp for report."""
        from datetime import datetime
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    def _update_report_button_state(self):
        """Update the report button state based on available data, plot, and mode."""
        self._update_report_button_state_for_mode()
        if hasattr(self, 'gaussian_info_btn'):
            # Enable Gaussian info button if we have a plot with Gaussian fit
            has_gaussian_fit = (hasattr(self, 'canvas') and 
                            hasattr(self.plotter, 'get_last_gaussian_fit') and
                            self.plotter.get_last_gaussian_fit() is not None)
            self.gaussian_info_btn.config(state='normal' if has_gaussian_fit else 'disabled')

    def _on_treeview_button_press(self, event):
        """Handle mouse button press on treeview - start drag operation."""
        widget = event.widget
        item = widget.identify_row(event.y)
        
        # Reset cursor first
        widget.configure(cursor="")
        
        if item:
            # Store drag information
            self.drag_item = item
            self.drag_start_y = event.y
            
            # Select the item being dragged if it's not already selected
            if item not in widget.selection():
                widget.selection_set(item)
                # Also trigger the selection handler to make this dataset active
                self._on_dataset_select(event)
        else:
            # Clear drag if clicking on empty space
            self.drag_item = None
            self.drag_start_y = None

    def _on_treeview_drag_motion(self, event):
        """Handle mouse motion during drag - provide visual feedback."""
        if self.drag_item is None:
            return
        
        # Check if we've moved enough to start dragging (prevent accidental drags)
        if self.drag_start_y is not None and abs(event.y - self.drag_start_y) < 5:
            return
        
        widget = event.widget
        target_item = widget.identify_row(event.y)
        
        # Change cursor to indicate drag operation
        if target_item and target_item != self.drag_item:
            widget.configure(cursor="hand2")
        else:
            widget.configure(cursor="")

    def _on_treeview_button_release(self, event):
        """Handle mouse button release - complete drag operation."""
        widget = event.widget
        
        # Always reset cursor
        widget.configure(cursor="")
        
        if self.drag_item is None:
            return
        
        target_item = widget.identify_row(event.y)
        
        # Only reorder if we have a valid target that's different from drag item
        if target_item and target_item != self.drag_item:
            # Check if we actually moved enough to constitute a drag
            if self.drag_start_y is not None and abs(event.y - self.drag_start_y) >= 5:
                self._reorder_datasets(self.drag_item, target_item, event.y)
        
        # Clean up drag state
        self.drag_item = None
        self.drag_start_y = None

    def _reorder_datasets(self, drag_item, target_item, drop_y):
        """Reorder datasets in both treeview and dataset manager."""
        try:
            # Get the dataset IDs from the treeview items BY LOOKING UP THE ACTUAL DATA
            all_items = list(self.dataset_treeview.get_children())
            
            # Create a mapping from treeview items to dataset IDs
            item_to_dataset_id = {}
            all_datasets = self.dataset_manager.get_all_datasets()
            
            for i, item in enumerate(all_items):
                values = self.dataset_treeview.item(item, 'values')
                if values and i < len(all_datasets):
                    # Match by tag and filename to find the correct dataset
                    tag, filename = values
                    for dataset in all_datasets:
                        if dataset['tag'] == tag and dataset['filename'] == filename:
                            item_to_dataset_id[item] = dataset['id']
                            break
            
            # Get the actual dataset IDs
            drag_dataset_id = item_to_dataset_id.get(drag_item)
            target_dataset_id = item_to_dataset_id.get(target_item)
            
            if not drag_dataset_id or not target_dataset_id:
                logger.warning("Could not find dataset IDs for drag items")
                return
            
            # Find the indices in the MANAGER's order (not treeview order)
            dataset_ids_ordered = self.dataset_manager.get_dataset_order_by_id()
            
            try:
                drag_index = dataset_ids_ordered.index(drag_dataset_id)
                target_index = dataset_ids_ordered.index(target_dataset_id)
            except ValueError as e:
                logger.error(f"Dataset ID not found in manager: {e}")
                return
            
            # Don't do anything if trying to drop on the same item
            if drag_index == target_index:
                logger.info("Drag and target are the same - no reorder needed")
                return
            
            # Get the dataset info for logging
            drag_dataset = self.dataset_manager.get_dataset(drag_dataset_id)
            target_dataset = self.dataset_manager.get_dataset(target_dataset_id)
            
            logger.info(f"Reordering: moving '{drag_dataset['tag']}' (manager index {drag_index}) near '{target_dataset['tag']}' (manager index {target_index})")
            
            # Determine drop position (above or below target)
            try:
                target_bbox = self.dataset_treeview.bbox(target_item)
                if target_bbox:
                    target_center_y = target_bbox[1] + target_bbox[3] // 2
                    drop_above = drop_y < target_center_y
                else:
                    drop_above = drag_index > target_index  # Default behavior
            except:
                drop_above = drag_index > target_index
            
            logger.info(f"Drop above target: {drop_above}")
            
            # Calculate new position in manager order
            if drag_index < target_index:
                # Dragging DOWN (from earlier position to later position)
                if drop_above:
                    new_position = target_index - 1  # Insert before target
                else:
                    new_position = target_index  # Insert after target (target moves up)
            else:
                # Dragging UP (from later position to earlier position) 
                if drop_above:
                    new_position = target_index  # Insert before target (target moves down)
                else:
                    new_position = target_index + 1  # Insert after target
            
            # Ensure position is within bounds
            new_position = max(0, min(new_position, len(dataset_ids_ordered) - 1))
            
            logger.info(f"Calculated new position in manager: {new_position}")
            
            # Don't do anything if position hasn't actually changed
            if new_position == drag_index:
                logger.info("New position same as old position - no reorder needed")
                return
            
            # Perform the reorder in the dataset manager
            self._reorder_datasets_in_manager(drag_dataset_id, new_position)
            
            # Update the UI (this will rebuild the treeview from the manager's new order)
            self._update_dataset_ui()
            
            # Maintain selection on the moved item
            # We need to find the new treeview item for this dataset
            updated_items = list(self.dataset_treeview.get_children())
            for item in updated_items:
                values = self.dataset_treeview.item(item, 'values')
                if values:
                    tag, filename = values
                    if tag == drag_dataset['tag'] and filename == drag_dataset['filename']:
                        self.dataset_treeview.selection_set(item)
                        self.dataset_treeview.see(item)
                        break
            
            logger.info(f"Successfully reordered datasets from manager position {drag_index} to {new_position}")
            
        except Exception as e:
            logger.error(f"Error reordering datasets: {e}")
            messagebox.showerror("Reorder Error", f"Failed to reorder datasets: {str(e)}")

    def _reorder_datasets_in_manager(self, dataset_id: str, new_position: int):
        """Reorder datasets in the dataset manager."""
        datasets = list(self.dataset_manager.datasets.items())
        
        # Find the dataset to move
        dataset_to_move = None
        old_position = None
        
        for i, (id, dataset) in enumerate(datasets):
            if id == dataset_id:
                dataset_to_move = (id, dataset)
                old_position = i
                break
        
        if dataset_to_move is None:
            raise ValueError(f"Dataset {dataset_id} not found")
        
        # Validate new position bounds
        if new_position < 0:
            new_position = 0
        elif new_position >= len(datasets):
            new_position = len(datasets) - 1
        
        print(f"DEBUG: Moving '{dataset_to_move[1]['tag']}' from position {old_position} to {new_position}")
        
        # Remove from old position
        datasets.pop(old_position)
        
        # Insert at new position
        datasets.insert(new_position, dataset_to_move)
        
        # Rebuild the datasets dictionary in the new order
        new_datasets = {}
        for id, dataset in datasets:
            new_datasets[id] = dataset
        
        # Replace the manager's datasets
        self.dataset_manager.datasets = new_datasets
        
        logger.info(f"Moved dataset {dataset_id} from position {old_position} to {new_position}")

    def debug_dataset_order(self):
        """Debug method to print current dataset order."""
        datasets = self.dataset_manager.get_all_datasets()
        print("=== Current Dataset Order ===")
        for i, dataset in enumerate(datasets):
            print(f"{i}: {dataset['tag']} - {dataset['filename']}")
        print("=============================")
    
    def _on_closing(self):
        """Handle application closing cleanly."""
        try:
            # Close matplotlib figures properly
            if hasattr(self, 'canvas'):
                if self.current_figure:
                    plt.close(self.current_figure)
                del self.canvas
            
            # Close plotter figures
            if hasattr(self.plotter, 'figure') and self.plotter.figure:
                plt.close(self.plotter.figure)
            
            # Close all remaining matplotlib figures
            plt.close('all')
            
            # Destroy the root window
            self.root.quit()
            self.root.destroy()
            
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")
            # Force exit if cleanup fails
            import sys
            sys.exit(0)