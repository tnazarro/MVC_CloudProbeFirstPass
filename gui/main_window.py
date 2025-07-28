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

from core.data_processor import ParticleDataProcessor
from core.dataset_manager import DatasetManager
from core.plotter import ParticlePlotter
from config.constants import SUPPORTED_FILE_TYPES, MIN_BIN_COUNT, MAX_BIN_COUNT, DEFAULT_BIN_COUNT, RANDOM_DATA_BOUNDS
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

        # Initialize core components
        self.dataset_manager = DatasetManager()
        self.plotter = ParticlePlotter()
        self.file_queue = FileQueue()
        
        # GUI variables
        self.bin_count_var = tk.IntVar(value=DEFAULT_BIN_COUNT)
        self.size_column_var = tk.StringVar()
        self.frequency_column_var = tk.StringVar()
        self.random_count_var = tk.IntVar(value=RANDOM_DATA_BOUNDS['default_n'])
        self.distribution_var = tk.StringVar(value='lognormal')
        self.show_stats_lines_var = tk.BooleanVar(value=True)
        self.data_mode_var = tk.StringVar(value='raw_measurements')  # 'pre_aggregated' or 'raw_measurements'
        self.skip_rows_var = tk.IntVar(value=0)
        
        # Analysis mode selection variable (calibration vs verification)
        self.analysis_mode_var = tk.StringVar(value='calibration')
        
        # NEW: Inline tag editing variable
        self.current_tag_var = tk.StringVar()
        self._updating_tag = False  # Flag to prevent recursive updates
        
        # Track current figure for proper cleanup
        self.current_figure = None
        
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
        # Main frame (now for right side only)
        self.main_frame = ttk.Frame(self.root)
        
        # Control frame (left side) - now goes inside scrollable frame
        self.control_frame = ttk.LabelFrame(self.scrollable_frame.scrollable_frame, text="Controls", padding=10)
        
        # === ANALYSIS MODE SELECTION ===
        self.analysis_mode_frame = ttk.LabelFrame(self.control_frame, text="Analysis Mode", padding=5)
        self.analysis_mode_frame.grid(row=0, column=0, columnspan=3, sticky='ew', pady=(0,10))
        
        # Mode radio buttons
        mode_radio_frame = ttk.Frame(self.analysis_mode_frame)
        mode_radio_frame.pack(fill='x')
        
        self.calibration_radio = ttk.Radiobutton(
            mode_radio_frame, 
            text="Calibration", 
            variable=self.analysis_mode_var, 
            value='calibration',
            command=self._on_analysis_mode_change
        )
        self.calibration_radio.pack(side='left', padx=(0,20))
        
        self.verification_radio = ttk.Radiobutton(
            mode_radio_frame, 
            text="Verification", 
            variable=self.analysis_mode_var, 
            value='verification',
            command=self._on_analysis_mode_change
        )
        self.verification_radio.pack(side='left')
        
        # Mode description label
        self.mode_description = ttk.Label(
            self.analysis_mode_frame, 
            text="Calibration: Single dataset analysis for instrument calibration",
            font=('TkDefaultFont', 8),
            foreground='blue'
        )
        self.mode_description.pack(anchor='w', pady=(5,0))
        
        # === FILE LOADING CONTROLS ===
        ttk.Label(self.control_frame, text="Data File:").grid(row=1, column=0, sticky='w', pady=2)

        # Single smart file loading button (full width)
        self.smart_load_button = ttk.Button(
            self.control_frame, 
            text="Load CSV File", 
            command=self.smart_load_files
        )
        self.smart_load_button.grid(row=1, column=1, columnspan=2, sticky='ew', pady=2)
        
        # Queue status display
        self.queue_status_frame = ttk.Frame(self.control_frame)
        self.queue_status_frame.grid(row=2, column=0, columnspan=3, sticky='ew', pady=2)
        
        self.queue_status_label = ttk.Label(self.queue_status_frame, text="", font=('TkDefaultFont', 8))
        self.queue_status_label.pack(anchor='w')
        
        # === LOADED DATASETS FRAME (MOVED HERE - previously in middle column) ===
        self.dataset_list_frame = ttk.LabelFrame(self.control_frame, text="Loaded Datasets", padding=5)
        self.dataset_list_frame.grid(row=3, column=0, columnspan=3, sticky='ew', pady=(10,10))
        
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
            font=('TkDefaultFont', 8),
            wraplength=250,  # Adjusted for left column width
            justify='left'
        )
        self.compact_info_label.pack(anchor='w', fill='x')
        
        # === RANDOM DATA GENERATION ===
        ttk.Separator(self.control_frame, orient='horizontal').grid(row=4, column=0, columnspan=3, sticky='ew', pady=5)

        ttk.Label(self.control_frame, text="Generate Random Data:").grid(row=5, column=0, sticky='w', pady=2)

        # Random data controls frame
        random_frame = ttk.Frame(self.control_frame)
        random_frame.grid(row=6, column=0, columnspan=3, sticky='ew', pady=2)
        
        ttk.Label(random_frame, text="Points:").grid(row=0, column=0, sticky='w')
        self.random_count_entry = ttk.Entry(random_frame, textvariable=self.random_count_var, width=8)
        self.random_count_entry.grid(row=0, column=1, padx=5)
        
        ttk.Label(random_frame, text="Distribution:").grid(row=0, column=2, sticky='w', padx=(10,0))
        self.distribution_combo = ttk.Combobox(random_frame, textvariable=self.distribution_var, 
                                             values=['lognormal', 'normal', 'uniform'], 
                                             state='readonly', width=10)
        self.distribution_combo.grid(row=0, column=3, padx=5)
        
        self.generate_button = ttk.Button(random_frame, text="Generate", command=self.generate_random_data)
        self.generate_button.grid(row=0, column=4, padx=5)
        
        # === DATA ANALYSIS CONTROLS ===
        ttk.Separator(self.control_frame, orient='horizontal').grid(row=7, column=0, columnspan=3, sticky='ew', pady=5)
        
        # Data mode selection
        ttk.Label(self.control_frame, text="Data Type:").grid(row=8, column=0, sticky='w', pady=2)
        
        data_mode_frame = ttk.Frame(self.control_frame)
        data_mode_frame.grid(row=8, column=1, columnspan=2, sticky='ew', pady=2)
        
        self.pre_agg_radio = ttk.Radiobutton(data_mode_frame, text="Pre-aggregated (Size + Frequency)", 
                                           variable=self.data_mode_var, value='pre_aggregated',
                                           command=self._on_data_mode_change)
        self.pre_agg_radio.grid(row=0, column=0, sticky='w')
        
        self.raw_radio = ttk.Radiobutton(data_mode_frame, text="Raw Measurements (Size only)", 
                                       variable=self.data_mode_var, value='raw_measurements',
                                       command=self._on_data_mode_change)
        self.raw_radio.grid(row=1, column=0, sticky='w')
        
        # Column selection
        ttk.Label(self.control_frame, text="Size Column:").grid(row=9, column=0, sticky='w', pady=2)
        self.size_combo = ttk.Combobox(self.control_frame, textvariable=self.size_column_var, 
                                      state='readonly')
        self.size_combo.grid(row=9, column=1, sticky='ew', pady=2)
        self.size_combo.bind('<<ComboboxSelected>>', self._on_column_change)
        
        self.frequency_label = ttk.Label(self.control_frame, text="Frequency Column:")
        self.frequency_label.grid(row=10, column=0, sticky='w', pady=2)
        self.frequency_combo = ttk.Combobox(self.control_frame, textvariable=self.frequency_column_var, 
                                           state='readonly')
        self.frequency_combo.grid(row=10, column=1, sticky='ew', pady=2)
        self.frequency_combo.bind('<<ComboboxSelected>>', self._on_column_change)
        
        # Bin count control
        ttk.Label(self.control_frame, text="Bins:").grid(row=11, column=0, sticky='w', pady=2)

        # Create frame for bin controls
        bin_frame = ttk.Frame(self.control_frame)
        bin_frame.grid(row=11, column=1, columnspan=2, sticky='ew', pady=2)

        # Bin count entry field only (remove slider)
        self.bin_entry = ttk.Entry(bin_frame, textvariable=self.bin_count_var, width=8)
        self.bin_entry.grid(row=0, column=0, sticky='w')
        self.bin_entry.bind('<Return>', self._on_bin_entry_change)
        self.bin_entry.bind('<FocusOut>', self._on_bin_entry_change)

        # Optional: Add a label showing the valid range
        bin_hint_label = ttk.Label(bin_frame, text=f"({MIN_BIN_COUNT}-{MAX_BIN_COUNT})", 
                                font=('TkDefaultFont', 8), foreground='gray')
        bin_hint_label.grid(row=0, column=1, sticky='w', padx=(5,0))

        # Configure bin frame column weights (optional, for consistent spacing)
        bin_frame.columnconfigure(0, weight=0)  # Entry field doesn't need to expand
        bin_frame.columnconfigure(1, weight=1)  # Hint label can expand if needed
        
        # Statistical lines toggle
        self.stats_lines_check = ttk.Checkbutton(self.control_frame, 
                                                text="Show Mean & Std Dev Lines", 
                                                variable=self.show_stats_lines_var,
                                                command=self._on_stats_toggle)
        self.stats_lines_check.grid(row=12, column=0, columnspan=2, sticky='w', pady=2)
        
        # Plot button
        self.plot_button = ttk.Button(self.control_frame, text="Create Plot", 
                                     command=self.create_plot, state='disabled')
        self.plot_button.grid(row=13, column=0, columnspan=2, sticky='ew', pady=10)
        
        # Report generation button - will be mode-restricted
        self.report_button = ttk.Button(self.control_frame, text="Generate Report", 
                                       command=self.generate_report, state='disabled')
        self.report_button.grid(row=14, column=0, columnspan=2, sticky='ew', pady=5)
        
        # Show/hide report button based on availability
        if not REPORTS_AVAILABLE:
            self.report_button.config(state='disabled', text="Generate Report (ReportLab not installed)")
        
        # === DATASET MANAGEMENT CONTROLS ===
        ttk.Separator(self.control_frame, orient='horizontal').grid(row=15, column=0, columnspan=3, sticky='ew', pady=10)
        
        # Dataset management frame
        self.dataset_mgmt_frame = ttk.LabelFrame(self.control_frame, text="Dataset Management", padding=5)
        self.dataset_mgmt_frame.grid(row=16, column=0, columnspan=3, sticky='ew', pady=5)
        
        # Dataset navigation
        nav_frame = ttk.Frame(self.dataset_mgmt_frame)
        nav_frame.pack(fill='x', pady=5)
        
        self.prev_dataset_btn = ttk.Button(nav_frame, text="◀ Previous", 
                                          command=self.previous_dataset, state='disabled')
        self.prev_dataset_btn.pack(side='left', padx=(0,5))
        
        self.next_dataset_btn = ttk.Button(nav_frame, text="Next ▶", 
                                          command=self.next_dataset, state='disabled')
        self.next_dataset_btn.pack(side='left')
        
        # Dataset actions (removed Edit Tag since we have inline editing)
        actions_frame = ttk.Frame(self.dataset_mgmt_frame)
        actions_frame.pack(fill='x', pady=5)
        
        self.edit_notes_btn = ttk.Button(actions_frame, text="Edit Notes", 
                                        command=self.edit_dataset_notes, state='disabled')
        self.edit_notes_btn.pack(side='left', padx=(0,5))
        
        self.remove_dataset_btn = ttk.Button(actions_frame, text="Remove", 
                                            command=self.remove_dataset, state='disabled')
        self.remove_dataset_btn.pack(side='left')
        
        # Stats display
        self.stats_frame = ttk.LabelFrame(self.control_frame, text="Data Info", padding=5)
        self.stats_frame.grid(row=17, column=0, columnspan=3, sticky='ew', pady=5)
        
        self.stats_text = tk.Text(self.stats_frame, height=8, width=30)
        self.stats_text.pack(fill='both', expand=True)
        
        # === PLOT FRAME (Right side - now the only right side frame) ===
        self.plot_frame = ttk.LabelFrame(self.main_frame, text="Plot", padding=10)
        
        # Configure column weights
        self.control_frame.columnconfigure(1, weight=1)
    
    def _create_layout(self):
        # Pack the scrollable frame and main frame
        self.scrollable_frame.pack(side='left', fill='y', padx=(5,5), pady=5)
        self.main_frame.pack(side='left', fill='both', expand=True, padx=(0,5), pady=5)
        
        # Pack the control frame inside the scrollable frame (already done in _create_widgets)
        self.control_frame.pack(fill='both', expand=True, padx=5, pady=5)
        
        # Pack the plot frame in the main frame
        self.plot_frame.pack(fill='both', expand=True)
    
    # === NEW: TAG EDITING METHODS ===
    
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
    
    # === ANALYSIS MODE MANAGEMENT METHODS ===
    
    def _on_analysis_mode_change(self):
        """Handle analysis mode change (calibration vs verification)."""
        mode = self.analysis_mode_var.get()
        logger.info(f"Analysis mode changed to: {mode}")
        
        # Update mode description
        if mode == 'calibration':
            self.mode_description.config(
                text="Calibration: Single dataset analysis for instrument calibration",
                foreground='blue'
            )
        else:  # verification
            self.mode_description.config(
                text="Verification: Multi-dataset comparison and validation analysis",
                foreground='green'
            )
        
        # Update UI elements based on mode
        self._update_analysis_mode_ui()
        
        # In calibration mode, if we have multiple datasets, show a warning
        if mode == 'calibration' and self.dataset_manager.get_dataset_count() > 1:
            result = messagebox.askyesno(
                "Calibration Mode",
                "Calibration mode is optimized for single dataset analysis.\n\n"
                "Would you like to remove all but the active dataset?\n\n"
                "Click 'No' to keep all datasets (you can manually remove extras later)."
            )
            if result:
                self._keep_only_active_dataset()
    
    def _update_analysis_mode_ui(self):
        """Update UI elements based on the current analysis mode."""
        mode = self.analysis_mode_var.get()
        is_calibration = (mode == 'calibration')
        
        # Update smart button text based on mode
        if is_calibration:
            self.smart_load_button.config(text="📄 Load CSV File")
        else:  # verification mode
            self.smart_load_button.config(text="📁 Load Data Files")
        
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
    
    def smart_load_files(self):
        """Smart file loading that adapts to analysis mode."""
        mode = self.analysis_mode_var.get()
        
        if mode == 'calibration':
            # Calibration mode: single file loading with enhanced preview
            self._load_single_file_with_preview()
        else:
            # Verification mode: direct multi-file loading (CHANGED)
            self.load_multiple_files()

    def _load_single_file_with_preview(self):
        """Load a single file with automatic preview option."""
        file_path = filedialog.askopenfilename(
            title="Select CSV file",
            filetypes=SUPPORTED_FILE_TYPES
        )
        
        if file_path:
            # Create and show the preview dialog
            preview_dialog = FilePreviewDialog(self.root, file_path, self._handle_file_load)
            preview_dialog.show()

    def _handle_load_choice(self, choice: str):
        """Handle the user's choice from the load choice dialog."""
        if choice == 'single':
            self._load_single_file_with_preview()
        elif choice == 'multiple':
            self.load_multiple_files()
        # If choice == 'cancel', do nothing

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
        """Load multiple CSV files using file queue system."""
        # Check mode restriction first
        if self.analysis_mode_var.get() == 'calibration':
            messagebox.showwarning(
                "Mode Restriction", 
                "Multiple file loading is only available in Verification mode.\n\n"
                "Switch to Verification mode to load multiple files for comparison analysis."
            )
            return
        
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
                                f"Click 'Process Queue' to begin loading with preview.")
                
                # Start the queue processing workflow
                self._start_queue_processing()
            else:
                messagebox.showerror("Error", "No valid files were added to the queue.")
    
    def generate_random_data(self):
        """Generate random particle data for testing."""
        try:
            n = self.random_count_var.get()
            distribution = self.distribution_var.get()
            
            if n <= 0:
                messagebox.showerror("Error", "Number of points must be positive.")
                return
            
            # Create temporary processor for random data generation
            temp_processor = ParticleDataProcessor()
            if temp_processor.generate_random_data(n, distribution):
                # Generate numeric tag based on parameters
                numeric_tag = str(float(n))  # Use point count as tag
                notes = f"Generated {distribution} distribution with {n} data points"
                
                dataset_id = self._add_generated_dataset(temp_processor, numeric_tag, notes)
                
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
                    
                    messagebox.showinfo("Success", f"Generated dataset '{numeric_tag}' successfully!")
                else:
                    messagebox.showerror("Error", "Failed to add generated data to dataset manager.")
            else:
                messagebox.showerror("Error", "Failed to generate random data.")
                
        except tk.TclError:
            messagebox.showerror("Error", "Please enter a valid number of points.")

    
    def _add_generated_dataset(self, data_processor, tag, notes):
        """Add a generated dataset to the dataset manager."""
        import uuid
        from datetime import datetime
        
        try:
            # Create unique ID for this dataset
            dataset_id = str(uuid.uuid4())
            
            # Assign color
            color = self.dataset_manager._get_next_color()
            
            # Create dataset entry for generated data
            dataset_info = {
                'id': dataset_id,
                'filename': 'Generated Data',
                'file_path': None,  # No file path for generated data
                'tag': tag,
                'notes': notes,
                'color': color,
                'data_processor': data_processor,
                'loaded_at': datetime.now(),
                'skip_rows': 0,
                # Store current analysis settings per dataset
                'analysis_settings': {
                    'data_mode': 'pre_aggregated',  # Generated data is always pre-aggregated
                    'bin_count': 50,
                    'size_column': data_processor.size_column,
                    'frequency_column': data_processor.frequency_column,
                    'show_stats_lines': True
                }
            }
            
            # Add to collection
            self.dataset_manager.datasets[dataset_id] = dataset_info
            
            # Set as active if it's the first dataset
            if self.dataset_manager.active_dataset_id is None:
                self.dataset_manager.active_dataset_id = dataset_id
            
            logger.info(f"Added generated dataset: {tag} (ID: {dataset_id})")
            return dataset_id
            
        except Exception as e:
            logger.error(f"Error adding generated dataset: {e}")
            return None
    
    # === FILE QUEUE PROCESSING METHODS ===
    
    def _start_queue_processing(self):
        """Start the queue processing workflow."""
        if not self.file_queue.has_more_files():
            messagebox.showinfo("Queue Complete", "No files to process.")
            return
        
        # Process the first file
        self._process_current_queue_file()

    def _process_current_queue_file(self):
        """Process the current file in the queue."""
        current_file = self.file_queue.get_current_file()
        
        if not current_file:
            # Queue is complete
            self._finish_queue_processing()
            return
        
        self._update_queue_status()
        
        # Show enhanced preview for current file
        self._show_queue_preview_dialog(current_file)

    def _show_queue_preview_dialog(self, file_info):
        """Show preview dialog for current file in queue."""
        file_path = file_info['file_path']
        
        # Try to preview the file
        temp_processor = ParticleDataProcessor()
        preview_data = temp_processor.preview_csv(file_path, preview_rows=15)
        
        if not preview_data['success']:
            # Can't preview - skip this file
            error_msg = f"Cannot preview file: {preview_data.get('error', 'Unknown error')}"
            self.file_queue.mark_current_failed(error_msg)
            
            # Ask user if they want to continue
            result = messagebox.askyesno(
                "Preview Failed", 
                f"Failed to preview {file_info['filename']}:\n{error_msg}\n\n"
                f"Skip this file and continue with queue?"
            )
            
            if result:
                self._process_current_queue_file()  # Process next file
            else:
                self._cancel_queue_processing()
            return
        
        # Show the enhanced preview dialog
        self._show_enhanced_queue_preview_dialog(preview_data, file_info)

    def _show_enhanced_queue_preview_dialog(self, preview_data, file_info):
            """Show enhanced preview dialog for queue processing."""
            # Create the dialog window (this was missing the local variable assignment!)
            preview_window = tk.Toplevel(self.root)
            preview_window.title(f"Queue Preview - {file_info['filename']}")
            preview_window.geometry("950x800")
            preview_window.grab_set()  # Make it modal
            
            # Queue progress header
            queue_info = self.file_queue.get_current_file_info()
            progress_frame = ttk.LabelFrame(preview_window, text="Queue Progress", padding=5)
            progress_frame.pack(fill='x', padx=10, pady=5)
            
            progress_text = f"File {queue_info['current_index'] + 1} of {queue_info['total_files']}"
            if queue_info['processed_count'] > 0:
                progress_text += f" | Processed: {queue_info['processed_count']}"
            if queue_info['failed_count'] > 0:
                progress_text += f" | Failed: {queue_info['failed_count']}"
            if queue_info['skipped_count'] > 0:
                progress_text += f" | Skipped: {queue_info['skipped_count']}"
            
            ttk.Label(progress_frame, text=progress_text, font=('TkDefaultFont', 10, 'bold')).pack(anchor='w')
            
            # File info header (NO TAG EDITING HERE - moved to filtering section)
            info_frame = ttk.LabelFrame(preview_window, text="Current File Information", padding=5)
            info_frame.pack(fill='x', padx=10, pady=5)
            
            ttk.Label(info_frame, text=f"File: {file_info['filename']}", font=('TkDefaultFont', 9, 'bold')).pack(anchor='w')
            ttk.Label(info_frame, text=f"Total lines: {preview_data['total_lines']}").pack(anchor='w')
            ttk.Label(info_frame, text=f"Detected columns: {preview_data['detected_columns']}").pack(anchor='w')
            
            # Preview text section
            preview_section = ttk.LabelFrame(preview_window, text="File Preview", padding=5)
            preview_section.pack(fill='both', expand=True, padx=10, pady=5)
            
            preview_text = tk.Text(preview_section, wrap='none', font=('Courier', 9), height=15)
            scrollbar = ttk.Scrollbar(preview_section, orient='vertical', command=preview_text.yview)
            preview_text.configure(yscrollcommand=scrollbar.set)
            
            preview_text.pack(side='left', fill='both', expand=True)
            scrollbar.pack(side='right', fill='y')
            
            # Add preview content
            for i, line in enumerate(preview_data['preview_lines']):
                preview_text.insert(tk.END, f"{i:3d}: {line}\n")
            preview_text.config(state='disabled')
            
            # Filter controls section (MOVED TAG EDITING HERE to match single-file dialog)
            filter_frame = ttk.LabelFrame(preview_window, text="Data Filtering Options", padding=10)
            filter_frame.pack(fill='x', padx=10, pady=5)
            
            # Create filter_row container like in single-file dialog
            filter_row = ttk.Frame(filter_frame)
            filter_row.pack(fill='x')
            
            # Tag editing with float validation (repositioned to match single-file layout)
            ttk.Label(filter_row, text="Bead Size (μm):").grid(row=0, column=0, sticky='w', padx=(0,5))
            tag_var = tk.StringVar(value=file_info['auto_tag'])
            
            # Register validation function for this dialog
            validate_float = preview_window.register(self._validate_float_input_for_dialog)
            
            tag_entry = ttk.Entry(
                filter_row, 
                textvariable=tag_var, 
                width=30,
                validate='key',
                validatecommand=(validate_float, '%P')
            )
            tag_entry.grid(row=0, column=1, sticky='w', padx=5)
            
            # Skip rows control (moved to same row structure)
            ttk.Label(filter_row, text="Skip rows from top:").grid(row=1, column=0, sticky='w', pady=(10,0), padx=(0,5))
            skip_var = tk.IntVar(value=file_info['skip_rows'])
            skip_entry = ttk.Entry(filter_row, textvariable=skip_var, width=6)
            skip_entry.grid(row=1, column=1, sticky='w', padx=5, pady=(10,0))
            
            # Add hint text like in single-file dialog
            skip_hint_label = ttk.Label(
                filter_row, 
                text="(Use this to skip headers, metadata, or junk data)", 
                font=('TkDefaultFont', 8)
            )
            skip_hint_label.grid(row=1, column=2, sticky='w', padx=(10,0), pady=(10,0))
            
            # Buttons
            button_frame = ttk.Frame(preview_window)
            button_frame.pack(fill='x', padx=10, pady=10)
            
            def load_current_file():
                try:
                    skip_rows = skip_var.get()
                    if skip_rows < 0:
                        skip_rows = 0
                    
                    tag_str = tag_var.get().strip()
                    if not tag_str:
                        messagebox.showerror("Error", "Please enter a numeric bead size value.")
                        return
                    
                    # Validate float
                    try:
                        tag_float = float(tag_str)
                        normalized_tag = str(tag_float)
                    except ValueError:
                        messagebox.showerror("Error", "Bead size must be a valid number (e.g., 1.5, -2.0, 42)")
                        return
                    
                    # Update file queue with settings
                    self.file_queue.update_current_file(
                        skip_rows=skip_rows,
                        auto_tag=normalized_tag
                    )
                    
                    preview_window.destroy()
                    self._load_current_queue_file(file_info['file_path'], normalized_tag, skip_rows)
                    
                except tk.TclError:
                    messagebox.showerror("Error", "Please enter a valid number for rows to skip.")
            
            def skip_current_file():
                self.file_queue.skip_current_file("User skipped during preview")
                preview_window.destroy()
                self._process_current_queue_file()
            
            def cancel_queue():
                preview_window.destroy()
                self._cancel_queue_processing()
            
            ttk.Button(button_frame, text="📁 Load This File", command=load_current_file).pack(side='left', padx=5)
            ttk.Button(button_frame, text="⏭️ Skip This File", command=skip_current_file).pack(side='left', padx=5)
            ttk.Button(button_frame, text="❌ Cancel Queue", command=cancel_queue).pack(side='left', padx=5)
            
            tag_entry.focus_set()
            tag_entry.select_range(0, tk.END)

    def _load_current_queue_file(self, file_path, dataset_tag, skip_rows):
        """Load the current queue file as a dataset."""
        try:
            dataset_id = self.dataset_manager.add_dataset(
                file_path=file_path,
                tag=dataset_tag,
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
                
                logger.info(f"Successfully loaded queue file: {dataset_tag}")
                self._process_current_queue_file()
                
            else:
                self.file_queue.mark_current_failed("Failed to load file into dataset manager")
                result = messagebox.askyesno(
                    "Load Failed", 
                    f"Failed to load {dataset_tag}.\n\nContinue with remaining files?"
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
                f"Error loading {dataset_tag}:\n{error_msg}\n\nContinue with remaining files?"
            )
            
            if result:
                self._process_current_queue_file()
            else:
                self._cancel_queue_processing()

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
    
    # === UPDATED DATASET MANAGEMENT METHODS ===
    
    def _update_dataset_ui(self):
        """Update all dataset-related UI elements."""
        self._update_dataset_treeview()  # Changed from _update_dataset_listbox
        self._update_compact_dataset_info()  # Updated method name
        self._update_navigation_buttons()
        self._update_tag_editor()  # NEW: Update tag editor
    
    def _update_dataset_treeview(self):
        """Update the dataset treeview with current datasets."""
        # Clear existing items
        for item in self.dataset_treeview.get_children():
            self.dataset_treeview.delete(item)
        
        datasets = self.dataset_manager.get_all_datasets()
        active_id = self.dataset_manager.active_dataset_id
        
        for i, dataset in enumerate(datasets):
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
        
        # Action buttons (removed edit_tag_btn since we have inline editing)
        self.edit_notes_btn.config(state='normal' if has_datasets else 'disabled')
        self.remove_dataset_btn.config(state='normal' if has_datasets else 'disabled')
    
    def _on_dataset_select(self, event):
        """Handle dataset selection from treeview."""
        selection = self.dataset_treeview.selection()  # ✅ Use treeview selection
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
                    self._update_tag_editor()  # Update tag editor when selection changes
                    self._update_column_combos()
                    self._update_stats_display()
                    
                    # Update plot if canvas exists and we have data
                    if hasattr(self, 'canvas') and self.dataset_manager.get_active_dataset():
                        self._update_plot()
            
            except (ValueError, IndexError) as e:
                logger.error(f"Error handling dataset selection: {e}")
                # Optionally show user-friendly error message

    
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
                widget.destroy()
            if self.current_figure:
                plt.close(self.current_figure)
                self.current_figure = None
        
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
            'show_stats_lines': self.show_stats_lines_var.get()
        }
        
        self.dataset_manager.update_analysis_settings(active_dataset['id'], settings)
    
    # === DATA PROCESSING AND PLOTTING METHODS ===
    
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
    
    def _on_bin_scale_move(self, value):
        """Handle bin count scale movement - convert to int and update display only."""
        # Convert float value to integer and update the IntVar
        bin_count = int(float(value))
        self.bin_count_var.set(bin_count)
    
    def _on_bin_scale_release(self, event):
        """Handle bin count scale release - triggers plot update."""
        # Ensure we have an integer value
        bin_count = int(self.bin_count_var.get())
        self.bin_count_var.set(bin_count)  # Force integer update
        
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
            data_mode=mode
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
                data_mode=mode
            )
            
            if figure is not None:
                self._display_plot(figure)
                self._update_report_button_state()  # Update report button after plot update
    
    def _display_plot(self, figure):
        """Display the plot in the GUI."""
        # Clear existing plot widgets completely
        for widget in self.plot_frame.winfo_children():
            widget.destroy()
        
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

    def _validate_float_input_for_dialog(self, value_if_allowed):
        """Validate float input for dialog contexts (same as main validation)."""
        return self._validate_float_input(value_if_allowed)

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
        