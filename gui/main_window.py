"""
Main GUI window for the Particle Data Analyzer with Dataset Manager integration.
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

# Try to import report generation (now required dependency)
try:
    from reports.templates import StandardReportTemplate
    REPORTS_AVAILABLE = True
except ImportError:
    REPORTS_AVAILABLE = False

logger = logging.getLogger(__name__)

class MainWindow:
    """Main application window with dataset management."""
    
    def __init__(self, root):
        self.root = root
        self.root.title("Particle Data Analyzer")
        self.root.geometry("1400x900")  # Slightly larger to accommodate dataset list
        
        # Set up proper close handling
        self.root.protocol("WM_DELETE_WINDOW", self._on_closing)
        
        # Initialize core components
        self.dataset_manager = DatasetManager()
        self.plotter = ParticlePlotter()
        
        # GUI variables
        self.bin_count_var = tk.IntVar(value=DEFAULT_BIN_COUNT)
        self.size_column_var = tk.StringVar()
        self.frequency_column_var = tk.StringVar()
        self.random_count_var = tk.IntVar(value=RANDOM_DATA_BOUNDS['default_n'])
        self.distribution_var = tk.StringVar(value='lognormal')
        self.show_stats_lines_var = tk.BooleanVar(value=True)
        self.data_mode_var = tk.StringVar(value='pre_aggregated')
        self.skip_rows_var = tk.IntVar(value=0)
        
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
    
    def _create_widgets(self):
        """Create all GUI widgets."""
        # Main frame
        self.main_frame = ttk.Frame(self.root)
        
        # Control frame (left side)
        self.control_frame = ttk.LabelFrame(self.main_frame, text="Controls", padding=10)
        
        # === FILE LOADING CONTROLS ===
        ttk.Label(self.control_frame, text="Data File:").grid(row=0, column=0, sticky='w', pady=2)
        
        file_frame = ttk.Frame(self.control_frame)
        file_frame.grid(row=0, column=1, columnspan=2, sticky='ew', pady=2)
        
        self.load_button = ttk.Button(file_frame, text="Load CSV", command=self.load_file)
        self.load_button.grid(row=0, column=0, sticky='ew', padx=(0,5))
        
        self.preview_button = ttk.Button(file_frame, text="Preview", command=self.preview_file)
        self.preview_button.grid(row=0, column=1)
        
        file_frame.columnconfigure(0, weight=1)
        
        # File filtering options
        filter_frame = ttk.Frame(self.control_frame)
        filter_frame.grid(row=1, column=0, columnspan=3, sticky='ew', pady=2)
        
        ttk.Label(filter_frame, text="Skip rows:").grid(row=0, column=0, sticky='w')
        self.skip_rows_entry = ttk.Entry(filter_frame, textvariable=self.skip_rows_var, width=6)
        self.skip_rows_entry.grid(row=0, column=1, padx=5)
        
        ttk.Label(filter_frame, text="(header rows, metadata, etc.)").grid(row=0, column=2, sticky='w', padx=(5,0))
        
        # === RANDOM DATA GENERATION ===
        ttk.Separator(self.control_frame, orient='horizontal').grid(row=2, column=0, columnspan=3, sticky='ew', pady=5)
        
        ttk.Label(self.control_frame, text="Generate Random Data:").grid(row=3, column=0, sticky='w', pady=2)
        
        # Random data controls frame
        random_frame = ttk.Frame(self.control_frame)
        random_frame.grid(row=4, column=0, columnspan=3, sticky='ew', pady=2)
        
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
        ttk.Separator(self.control_frame, orient='horizontal').grid(row=5, column=0, columnspan=3, sticky='ew', pady=5)
        
        # Data mode selection
        ttk.Label(self.control_frame, text="Data Type:").grid(row=6, column=0, sticky='w', pady=2)
        
        data_mode_frame = ttk.Frame(self.control_frame)
        data_mode_frame.grid(row=6, column=1, columnspan=2, sticky='ew', pady=2)
        
        self.pre_agg_radio = ttk.Radiobutton(data_mode_frame, text="Pre-aggregated (Size + Frequency)", 
                                           variable=self.data_mode_var, value='pre_aggregated',
                                           command=self._on_data_mode_change)
        self.pre_agg_radio.grid(row=0, column=0, sticky='w')
        
        self.raw_radio = ttk.Radiobutton(data_mode_frame, text="Raw Measurements (Size only)", 
                                       variable=self.data_mode_var, value='raw_measurements',
                                       command=self._on_data_mode_change)
        self.raw_radio.grid(row=1, column=0, sticky='w')
        
        # Column selection
        ttk.Label(self.control_frame, text="Size Column:").grid(row=7, column=0, sticky='w', pady=2)
        self.size_combo = ttk.Combobox(self.control_frame, textvariable=self.size_column_var, 
                                      state='readonly')
        self.size_combo.grid(row=7, column=1, sticky='ew', pady=2)
        self.size_combo.bind('<<ComboboxSelected>>', self._on_column_change)
        
        self.frequency_label = ttk.Label(self.control_frame, text="Frequency Column:")
        self.frequency_label.grid(row=8, column=0, sticky='w', pady=2)
        self.frequency_combo = ttk.Combobox(self.control_frame, textvariable=self.frequency_column_var, 
                                           state='readonly')
        self.frequency_combo.grid(row=8, column=1, sticky='ew', pady=2)
        self.frequency_combo.bind('<<ComboboxSelected>>', self._on_column_change)
        
        # Bin count control
        ttk.Label(self.control_frame, text="Bins:").grid(row=9, column=0, sticky='w', pady=2)
        
        # Create frame for bin controls
        bin_frame = ttk.Frame(self.control_frame)
        bin_frame.grid(row=9, column=1, columnspan=2, sticky='ew', pady=2)
        
        # Bin count slider
        self.bin_scale = ttk.Scale(bin_frame, from_=MIN_BIN_COUNT, to=MAX_BIN_COUNT, 
                                  variable=self.bin_count_var, orient='horizontal')
        self.bin_scale.grid(row=0, column=0, sticky='ew', padx=(0,5))
        
        # Configure scale to use integer values only
        self.bin_scale.configure(command=self._on_bin_scale_move)
        
        # Bind to ButtonRelease instead of continuous movement for plot updates
        self.bin_scale.bind('<ButtonRelease-1>', self._on_bin_scale_release)
        
        # Bin count entry field
        self.bin_entry = ttk.Entry(bin_frame, textvariable=self.bin_count_var, width=6)
        self.bin_entry.grid(row=0, column=1)
        self.bin_entry.bind('<Return>', self._on_bin_entry_change)
        self.bin_entry.bind('<FocusOut>', self._on_bin_entry_change)
        
        # Configure bin frame column weights
        bin_frame.columnconfigure(0, weight=1)
        
        # Statistical lines toggle
        self.stats_lines_check = ttk.Checkbutton(self.control_frame, 
                                                text="Show Mean & Std Dev Lines", 
                                                variable=self.show_stats_lines_var,
                                                command=self._on_stats_toggle)
        self.stats_lines_check.grid(row=10, column=0, columnspan=2, sticky='w', pady=2)
        
        # Plot button
        self.plot_button = ttk.Button(self.control_frame, text="Create Plot", 
                                     command=self.create_plot, state='disabled')
        self.plot_button.grid(row=11, column=0, columnspan=2, sticky='ew', pady=10)
        
        # Report generation button
        self.report_button = ttk.Button(self.control_frame, text="Generate Report", 
                                       command=self.generate_report, state='disabled')
        self.report_button.grid(row=12, column=0, columnspan=2, sticky='ew', pady=5)
        
        # Show/hide report button based on availability
        if not REPORTS_AVAILABLE:
            self.report_button.config(state='disabled', text="Generate Report (ReportLab not installed)")
        
        # === DATASET MANAGEMENT CONTROLS ===
        ttk.Separator(self.control_frame, orient='horizontal').grid(row=13, column=0, columnspan=3, sticky='ew', pady=10)
        
        # Dataset management frame
        self.dataset_mgmt_frame = ttk.LabelFrame(self.control_frame, text="Dataset Management", padding=5)
        self.dataset_mgmt_frame.grid(row=14, column=0, columnspan=3, sticky='ew', pady=5)
        
        # Dataset navigation
        nav_frame = ttk.Frame(self.dataset_mgmt_frame)
        nav_frame.pack(fill='x', pady=5)
        
        self.prev_dataset_btn = ttk.Button(nav_frame, text="◀ Previous", 
                                          command=self.previous_dataset, state='disabled')
        self.prev_dataset_btn.pack(side='left', padx=(0,5))
        
        self.next_dataset_btn = ttk.Button(nav_frame, text="Next ▶", 
                                          command=self.next_dataset, state='disabled')
        self.next_dataset_btn.pack(side='left')
        
        # Dataset info display
        self.dataset_info_frame = ttk.Frame(self.dataset_mgmt_frame)
        self.dataset_info_frame.pack(fill='x', pady=5)
        
        self.dataset_info_label = ttk.Label(self.dataset_info_frame, text="No datasets loaded", 
                                           font=('TkDefaultFont', 9, 'bold'))
        self.dataset_info_label.pack(anchor='w')
        
        # Dataset actions
        actions_frame = ttk.Frame(self.dataset_mgmt_frame)
        actions_frame.pack(fill='x', pady=5)
        
        self.edit_tag_btn = ttk.Button(actions_frame, text="Edit Tag", 
                                      command=self.edit_dataset_tag, state='disabled')
        self.edit_tag_btn.pack(side='left', padx=(0,5))
        
        self.edit_notes_btn = ttk.Button(actions_frame, text="Edit Notes", 
                                        command=self.edit_dataset_notes, state='disabled')
        self.edit_notes_btn.pack(side='left', padx=(0,5))
        
        self.remove_dataset_btn = ttk.Button(actions_frame, text="Remove", 
                                            command=self.remove_dataset, state='disabled')
        self.remove_dataset_btn.pack(side='left')
        
        # Stats display
        self.stats_frame = ttk.LabelFrame(self.control_frame, text="Data Info", padding=5)
        self.stats_frame.grid(row=15, column=0, columnspan=3, sticky='ew', pady=5)
        
        self.stats_text = tk.Text(self.stats_frame, height=8, width=30)
        self.stats_text.pack(fill='both', expand=True)
        
        # === DATASET LIST (Center) ===
        self.dataset_list_frame = ttk.LabelFrame(self.main_frame, text="Loaded Datasets", padding=5)
        
        # Dataset listbox with scrollbar
        list_container = ttk.Frame(self.dataset_list_frame)
        list_container.pack(fill='both', expand=True)
        
        self.dataset_listbox = tk.Listbox(list_container, height=6, selectmode='single')
        dataset_scrollbar = ttk.Scrollbar(list_container, orient='vertical', command=self.dataset_listbox.yview)
        
        self.dataset_listbox.configure(yscrollcommand=dataset_scrollbar.set)
        self.dataset_listbox.bind('<<ListboxSelect>>', self._on_dataset_select)
        
        self.dataset_listbox.pack(side='left', fill='both', expand=True)
        dataset_scrollbar.pack(side='right', fill='y')
        
        # === PLOT FRAME (Right side) ===
        self.plot_frame = ttk.LabelFrame(self.main_frame, text="Plot", padding=10)
        
        # Configure column weights
        self.control_frame.columnconfigure(1, weight=1)
    
    def _create_layout(self):
        """Arrange widgets in the window."""
        self.main_frame.pack(fill='both', expand=True, padx=5, pady=5)
        
        # Use grid for main layout: controls | dataset list | plot
        self.main_frame.columnconfigure(2, weight=1)  # Plot gets most space
        self.main_frame.rowconfigure(0, weight=1)
        
        self.control_frame.grid(row=0, column=0, sticky='nsew', padx=(0, 5))
        self.dataset_list_frame.grid(row=0, column=1, sticky='nsew', padx=(0, 5))
        self.plot_frame.grid(row=0, column=2, sticky='nsew')
    
    def load_file(self):
        """Load a CSV file and add it to the dataset manager."""
        file_path = filedialog.askopenfilename(
            title="Select CSV file",
            filetypes=SUPPORTED_FILE_TYPES
        )
        
        if file_path:
            try:
                skip_rows = self.skip_rows_var.get()
                if skip_rows < 0:
                    skip_rows = 0
                    self.skip_rows_var.set(0)
                
                # Create a default tag from filename
                filename = file_path.split('/')[-1].split('\\')[-1]
                default_tag = filename.replace('.csv', '').replace('.CSV', '')
                
                # Add dataset to manager
                dataset_id = self.dataset_manager.add_dataset(
                    file_path=file_path,
                    tag=default_tag,
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
                    
                    if skip_rows > 0:
                        messagebox.showinfo("Success", f"Dataset '{default_tag}' loaded successfully!\nSkipped {skip_rows} rows.")
                    else:
                        messagebox.showinfo("Success", f"Dataset '{default_tag}' loaded successfully!")
                else:
                    messagebox.showerror("Error", "Failed to load file. Please check the file format.")
                    
            except ValueError:
                messagebox.showerror("Error", "Please enter a valid number for rows to skip.")
    
    def preview_file(self):
        """Preview a CSV file to help identify junk data."""
        file_path = filedialog.askopenfilename(
            title="Select CSV file to preview",
            filetypes=SUPPORTED_FILE_TYPES
        )
        
        if file_path:
            # Create a temporary data processor for preview
            temp_processor = ParticleDataProcessor()
            preview_data = temp_processor.preview_csv(file_path, preview_rows=15)
            
            if preview_data['success']:
                self._show_enhanced_preview_dialog(preview_data, file_path)
            else:
                messagebox.showerror("Preview Error", f"Failed to preview file:\n{preview_data['error']}")
    
    def _show_enhanced_preview_dialog(self, initial_preview_data, file_path):
        """Show an enhanced dialog with configurable preview and filtering options."""
        preview_window = tk.Toplevel(self.root)
        preview_window.title("CSV File Preview - Enhanced")
        preview_window.geometry("950x750")
        preview_window.grab_set()  # Make it modal
        
        # File info header
        info_frame = ttk.LabelFrame(preview_window, text="File Information", padding=5)
        info_frame.pack(fill='x', padx=10, pady=5)
        
        ttk.Label(info_frame, text=f"File: {file_path.split('/')[-1]}", font=('TkDefaultFont', 9, 'bold')).pack(anchor='w')
        ttk.Label(info_frame, text=f"Total lines: {initial_preview_data['total_lines']}").pack(anchor='w')
        ttk.Label(info_frame, text=f"Detected columns: {initial_preview_data['detected_columns']}").pack(anchor='w')
        
        # Preview controls section
        preview_control_frame = ttk.LabelFrame(preview_window, text="Preview Controls", padding=5)
        preview_control_frame.pack(fill='x', padx=10, pady=5)
        
        # Preview length controls
        controls_row = ttk.Frame(preview_control_frame)
        controls_row.pack(fill='x')
        
        ttk.Label(controls_row, text="Preview lines:").grid(row=0, column=0, sticky='w', padx=(0,5))
        preview_lines_var = tk.IntVar(value=15)
        preview_lines_entry = ttk.Entry(controls_row, textvariable=preview_lines_var, width=8)
        preview_lines_entry.grid(row=0, column=1, padx=5)
        
        def refresh_preview():
            try:
                num_lines = preview_lines_var.get()
                if num_lines < 1:
                    num_lines = 1
                    preview_lines_var.set(1)
                elif num_lines > 1000:
                    num_lines = 1000
                    preview_lines_var.set(1000)
                
                # Get new preview data
                temp_processor = ParticleDataProcessor()
                new_preview_data = temp_processor.preview_csv(file_path, preview_rows=num_lines)
                
                if new_preview_data['success']:
                    # Clear and update preview text
                    preview_text.config(state='normal')
                    preview_text.delete(1.0, tk.END)
                    
                    # Add preview content with row numbers
                    for i, line in enumerate(new_preview_data['preview_lines']):
                        preview_text.insert(tk.END, f"{i:3d}: {line}\n")
                    
                    preview_text.config(state='disabled')
                    
                    # Update status
                    status_label.config(text=f"✓ Showing first {len(new_preview_data['preview_lines'])} lines")
                else:
                    messagebox.showerror("Preview Error", f"Failed to refresh preview:\n{new_preview_data['error']}")
                    
            except tk.TclError:
                messagebox.showerror("Error", "Please enter a valid number of lines to preview.")
        
        refresh_button = ttk.Button(controls_row, text="🔄 Refresh Preview", command=refresh_preview)
        refresh_button.grid(row=0, column=2, padx=10)
        
        ttk.Label(controls_row, text="(1-1000 lines)", font=('TkDefaultFont', 8)).grid(row=0, column=3, sticky='w', padx=(5,0))
        
        # Status label
        status_label = ttk.Label(controls_row, text=f"✓ Showing first {len(initial_preview_data['preview_lines'])} lines", 
                               foreground='green', font=('TkDefaultFont', 8))
        status_label.grid(row=0, column=4, sticky='w', padx=(20,0))
        
        # Preview text section
        preview_section = ttk.LabelFrame(preview_window, text="File Preview", padding=5)
        preview_section.pack(fill='both', expand=True, padx=10, pady=5)
        
        # Text widget with scrollbars
        text_frame = ttk.Frame(preview_section)
        text_frame.pack(fill='both', expand=True)
        
        preview_text = tk.Text(text_frame, wrap='none', font=('Courier', 9))
        scrollbar_y = ttk.Scrollbar(text_frame, orient='vertical', command=preview_text.yview)
        scrollbar_x = ttk.Scrollbar(text_frame, orient='horizontal', command=preview_text.xview)
        
        preview_text.configure(yscrollcommand=scrollbar_y.set, xscrollcommand=scrollbar_x.set)
        
        preview_text.grid(row=0, column=0, sticky='nsew')
        scrollbar_y.grid(row=0, column=1, sticky='ns')
        scrollbar_x.grid(row=1, column=0, sticky='ew')
        
        text_frame.grid_rowconfigure(0, weight=1)
        text_frame.grid_columnconfigure(0, weight=1)
        
        # Add initial preview content with row numbers
        for i, line in enumerate(initial_preview_data['preview_lines']):
            preview_text.insert(tk.END, f"{i:3d}: {line}\n")
        
        preview_text.config(state='disabled')
        
        # Allow Enter key to refresh preview
        preview_lines_entry.bind('<Return>', lambda e: refresh_preview())
        
        # Filter controls section
        filter_frame = ttk.LabelFrame(preview_window, text="Data Filtering Options", padding=10)
        filter_frame.pack(fill='x', padx=10, pady=5)
        
        filter_row = ttk.Frame(filter_frame)
        filter_row.pack(fill='x')
        
        ttk.Label(filter_row, text="Skip rows from top:").grid(row=0, column=0, sticky='w')
        skip_var = tk.IntVar(value=self.skip_rows_var.get())
        skip_entry = ttk.Entry(filter_row, textvariable=skip_var, width=6)
        skip_entry.grid(row=0, column=1, padx=10)
        
        ttk.Label(filter_row, text="(Use this to skip headers, metadata, or junk data)", 
                 font=('TkDefaultFont', 8)).grid(row=0, column=2, sticky='w', padx=(10,0))
        
        # Buttons section
        button_frame = ttk.Frame(preview_window)
        button_frame.pack(fill='x', padx=10, pady=10)
        
        def load_with_filter():
            try:
                skip_rows = skip_var.get()
                if skip_rows < 0:
                    skip_rows = 0
                    
                self.skip_rows_var.set(skip_rows)
                preview_window.destroy()
                
                # Create a default tag from filename
                filename = file_path.split('/')[-1].split('\\')[-1]
                default_tag = filename.replace('.csv', '').replace('.CSV', '')
                
                # Add dataset to manager
                dataset_id = self.dataset_manager.add_dataset(
                    file_path=file_path,
                    tag=default_tag,
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
                    
                    if skip_rows > 0:
                        messagebox.showinfo("Success", f"Dataset '{default_tag}' loaded successfully!\nSkipped {skip_rows} rows.")
                    else:
                        messagebox.showinfo("Success", f"Dataset '{default_tag}' loaded successfully!")
                else:
                    messagebox.showerror("Error", "Failed to load file. Please check the file format.")
                    
            except tk.TclError:
                messagebox.showerror("Error", "Please enter a valid number for rows to skip.")
        
        ttk.Button(button_frame, text="📁 Load with Filter", command=load_with_filter).pack(side='left', padx=5)
        ttk.Button(button_frame, text="❌ Cancel", command=preview_window.destroy).pack(side='left', padx=5)
        
        # Focus on preview lines entry for immediate use
        preview_lines_entry.focus_set()
        preview_lines_entry.select_range(0, tk.END)
    
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
                # Add to dataset manager
                tag = f"Random {distribution.title()} ({n} points)"
                notes = f"Generated {distribution} distribution with {n} data points"
                
                # We need to save the random data first since DatasetManager expects a file
                # For now, we'll use a special internal method
                dataset_id = self._add_generated_dataset(temp_processor, tag, notes)
                
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
                    messagebox.showinfo("Success", f"Generated dataset '{tag}' successfully!")
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
    
    # === DATASET MANAGEMENT METHODS ===
    
    def _update_dataset_ui(self):
        """Update all dataset-related UI elements."""
        self._update_dataset_listbox()
        self._update_dataset_info()
        self._update_navigation_buttons()
    
    def _update_dataset_listbox(self):
        """Update the dataset listbox with current datasets."""
        self.dataset_listbox.delete(0, tk.END)
        
        datasets = self.dataset_manager.get_all_datasets()
        active_id = self.dataset_manager.active_dataset_id
        
        for i, dataset in enumerate(datasets):
            # Format: "[Tag] - filename" with color indicator for better visibility
            if dataset['filename'] != 'Generated Data':
                display_text = f"● [{dataset['tag']}] - {dataset['filename']}"
            else:
                display_text = f"● [{dataset['tag']}] - Generated"
            
            self.dataset_listbox.insert(tk.END, display_text)
            
            # Highlight active dataset
            if dataset['id'] == active_id:
                self.dataset_listbox.selection_set(i)
                self.dataset_listbox.see(i)
    
    def _update_dataset_info(self):
        """Update the dataset info display."""
        active_dataset = self.dataset_manager.get_active_dataset()
        
        if active_dataset:
            info_text = f"Active: {active_dataset['tag']}"
            if active_dataset['notes']:
                info_text += f"\nNotes: {active_dataset['notes'][:50]}..."
            
            self.dataset_info_label.config(text=info_text)
        else:
            self.dataset_info_label.config(text="No datasets loaded")
    
    def _update_navigation_buttons(self):
        """Update the state of navigation and action buttons."""
        has_datasets = self.dataset_manager.has_datasets()
        has_multiple = self.dataset_manager.get_dataset_count() > 1
        
        # Navigation buttons
        self.prev_dataset_btn.config(state='normal' if has_multiple else 'disabled')
        self.next_dataset_btn.config(state='normal' if has_multiple else 'disabled')
        
        # Action buttons
        self.edit_tag_btn.config(state='normal' if has_datasets else 'disabled')
        self.edit_notes_btn.config(state='normal' if has_datasets else 'disabled')
        self.remove_dataset_btn.config(state='normal' if has_datasets else 'disabled')
    
    def _on_dataset_select(self, event):
        """Handle dataset selection from listbox."""
        selection = self.dataset_listbox.curselection()
        if selection:
            # Get the dataset ID based on selection index
            datasets = self.dataset_manager.get_all_datasets()
            if selection[0] < len(datasets):
                selected_dataset = datasets[selection[0]]
                self.dataset_manager.set_active_dataset(selected_dataset['id'])
                
                # Update UI for new active dataset
                self._load_active_dataset_settings()
                self._update_dataset_info()
                self._update_column_combos()
                self._update_stats_display()
                
                # Update plot if auto-plot is desired
                if hasattr(self, 'canvas') and self.dataset_manager.get_active_dataset():
                    self._update_plot()
    
    def previous_dataset(self):
        """Navigate to previous dataset."""
        prev_id = self.dataset_manager.get_previous_dataset_id()
        if prev_id:
            self.dataset_manager.set_active_dataset(prev_id)
            self._load_active_dataset_settings()
            self._update_dataset_ui()
            self._update_column_combos()
            self._update_stats_display()
            
            # Update plot if one exists
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
            
            # Update plot if one exists
            if hasattr(self, 'canvas'):
                self._update_plot()
    
    def edit_dataset_tag(self):
        """Edit the tag of the active dataset."""
        active_dataset = self.dataset_manager.get_active_dataset()
        if not active_dataset:
            return
        
        new_tag = simpledialog.askstring(
            "Edit Dataset Tag",
            "Enter new tag:",
            initialvalue=active_dataset['tag']
        )
        
        if new_tag and new_tag.strip():
            self.dataset_manager.update_dataset_tag(active_dataset['id'], new_tag.strip())
            self._update_dataset_ui()
    
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
    
    # === EXISTING METHODS (Updated for Dataset Manager) ===
    
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
    
    def _update_report_button_state(self):
        """Update the report button state based on available data and plot."""
        if REPORTS_AVAILABLE and hasattr(self, 'canvas') and self.current_figure:
            self.report_button.config(state='normal')
        else:
            if REPORTS_AVAILABLE:
                self.report_button.config(state='disabled')
    
    def generate_report(self):
        """Generate a PDF report with current analysis."""
        if not REPORTS_AVAILABLE:
            messagebox.showerror("Error", "ReportLab is not installed. Please install it with: pip install reportlab")
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
            
            # Collect analysis parameters
            analysis_params = {
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
