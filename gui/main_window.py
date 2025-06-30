"""
DEBUG VERSION - Main GUI window for the Particle Data Analyzer.
This version includes extensive logging to diagnose plot overlay issues.
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
    """Main application window with debug logging."""
    
    def __init__(self, root):
        self.root = root
        self.root.title("Particle Data Analyzer - DEBUG VERSION")
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
        
        # Debug tracking
        self.plot_counter = 0
        self.update_counter = 0
        self.current_figure = None  # Track our current figure separately
        
        self._create_widgets()
        self._create_layout()
        
        logger.info("MainWindow initialized successfully")
    
    def _create_widgets(self):
        """Create all GUI widgets."""
        logger.info("Creating GUI widgets...")
        
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
        
        # Create frame for bin controls
        bin_frame = ttk.Frame(self.control_frame)
        bin_frame.grid(row=7, column=1, columnspan=2, sticky='ew', pady=2)
        
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
        self.stats_lines_check.grid(row=8, column=0, columnspan=2, sticky='w', pady=2)
        
        # Plot button
        self.plot_button = ttk.Button(self.control_frame, text="Create Plot", 
                                     command=self.create_plot, state='disabled')
        self.plot_button.grid(row=9, column=0, columnspan=2, sticky='ew', pady=10)
        
        # DEBUG: Add manual cleanup button
        self.debug_cleanup_button = ttk.Button(self.control_frame, text="DEBUG: Force Cleanup", 
                                              command=self._debug_force_cleanup)
        self.debug_cleanup_button.grid(row=10, column=0, columnspan=2, sticky='ew', pady=5)
        
        # Stats display
        self.stats_frame = ttk.LabelFrame(self.control_frame, text="Data Info", padding=5)
        self.stats_frame.grid(row=11, column=0, columnspan=3, sticky='ew', pady=5)
        
        self.stats_text = tk.Text(self.stats_frame, height=6, width=30)
        self.stats_text.pack(fill='both', expand=True)
        
        # Plot frame (right side)
        self.plot_frame = ttk.LabelFrame(self.main_frame, text="Plot", padding=10)
        
        # Configure column weights
        self.control_frame.columnconfigure(1, weight=1)
        
        logger.info("GUI widgets created successfully")
    
    def _create_layout(self):
        """Arrange widgets in the window."""
        logger.info("Creating layout...")
        self.main_frame.pack(fill='both', expand=True, padx=5, pady=5)
        
        # Use grid for main layout
        self.main_frame.columnconfigure(1, weight=1)
        self.main_frame.rowconfigure(0, weight=1)
        
        self.control_frame.grid(row=0, column=0, sticky='nsew', padx=(0, 5))
        self.plot_frame.grid(row=0, column=1, sticky='nsew')
        logger.info("Layout created successfully")
    
    def load_file(self):
        """Load a CSV file."""
        logger.info("Load file button clicked")
        file_path = filedialog.askopenfilename(
            title="Select CSV file",
            filetypes=SUPPORTED_FILE_TYPES
        )
        
        if file_path:
            logger.info(f"Selected file: {file_path}")
            if self.data_processor.load_csv(file_path):
                self._update_column_combos()
                self._update_stats_display()
                self.plot_button.config(state='normal')
                messagebox.showinfo("Success", "File loaded successfully!")
            else:
                messagebox.showerror("Error", "Failed to load file. Please check the file format.")
    
    def generate_random_data(self):
        """Generate random particle data for testing."""
        logger.info("Generate random data button clicked")
        try:
            n = self.random_count_var.get()
            distribution = self.distribution_var.get()
            
            logger.info(f"Generating {n} points with {distribution} distribution")
            
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
        logger.info("Updating column combos")
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
        logger.info("Updating stats display")
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
    
    def _on_bin_scale_move(self, value):
        """Handle bin count scale movement - convert to int and update display only."""
        # Convert float value to integer and update the IntVar
        bin_count = int(float(value))
        self.bin_count_var.set(bin_count)
        logger.info(f"Bin count slider moved to: {bin_count} (no plot update)")
    
    def _on_bin_change(self, value):
        """Handle bin count scale change - now only for display updates."""
        # This method is now redundant but kept for compatibility
        bin_count = int(float(value))
        logger.info(f"Bin count changed to: {bin_count} (no plot update)")
    
    def _on_bin_scale_release(self, event):
        """Handle bin count scale release - triggers plot update."""
        # Ensure we have an integer value
        bin_count = int(self.bin_count_var.get())
        self.bin_count_var.set(bin_count)  # Force integer update
        
        logger.info(f"Bin count slider released at: {bin_count}")
        
        # Validate and constrain the value
        if bin_count < MIN_BIN_COUNT:
            bin_count = MIN_BIN_COUNT
            self.bin_count_var.set(bin_count)
        elif bin_count > MAX_BIN_COUNT:
            bin_count = MAX_BIN_COUNT  
            self.bin_count_var.set(bin_count)
        
        # Update plot if we have data
        if hasattr(self, 'canvas') and self.data_processor.data is not None:
            logger.info("Calling _update_plot from bin scale release")
            self._update_plot()
    
    def _on_bin_entry_change(self, event):
        """Handle bin count entry field changes."""
        try:
            bin_count = int(self.bin_count_var.get())
            logger.info(f"Bin count entry changed to: {bin_count}")
            
            # Validate and constrain the value
            if bin_count < MIN_BIN_COUNT:
                bin_count = MIN_BIN_COUNT
                self.bin_count_var.set(bin_count)
                logger.info(f"Bin count constrained to minimum: {bin_count}")
            elif bin_count > MAX_BIN_COUNT:
                bin_count = MAX_BIN_COUNT
                self.bin_count_var.set(bin_count)
                logger.info(f"Bin count constrained to maximum: {bin_count}")
            
            # Update plot if we have data
            if hasattr(self, 'canvas') and self.data_processor.data is not None:
                logger.info("Calling _update_plot from bin entry change")
                self._update_plot()
                
        except (ValueError, tk.TclError):
            # Invalid entry - reset to current slider value or default
            logger.warning("Invalid bin count entry - resetting")
            self.bin_count_var.set(DEFAULT_BIN_COUNT)
    
    def _on_stats_toggle(self):
        """Handle statistical lines toggle change."""
        show_stats = self.show_stats_lines_var.get()
        logger.info(f"Stats lines toggled to: {show_stats}")
        
        # If we have a current plot, update it
        if hasattr(self, 'canvas') and self.data_processor.data is not None:
            logger.info("Calling _update_plot from stats toggle")
            self._update_plot()
    
    def create_plot(self):
        """Create and display the histogram plot."""
        self.plot_counter += 1
        logger.info(f"=== CREATE PLOT #{self.plot_counter} ===")
        
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
        
        logger.info(f"Creating plot with {len(size_data)} data points")
        logger.info(f"Current matplotlib figures: {len(plt.get_fignums())}")
        
        # Create the plot
        figure = self.plotter.create_histogram(
            size_data, frequency_data, self.bin_count_var.get(),
            show_stats_lines=self.show_stats_lines_var.get()
        )
        
        if figure is not None:
            logger.info(f"Plot created successfully. Figure ID: {figure.number}")
            logger.info(f"Matplotlib figures after creation: {len(plt.get_fignums())}")
            self.current_figure = figure  # Store reference to current figure
            self._display_plot(figure)
        else:
            logger.error("Failed to create plot")
    
    def _update_plot(self):
        """Update the existing plot with new bin count or settings."""
        self.update_counter += 1
        logger.info(f"=== UPDATE PLOT #{self.update_counter} ===")
        
        if not hasattr(self, 'canvas'):
            logger.warning("No canvas found for update")
            return
        
        logger.info(f"Canvas exists: {hasattr(self, 'canvas')}")
        logger.info(f"Current matplotlib figures before update: {len(plt.get_fignums())}")
        logger.info(f"Figure numbers: {plt.get_fignums()}")
        
        size_data = self.data_processor.get_size_data()
        frequency_data = self.data_processor.get_frequency_data()
        
        if size_data is not None:
            logger.info(f"Updating plot with {len(size_data)} data points")
            
            # For updates, just recreate the entire plot display
            # This is more reliable than trying to swap figures
            figure = self.plotter.create_histogram(
                size_data, frequency_data, self.bin_count_var.get(),
                show_stats_lines=self.show_stats_lines_var.get()
            )
            
            if figure is not None:
                logger.info(f"New figure created for update. Figure ID: {figure.number}")
                logger.info(f"Using full display recreation for reliability")
                self._display_plot(figure)
            else:
                logger.error("Failed to create updated plot")
        else:
            logger.warning("No size data available for update")
    
    def _display_plot(self, figure):
        """Display the plot in the GUI."""
        logger.info(f"=== DISPLAY PLOT ===")
        logger.info(f"Plot frame children before clear: {len(self.plot_frame.winfo_children())}")
        
        # Clear existing plot widgets completely
        for i, widget in enumerate(self.plot_frame.winfo_children()):
            logger.info(f"Destroying widget {i}: {type(widget)}")
            widget.destroy()
        
        logger.info(f"Plot frame children after clear: {len(self.plot_frame.winfo_children())}")
        
        # Clear any existing matplotlib figures
        if hasattr(self, 'canvas'):
            logger.info("Cleaning up existing canvas")
            if self.current_figure and self.current_figure != figure:
                # Only close if it's a different figure than the one we're displaying
                old_fig_id = self.current_figure.number
                logger.info(f"Closing old figure ID: {old_fig_id}")
                plt.close(self.current_figure)
            else:
                logger.info("Skipping figure close - same as new figure or no current figure")
            del self.canvas
        
        logger.info(f"Matplotlib figures after cleanup: {len(plt.get_fignums())}")
        
        # Create new canvas with the figure
        logger.info(f"Creating new canvas with figure ID: {figure.number}")
        self.canvas = FigureCanvasTkAgg(figure, self.plot_frame)
        self.current_figure = figure  # Update our reference
        self.canvas.draw()
        
        # Pack the canvas widget
        canvas_widget = self.canvas.get_tk_widget()
        canvas_widget.pack(fill='both', expand=True)
        logger.info("Canvas widget packed")
        
        # Add toolbar
        toolbar = NavigationToolbar2Tk(self.canvas, self.plot_frame)
        toolbar.update()
        logger.info("Toolbar added")
        
        logger.info(f"Final matplotlib figures: {len(plt.get_fignums())}")
        logger.info(f"Plot frame children after display: {len(self.plot_frame.winfo_children())}")
    
    def _replace_plot_figure(self, new_figure, old_figure=None):
        """Replace the current plot figure without recreating widgets."""
        logger.info(f"=== REPLACE PLOT FIGURE ===")
        logger.info(f"Replacing with figure ID: {new_figure.number}")
        
        try:
            # Close the old figure properly using our stored reference
            if old_figure:
                old_fig_id = old_figure.number
                logger.info(f"Closing old figure ID: {old_fig_id}")
                plt.close(old_figure)
            elif hasattr(self.canvas, 'figure') and self.canvas.figure:
                # Fallback to canvas figure if no stored reference
                old_fig_id = self.canvas.figure.number
                logger.info(f"Closing canvas figure ID: {old_fig_id}")
                plt.close(self.canvas.figure)
            
            logger.info(f"Matplotlib figures after closing old: {len(plt.get_fignums())}")
            
            # Update the canvas with the new figure
            logger.info("Setting new figure on canvas")
            self.canvas.figure = new_figure
            self.canvas.draw()
            
            # Force a GUI update to ensure proper rendering
            self.canvas.get_tk_widget().update()
            logger.info("Canvas updated and redrawn")
            
            logger.info(f"Final matplotlib figures: {len(plt.get_fignums())}")
            
        except Exception as e:
            logger.error(f"Error replacing plot figure: {e}")
            # If replacement fails, fall back to full plot recreation
            logger.info("Falling back to full plot recreation")
            self._display_plot(new_figure)
    
    def _debug_force_cleanup(self):
        """DEBUG: Force cleanup of all matplotlib figures."""
        logger.info("=== FORCE CLEANUP DEBUG ===")
        logger.info(f"Matplotlib figures before cleanup: {len(plt.get_fignums())}")
        logger.info(f"Figure numbers: {plt.get_fignums()}")
        
        # Close all matplotlib figures
        plt.close('all')
        
        # Clear plot frame
        for widget in self.plot_frame.winfo_children():
            widget.destroy()
        
        # Reset canvas
        if hasattr(self, 'canvas'):
            del self.canvas
        
        if hasattr(self, 'current_figure'):
            self.current_figure = None
        
        logger.info(f"Matplotlib figures after cleanup: {len(plt.get_fignums())}")
        messagebox.showinfo("Debug", "Forced cleanup completed - check console for details")
    
    def _on_closing(self):
        """Handle application closing cleanly."""
        logger.info("=== APPLICATION CLOSING ===")
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

#Second test; viewing testingHistogram branch change