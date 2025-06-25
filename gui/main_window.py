# gui/main_window.py
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
        
        self._create_widgets()
        self._create_layout()
    
    def _create_widgets(self):
        """Create all GUI widgets."""
        # Main frame
        self.main_frame = ttk.Frame(self.root)
        
        # Control frame (left side)
        self.control_frame = ttk.LabelFrame(self.main_frame, text="Controls", padding=10)
        
        # File loading
        ttk.Label(self.control_frame, text="Data File:").grid(row=0, column=0, sticky='w', pady=2)
        self.load_button = ttk.Button(self.control_frame, text="Load CSV", command=self.load_file)
        self.load_button.grid(row=0, column=1, sticky='ew', pady=2)
        
        # Random data generation
        ttk.Separator(self.control_frame, orient='horizontal').grid(row=1, column=0, columnspan=3, sticky='ew', pady=5)
        
        ttk.Label(self.control_frame, text="Generate Random Data:").grid(row=2, column=0, sticky='w', pady=2)
        
        # Random data controls frame
        random_frame = ttk.Frame(self.control_frame)
        random_frame.grid(row=3, column=0, columnspan=3, sticky='ew', pady=2)
        
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
        
        ttk.Separator(self.control_frame, orient='horizontal').grid(row=4, column=0, columnspan=3, sticky='ew', pady=5)
        
        # Column selection
        ttk.Label(self.control_frame, text="Size Column:").grid(row=5, column=0, sticky='w', pady=2)
        self.size_combo = ttk.Combobox(self.control_frame, textvariable=self.size_column_var, state='readonly')
        self.size_combo.grid(row=5, column=1, sticky='ew', pady=2)
        
        ttk.Label(self.control_frame, text="Frequency Column:").grid(row=6, column=0, sticky='w', pady=2)
        self.frequency_combo = ttk.Combobox(self.control_frame, textvariable=self.frequency_column_var, state='readonly')
        self.frequency_combo.grid(row=6, column=1, sticky='ew', pady=2)
        
        # Bin count control
        ttk.Label(self.control_frame, text="Bins:").grid(row=7, column=0, sticky='w', pady=2)
        self.bin_scale = ttk.Scale(self.control_frame, from_=MIN_BIN_COUNT, to=MAX_BIN_COUNT, 
                                  variable=self.bin_count_var, orient='horizontal', command=self._on_bin_change)
        self.bin_scale.grid(row=7, column=1, sticky='ew', pady=2)
        
        self.bin_label = ttk.Label(self.control_frame, text=str(DEFAULT_BIN_COUNT))
        self.bin_label.grid(row=7, column=2, pady=2)
        
        # Plot button
        self.plot_button = ttk.Button(self.control_frame, text="Create Plot", 
                                     command=self.create_plot, state='disabled')
        self.plot_button.grid(row=8, column=0, columnspan=2, sticky='ew', pady=10)
        
        # Stats display
        self.stats_frame = ttk.LabelFrame(self.control_frame, text="Data Info", padding=5)
        self.stats_frame.grid(row=9, column=0, columnspan=3, sticky='ew', pady=5)
        
        self.stats_text = tk.Text(self.stats_frame, height=6, width=30)
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
        """Load a CSV file."""
        file_path = filedialog.askopenfilename(
            title="Select CSV file",
            filetypes=SUPPORTED_FILE_TYPES
        )
        
        if file_path:
            if self.data_processor.load_csv(file_path):
                self._update_column_combos()
                self._update_stats_display()
                self.plot_button.config(state='normal')
                messagebox.showinfo("Success", "File loaded successfully!")
            else:
                messagebox.showerror("Error", "Failed to load file. Please check the file format.")
    
    def generate_random_data(self):
        """Generate random particle data for testing."""
        try:
            n = self.random_count_var.get()
            distribution = self.distribution_var.get()
            
            if n <= 0:
                messagebox.showerror("Error", "Number of points must be positive.")
                return
            
            if self.data_processor.generate_random_data(n, distribution):
                self._update_column_combos()
                self._update_stats_display()
                self.plot_button.config(state='normal')
                messagebox.showinfo("Success", f"Generated {n} random data points!")
            else:
                messagebox.showerror("Error", "Failed to generate random data.")
                
        except tk.TclError:
            messagebox.showerror("Error", "Please enter a valid number of points.")
    
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
        
        if 'size_min' in stats:
            stats_str += f"\nSize Range:\n"
            stats_str += f"  Min: {stats['size_min']:.3f}\n"
            stats_str += f"  Max: {stats['size_max']:.3f}\n"
            stats_str += f"  Mean: {stats['size_mean']:.3f}\n"
        
        self.stats_text.insert(1.0, stats_str)
    
    def _on_bin_change(self, value):
        """Handle bin count scale change."""
        bin_count = int(float(value))
        self.bin_label.config(text=str(bin_count))
        
        # If we have a current plot, update it
        if hasattr(self, 'canvas') and self.data_processor.data is not None:
            self._update_plot()
    
    def create_plot(self):
        """Create and display the histogram plot."""
        # Update column selections
        self.data_processor.set_columns(
            self.size_column_var.get(),
            self.frequency_column_var.get()
        )
        
        size_data = self.data_processor.get_size_data()
        frequency_data = self.data_processor.get_frequency_data()
        
        if size_data is None:
            messagebox.showerror("Error", "Please select a valid size column.")
            return
        
        # Create the plot
        figure = self.plotter.create_histogram(
            size_data, frequency_data, self.bin_count_var.get()
        )
        
        if figure is not None:
            self._display_plot(figure)
    
    def _update_plot(self):
        """Update the existing plot with new bin count."""
        if not hasattr(self, 'canvas'):
            return
        
        size_data = self.data_processor.get_size_data()
        frequency_data = self.data_processor.get_frequency_data()
        
        if size_data is not None:
            # Clear the existing plot properly
            if hasattr(self, 'canvas') and self.canvas.figure:
                self.canvas.figure.clear()
            
            # Create new plot
            figure = self.plotter.create_histogram(
                size_data, frequency_data, self.bin_count_var.get()
            )
            
            if figure is not None:
                # Update the canvas with the new figure
                self.canvas.figure = figure
                self.canvas.draw()
    
    def _display_plot(self, figure):
        """Display the plot in the GUI."""
        # Clear existing plot widgets completely
        for widget in self.plot_frame.winfo_children():
            widget.destroy()
        
        # Clear any existing matplotlib figures
        if hasattr(self, 'canvas'):
            if hasattr(self.canvas, 'figure') and self.canvas.figure:
                plt.close(self.canvas.figure)
            del self.canvas
        
        # Create new canvas with the figure
        self.canvas = FigureCanvasTkAgg(figure, self.plot_frame)
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
                if hasattr(self.canvas, 'figure') and self.canvas.figure:
                    plt.close(self.canvas.figure)
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