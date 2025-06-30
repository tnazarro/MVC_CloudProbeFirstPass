"""
Main GUI window for the Particle Data Analyzer.
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import logging
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
import matplotlib.pyplot as plt

from core.data_processor import ParticleDataProcessor
from core.plotter import ParticlePlotter
from config.constants import SUPPORTED_FILE_TYPES, MIN_BIN_COUNT, MAX_BIN_COUNT, DEFAULT_BIN_COUNT, RANDOM_DATA_BOUNDS

logger = logging.getLogger(__name__)

class MainWindow:
    """Main application window."""
    
    def __init__(self, root):
        self.root = root
        self.root.title("Particle Data Analyzer")
        self.root.geometry("1200x800")
        
        # Set up proper close handling
        self.root.protocol("WM_DELETE_WINDOW", self._on_closing)
        
        # Initialize core components
        self.data_processor = ParticleDataProcessor()
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
        
        self._create_widgets()
        self._create_layout()
        
        # Initialize UI state
        self._update_data_mode_ui()
    
    def _create_widgets(self):
        """Create all GUI widgets."""
        # Main frame
        self.main_frame = ttk.Frame(self.root)
        
        # Control frame (left side)
        self.control_frame = ttk.LabelFrame(self.main_frame, text="Controls", padding=10)
        
        # File loading with preview
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
        
        # Random data generation
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
        
        ttk.Separator(self.control_frame, orient='horizontal').grid(row=7, column=0, columnspan=3, sticky='ew', pady=5)
        
        # Column selection
        ttk.Label(self.control_frame, text="Size Column:").grid(row=8, column=0, sticky='w', pady=2)
        self.size_combo = ttk.Combobox(self.control_frame, textvariable=self.size_column_var, state='readonly')
        self.size_combo.grid(row=8, column=1, sticky='ew', pady=2)
        
        self.frequency_label = ttk.Label(self.control_frame, text="Frequency Column:")
        self.frequency_label.grid(row=9, column=0, sticky='w', pady=2)
        self.frequency_combo = ttk.Combobox(self.control_frame, textvariable=self.frequency_column_var, state='readonly')
        self.frequency_combo.grid(row=9, column=1, sticky='ew', pady=2)
        
        # Bin count control
        ttk.Label(self.control_frame, text="Bins:").grid(row=10, column=0, sticky='w', pady=2)
        
        # Create frame for bin controls
        bin_frame = ttk.Frame(self.control_frame)
        bin_frame.grid(row=10, column=1, columnspan=2, sticky='ew', pady=2)
        
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
        self.stats_lines_check.grid(row=11, column=0, columnspan=2, sticky='w', pady=2)
        
        # Plot button
        self.plot_button = ttk.Button(self.control_frame, text="Create Plot", 
                                     command=self.create_plot, state='disabled')
        self.plot_button.grid(row=12, column=0, columnspan=2, sticky='ew', pady=10)
        
        # Stats display
        self.stats_frame = ttk.LabelFrame(self.control_frame, text="Data Info", padding=5)
        self.stats_frame.grid(row=13, column=0, columnspan=3, sticky='ew', pady=5)
        
        self.stats_text = tk.Text(self.stats_frame, height=8, width=30)
        self.stats_text.pack(fill='both', expand=True)
        
        # Plot frame (right side)
        self.plot_frame = ttk.LabelFrame(self.main_frame, text="Plot", padding=10)
        
        # Configure column weights
        self.control_frame.columnconfigure(1, weight=1)
    
    def _create_layout(self):
        """Arrange widgets in the window."""
        self.main_frame.pack(fill='both', expand=True, padx=5, pady=5)
        
        # Use grid for main layout
        self.main_frame.columnconfigure(1, weight=1)
        self.main_frame.rowconfigure(0, weight=1)
        
        self.control_frame.grid(row=0, column=0, sticky='nsew', padx=(0, 5))
        self.plot_frame.grid(row=0, column=1, sticky='nsew')
    
    def load_file(self):
        """Load a CSV file with optional row filtering."""
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
                
                if self.data_processor.load_csv(file_path, skip_rows):
                    self._update_column_combos()
                    self._update_stats_display()
                    self.plot_button.config(state='normal')
                    
                    if skip_rows > 0:
                        messagebox.showinfo("Success", f"File loaded successfully!\nSkipped {skip_rows} rows.")
                    else:
                        messagebox.showinfo("Success", "File loaded successfully!")
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
            # Start with a default preview
            preview_data = self.data_processor.preview_csv(file_path, preview_rows=15)
            
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
                new_preview_data = self.data_processor.preview_csv(file_path, preview_rows=num_lines)
                
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
                
                if self.data_processor.load_csv(file_path, skip_rows):
                    self._update_column_combos()
                    self._update_stats_display()
                    self.plot_button.config(state='normal')
                    if skip_rows > 0:
                        messagebox.showinfo("Success", f"File loaded successfully!\nSkipped {skip_rows} rows.")
                    else:
                        messagebox.showinfo("Success", "File loaded successfully!")
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
            
            if self.data_processor.generate_random_data(n, distribution):
                # Set data mode to match generated data (always pre-aggregated for random data)
                self.data_processor.set_data_mode('pre_aggregated')
                self.data_mode_var.set('pre_aggregated')
                self._update_data_mode_ui()
                
                self._update_column_combos()
                self._update_stats_display()
                self.plot_button.config(state='normal')
                messagebox.showinfo("Success", f"Generated {n} random data points!")
            else:
                messagebox.showerror("Error", "Failed to generate random data.")
                
        except tk.TclError:
            messagebox.showerror("Error", "Please enter a valid number of points.")
    
    def _on_data_mode_change(self):
        """Handle data mode change (pre-aggregated vs raw measurements)."""
        mode = self.data_mode_var.get()
        
        # Update data processor
        self.data_processor.set_data_mode(mode)
        
        # Update UI
        self._update_data_mode_ui()
        
        # Update stats display
        self._update_stats_display()
        
        # If we have a current plot, update it
        if hasattr(self, 'canvas') and self.data_processor.data is not None:
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
        columns = self.data_processor.get_columns()
        
        self.size_combo['values'] = columns
        self.frequency_combo['values'] = columns
        
        # Set default selections if auto-detected
        if self.data_processor.size_column:
            self.size_column_var.set(self.data_processor.size_column)
        if self.data_processor.frequency_column:
            self.frequency_column_var.set(self.data_processor.frequency_column)
    
    def _update_stats_display(self):
        """Update the statistics display."""
        stats = self.data_processor.get_data_stats()
        
        self.stats_text.delete(1.0, tk.END)
        
        stats_str = f"Rows: {stats.get('total_rows', 'N/A')}\n"
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
        
        # Update plot if we have data
        if hasattr(self, 'canvas') and self.data_processor.data is not None:
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
            
            # Update plot if we have data
            if hasattr(self, 'canvas') and self.data_processor.data is not None:
                self._update_plot()
                
        except (ValueError, tk.TclError):
            # Invalid entry - reset to current slider value or default
            self.bin_count_var.set(DEFAULT_BIN_COUNT)
    
    def _on_stats_toggle(self):
        """Handle statistical lines toggle change."""
        # If we have a current plot, update it
        if hasattr(self, 'canvas') and self.data_processor.data is not None:
            self._update_plot()
    
    def create_plot(self):
        """Create and display the histogram plot."""
        # Update data processor with current settings
        mode = self.data_mode_var.get()
        self.data_processor.set_data_mode(mode)
        
        # Update column selections
        if mode == 'pre_aggregated':
            self.data_processor.set_columns(
                self.size_column_var.get(),
                self.frequency_column_var.get()
            )
        else:  # raw_measurements
            self.data_processor.set_columns(
                self.size_column_var.get()
            )
        
        size_data = self.data_processor.get_size_data()
        frequency_data = self.data_processor.get_frequency_data()
        
        if size_data is None:
            messagebox.showerror("Error", "Please select a valid size column.")
            return
        
        # Create the plot
        figure = self.plotter.create_histogram(
            size_data, frequency_data, self.bin_count_var.get(),
            show_stats_lines=self.show_stats_lines_var.get(),
            data_mode=mode
        )
        
        if figure is not None:
            self.current_figure = figure  # Store reference to current figure
            self._display_plot(figure)
        else:
            messagebox.showerror("Error", "Failed to create plot.")
    
    def _update_plot(self):
        """Update the existing plot with new bin count or settings."""
        if not hasattr(self, 'canvas'):
            return
        
        size_data = self.data_processor.get_size_data()
        frequency_data = self.data_processor.get_frequency_data()
        
        if size_data is not None:
            # For updates, just recreate the entire plot display
            # This is more reliable than trying to swap figures
            mode = self.data_mode_var.get()
            
            figure = self.plotter.create_histogram(
                size_data, frequency_data, self.bin_count_var.get(),
                show_stats_lines=self.show_stats_lines_var.get(),
                data_mode=mode
            )
            
            if figure is not None:
                self._display_plot(figure)
    
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