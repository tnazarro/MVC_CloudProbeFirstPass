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
import matplotlib.figure
import numpy as np
from datetime import datetime
import sys
from typing import Dict, List, Optional, Any

from core.data_processor import ParticleDataProcessor
from core.dataset_manager import DatasetManager
from core.plotter import ParticlePlotter
from config.constants import *
from core.file_queue import FileQueue
from gui.dialogs.file_preview import FilePreviewDialog
from gui.dialogs.load_choice import LoadChoiceDialog
from gui.widgets import *


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
        
        # Bind mousewheel only when mouse is over this canvas
        self.canvas.bind("<Enter>", lambda e: self.canvas.bind_all("<MouseWheel>", self._on_mousewheel))
        self.canvas.bind("<Leave>", lambda e: self.canvas.unbind_all("<MouseWheel>"))

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
        
        self.show_config_warning = False
        
        #Check config status and show banner if needed
        if not self.dataset_manager.config_manager.is_config_file_loaded():
            self.show_config_warning = True
            # Banner will be shown after widgets are created

        # GUI variables
        self.bin_count_var = tk.IntVar(value=DEFAULT_BIN_COUNT)
        self.size_column_var = tk.StringVar()
        self.show_stats_lines_var = tk.BooleanVar(value=False)
        self.data_mode_var = tk.StringVar(value='raw_measurements')  # 'pre_aggregated' or 'raw_measurements'
        self.skip_rows_var = tk.IntVar(value=0)
        

        # Variable for gaussian fit
        self.show_gaussian_fit_var = tk.BooleanVar(value=True)

        # Analysis mode selection variable (calibration vs verification)
        self.analysis_mode_var = tk.StringVar(value='calibration')
        
        # Inline tag editing variable
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
        
        #Show banner after widgets exist
        if self.show_config_warning:
            self._show_config_warning_banner()

        # Initialize UI state
        self._update_dataset_ui()
        self._update_analysis_mode_ui()
        self._setup_keyboard_shortcuts()
    
    def _create_widgets(self):
        """Create all GUI widgets using container panels."""
        # Main frame (keeping for compatibility but not used)
        self.main_frame = ttk.Frame(self.root)
        
        # Control frame (left side) - now goes inside scrollable frame
        self.control_frame = ttk.LabelFrame(self.scrollable_frame.scrollable_frame, text="Controls", padding=10)
        
        # Register float validation (needed before DatasetListPanel creation)
        self.validate_float = self.root.register(self._validate_float_input)
        
        # Serial number variable (needed by AnalysisModePanel)
        self.serial_var = tk.StringVar(value=self.dataset_manager.instrument_serial_number)
        self.serial_var.trace_add('write', self._on_serial_number_change)
        
        # Analysis Mode Panel
        self.analysis_mode_panel = AnalysisModePanel(
            self.control_frame,
            on_load_calibration=self._load_for_calibration,
            on_load_verification=self._load_for_verification,
            serial_var=self.serial_var
        )
        self.analysis_mode_panel.pack(fill='x', pady=(0, 10))
        
        # Queue Status Panel
        self.queue_status_panel = QueueStatusPanel(
            self.control_frame,
            font_style=FONT_STATUS
        )
        self.queue_status_panel.pack(fill='x', pady=2)
        
        # Dataset List Panel (includes treeview, tag editor)
        self.dataset_list_panel = DatasetListPanel(
            self.control_frame,
            current_tag_var=self.current_tag_var,
            on_dataset_select=self._on_dataset_select,
            on_tag_save=self._save_current_tag,
            on_dataset_reorder=self._handle_dataset_reorder,
            validate_float_func=self.validate_float,
            treeview_height=8
        )
        self.dataset_list_panel.pack(fill='x', pady=(10, 10))
        
        # Bind tag entry events
        self.current_tag_var.trace('w', self._on_tag_var_change)
        self.dataset_list_panel.tag_entry.bind('<Return>', self._on_tag_entry_return)
        self.dataset_list_panel.tag_entry.bind('<FocusOut>', self._on_tag_entry_focusout)
        
        # Dataset Management Panel
        self.dataset_mgmt_panel = DatasetManagementPanel(
            self.control_frame,
            on_reset_config=self.reset_to_config_defaults,
            on_edit_notes=self.edit_dataset_notes,
            on_remove=self.remove_dataset,
            on_clear_all=self.clear_all_datasets,
            on_help=self.show_help_dialog
        )
        self.dataset_mgmt_panel.pack(fill='x', pady=5)
        
        # Stats Panel
        self.stats_panel = StatsPanel(
            self.control_frame,
            text_height=8,
            text_width=30
        )
        self.stats_panel.pack(fill='x', pady=5)
        
        # Analysis Controls Panel
        self.analysis_controls_panel = AnalysisControlsPanel(
            self.control_frame,
            size_column_var=self.size_column_var,
            bin_count_var=self.bin_count_var,
            on_column_change=self._on_column_change,
            on_bin_change=self._on_bin_entry_change,
            on_gaussian_info=self.show_gaussian_info,
            min_bins=MIN_BIN_COUNT,
            max_bins=MAX_BIN_COUNT
        )
        self.analysis_controls_panel.pack(fill='x', pady=5)
        
        # Action Buttons Panel
        self.action_buttons_panel = ActionButtonsPanel(
            self.control_frame,
            on_report=self.generate_report,
            reports_available=REPORTS_AVAILABLE
        )
        self.action_buttons_panel.pack(fill='x', pady=5)
        
        # === PLOT FRAME ===
        self.plot_frame = ttk.LabelFrame(self.plot_scrollable_frame.scrollable_frame, text="Plot", padding=10)
        
        # Plot Navigation Panel
        self.plot_nav_panel = PlotNavigationPanel(
            self.plot_frame,
            on_previous=self.previous_dataset,
            on_next=self.next_dataset,
            on_save=self.save_graph
        )
        self.plot_nav_panel.pack(fill='x', pady=(0, 10))
    
    def save_graph(self):
        """Save the current graph as a PNG image."""
        if not hasattr(self, 'canvas') or not self.current_figure:
            messagebox.showerror("Error", "No graph to save. Please create a plot first.")
            return
        
        active_dataset = self.dataset_manager.get_active_dataset()
        if not active_dataset:
            messagebox.showerror("Error", "No active dataset.")
            return
        
        # Generate default filename with dataset tag and timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        dataset_tag = active_dataset['tag'].replace('.', '_').replace(' ', '_')
        default_filename = f"{dataset_tag}_bead_size_{timestamp}.png"
        
        # Show save file dialog
        file_path = filedialog.asksaveasfilename(
            title="Save Graph As",
            defaultextension=".png",
            initialfile=default_filename,
            filetypes=[("PNG files", "*.png")]
        )
        
        if not file_path:
            return  # User cancelled
        
        try:
            # Save the plot using the plotter's save method
            success = self.plotter.save_plot(file_path, dpi=EXPORT_DPI)
            
            if success:
                messagebox.showinfo("Success", f"Graph saved successfully!\nSaved to: {file_path}")
            else:
                messagebox.showerror("Error", "Failed to save graph.")
                
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save graph: {str(e)}")
    
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
                                      text="No plot to display\nLoad data to begin",
                                      font=('TkDefaultFont', 10),
                                      foreground='gray',
                                      justify='center')
        self.no_plot_label.pack(expand=True)
    
    # === DIRECT LOAD METHODS ===
    
    def _show_config_warning_banner(self):
        """Show persistent config warning in queue status area."""
        self.queue_status_panel.set_status(
            text="⚠️  Config: Using Built-in Defaults (may be outdated)",
            foreground='red'
        )
        logger.info("Displaying config warning banner")

    def _load_for_calibration(self):
        """Direct calibration loading - sets mode and loads single file."""
        current_mode = self.analysis_mode_var.get()
        
        if current_mode != 'calibration' and self.dataset_manager.has_datasets():
            if not self._confirm_clear_datasets_if_needed():
                return
        
        self.analysis_mode_var.set('calibration')
        self._update_analysis_mode_ui()
        self.load_multiple_files()
        
    def _load_for_verification(self):
        """Direct verification loading - sets mode and loads multiple files."""
        current_mode = self.analysis_mode_var.get()
        
        if current_mode != 'verification' and self.dataset_manager.has_datasets():
            if not self._confirm_clear_datasets_if_needed():
                return
        
        self.analysis_mode_var.set('verification') 
        self._update_analysis_mode_ui()
        self.load_multiple_files()
    
    def _on_serial_number_change(self, *args):
        """Handle serial number changes - auto-sync to DatasetManager."""
        new_serial = self.serial_var.get().strip()
        self.dataset_manager.instrument_serial_number = new_serial
        logger.debug(f"Serial number updated: {new_serial}")

    def _confirm_clear_datasets_if_needed(self):
        """
        Returns:
            bool: True if user confirmed or no datasets to clear, False if cancelled
        """
        if not self.dataset_manager.has_datasets():
            return True  # No datasets to clear, proceed
        
        dataset_count = self.dataset_manager.get_dataset_count()
        dataset_names = [dataset['tag'] for dataset in self.dataset_manager.get_all_datasets_ordered()]
        
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
                self.dataset_list_panel.tag_save_btn.config(state='normal')
            else:
                self.dataset_list_panel.tag_save_btn.config(state='disabled')
    
    def _on_tag_entry_return(self, event):
        """Handle Enter key in tag entry - save immediately."""
        self._save_current_tag()
        self.dataset_list_panel.tag_entry.selection_clear()  # Clear selection after save
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
                self.dataset_list_panel.tag_save_btn.config(state='disabled')
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
            self.dataset_list_panel.tag_entry.config(state='normal')
            self.dataset_list_panel.tag_save_btn.config(state='disabled')  # Start with save disabled
        else:
            self.current_tag_var.set("")
            self.dataset_list_panel.tag_entry.config(state='disabled')
            self.dataset_list_panel.tag_save_btn.config(state='disabled')
        
        self._updating_tag = False
    
    def _on_analysis_mode_change(self):
        """This method is no longer called by radio buttons, but kept for internal mode changes."""
        mode = self.analysis_mode_var.get()
        logger.info(f"Analysis mode changed to: {mode}")
        
        # Update mode description
        if mode == 'calibration':
            self.analysis_mode_panel.mode_description.config(
                text="Current Mode: Calibration (Single/Multi dataset analysis)",
                foreground='blue'
            )
        else:  # verification
            self.analysis_mode_panel.mode_description.config(
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
            self.analysis_mode_panel.mode_description.config(
                text="Current Mode: Calibration (Single/Multi dataset analysis)",
                foreground='blue'
            )
        else:
            self.analysis_mode_panel.mode_description.config(
                text="Current Mode: Verification (Multi-dataset comparison)",
                foreground='green'
            )
        
        # Update other UI elements based on mode
        self._update_navigation_buttons_for_mode()
        
        logger.info(f"UI updated for {mode} mode")
    
    def _update_report_button_state_for_mode(self):
        """Update report button state based on mode and data availability."""
        mode = self.analysis_mode_var.get()
        
        if not REPORTS_AVAILABLE:
            self.action_buttons_panel.report_button.config(state='disabled', text="Generate Report (ReportLab not installed)")
            return
        
        if mode == 'calibration':
            # In calibration mode, disable report generation
            self.action_buttons_panel.report_button.config(
                state='disabled',
                text="Generate Report (Verification mode only)"
            )
        else:  # verification mode
            # In verification mode, enable if we have data and plot
            if hasattr(self, 'canvas') and self.current_figure:
                self.action_buttons_panel.report_button.config(state='normal', text="Generate Report")
            else:
                self.action_buttons_panel.report_button.config(state='disabled', text="Generate Report")
    
    def _update_navigation_buttons_for_mode(self):
        """Update navigation buttons based on mode."""
        mode = self.analysis_mode_var.get()
        has_datasets = self.dataset_manager.has_datasets()
        has_multiple = self.dataset_manager.get_dataset_count() > 1
        has_plot = hasattr(self, 'canvas') and self.current_figure
        
        if mode == 'calibration':
            # In calibration mode, navigation is less relevant but still functional
            self.plot_nav_panel.prev_btn.config(state='normal' if has_multiple else 'disabled')
            self.plot_nav_panel.next_btn.config(state='normal' if has_multiple else 'disabled')
        else:  # verification mode
            # In verification mode, navigation is fully functional
            self.plot_nav_panel.prev_btn.config(state='normal' if has_multiple else 'disabled')
            self.plot_nav_panel.next_btn.config(state='normal' if has_multiple else 'disabled')
        
        # Save graph button is enabled when there's a plot to save
        self.plot_nav_panel.save_btn.config(state='normal' if has_plot else 'disabled')
    
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
                
                self._update_UI()
                
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
        
        # Track initial dataset count for summary message
        self._initial_dataset_count = self.dataset_manager.get_dataset_count()
        
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

        
        # Enhanced keyboard shortcuts for queue preview
        preview_dialog.parent.bind('<Return>', lambda e: self._handle_queue_file_load())
        preview_dialog.parent.bind('<Escape>', lambda e: self._cancel_queue_processing(self))
        preview_dialog.parent.bind('<Control-s>', lambda e: self._on_queue_skip(self))  # Ctrl+S to skip

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
                
                self._update_UI()

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

    def _update_UI(self):
        """Update UI elements after queue file load."""
        self._update_dataset_ui()
        self._load_active_dataset_settings()
        self._update_column_combos()
        self._update_stats_display()
        self._update_report_button_state()

        #Also auto-create first plot if none exists
        if not hasattr(self, 'canvas'):
            self.create_plot()

        # Update scroll region after adding dataset
        self.scrollable_frame.update_scroll_region()

    def _on_queue_skip(self):
        """Handle skip button in queue processing."""
        self.file_queue.skip_current_file("User skipped during preview")
        self._process_current_queue_file()

    def _finish_queue_processing(self):
        """Finish queue processing and show summary."""
        summary = self.file_queue.get_summary()
        current_total = self.dataset_manager.get_dataset_count()
        
        summary_text = f"Queue Processing Complete!\n\n"
        summary_text += f"Total files: {summary['total_files']}\n"
        summary_text += f"Successfully loaded: {summary['processed']}\n"
        summary_text += f"Failed: {summary['failed']}\n"
        summary_text += f"Skipped: {summary['skipped']}\n"
        summary_text += f"Success rate: {summary['success_rate']:.1f}%\n\n"
        
        # Show append info
        if self._initial_dataset_count > 0:
            summary_text += f"Added {summary['processed']} datasets ({current_total} total now loaded)"
        else:
            summary_text += f"Loaded {current_total} datasets"
        
        messagebox.showinfo("Queue Complete", summary_text)
        self._update_queue_status()

    def _cancel_queue_processing(self):
        """Cancel queue processing."""
        self.file_queue.clear_queue()
        self._update_queue_status()
        messagebox.showinfo("Cancelled", "Queue processing was cancelled.")

    def _update_queue_status(self):
        """Update the queue status display."""
        # Don't overwrite config warning
        if self.show_config_warning:
            return

        if not self.file_queue.has_more_files() and len(self.file_queue.files) == 0:
            self.queue_status_panel.set_status(text="")
            return

        info = self.file_queue.get_current_file_info()
        
        if info['is_complete']:
            self.queue_status_panel.set_status(text="Queue processing complete")
        elif info['has_current_file']:
            current_file = self.file_queue.get_current_file()
            status_text = f"Queue: {info['current_index'] + 1}/{info['total_files']} - {current_file['filename']}"
            if info['processed_count'] > 0 or info['failed_count'] > 0 or info['skipped_count'] > 0:
                status_text += f" (P:{info['processed_count']} F:{info['failed_count']} S:{info['skipped_count']})"
            self.queue_status_panel.set_status(text=status_text)
        else:
            self.queue_status_panel.set_status(text=f"Queue ready: {info['total_files']} files")
    
    # === KEYBOARD SHORTCUTS ===

    def _setup_keyboard_shortcuts(self):
        """Setup keyboard shortcuts for the main window."""
        # File loading shortcuts - these work perfectly with compound keys
        self.root.bind('<Control-o>', lambda e: self._load_for_calibration())
        self.root.bind('<Control-Shift-O>', lambda e: self._load_for_verification())
        
        # Dataset navigation shortcuts
        self.root.bind('<Up>', lambda e: self._navigate_dataset_previous())
        self.root.bind('<Down>', lambda e: self._navigate_dataset_next())
        self.root.bind('<Left>', lambda e: self._navigate_dataset_previous())
        self.root.bind('<Right>', lambda e: self._navigate_dataset_next())
        
        # Make sure the main window can receive focus for keyboard events
        self.root.focus_set()

    def _is_text_input_widget(self, widget):
        """Check if widget is a text input that should handle keys normally."""
        if widget is None:
            return False
        
        # Check for common text input widgets
        if isinstance(widget, (tk.Entry, tk.Text, ttk.Entry, ttk.Combobox)):
            return True
        
        return False

    def _navigate_dataset_previous(self):
        """Navigate to previous dataset if datasets are loaded."""
        if self.dataset_manager.has_datasets() and self.dataset_manager.get_dataset_count() > 1:
            prev_id = self.dataset_manager.get_previous_dataset_id()
            if prev_id is not None:
                self.dataset_manager.set_active_dataset(prev_id)
                self._load_active_dataset_settings()
                self._update_dataset_ui()
                self._update_column_combos()
                self._update_stats_display()
                
                # Auto-update plot if one exists
                if hasattr(self, 'canvas'):
                    self._update_plot()

    def _navigate_dataset_next(self):
        """Navigate to next dataset if datasets are loaded."""
        if self.dataset_manager.has_datasets() and self.dataset_manager.get_dataset_count() > 1:
            next_id = self.dataset_manager.get_next_dataset_id()
            if next_id is not None:
                self.dataset_manager.set_active_dataset(next_id)
                self._load_active_dataset_settings()
                self._update_dataset_ui()
                self._update_column_combos()
                self._update_stats_display()
                
                # Auto-update plot if one exists
                if hasattr(self, 'canvas'):
                    self._update_plot()


    # === DATASET MANAGEMENT METHODS ===
    
    def _update_dataset_ui(self):
        """Update all dataset-related UI elements."""
        self._update_dataset_treeview()
        self._update_navigation_buttons()
        self._update_tag_editor()
    
    def _update_dataset_treeview(self):
        """Update the dataset treeview with current datasets in manager order."""
        # Clear existing items
        for item in self.dataset_list_panel.treeview.get_children():
            self.dataset_list_panel.treeview.delete(item)
        
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
            item_id = self.dataset_list_panel.treeview.insert(
                '', 'end',
                text='•',
                values=(dataset['tag'], filename_display),
                tags=('dataset',)
            )
            
            # Select and show active dataset
            if dataset['id'] == active_id:
                self.dataset_list_panel.treeview.selection_set(item_id)
                self.dataset_list_panel.treeview.see(item_id)
        
        # Configure tag styling
        self.dataset_list_panel.treeview.tag_configure('dataset', foreground='black')

    def _update_navigation_buttons(self):
        """Update the state of navigation and action buttons."""
        has_datasets = self.dataset_manager.has_datasets()
        
        # Mode-aware navigation button updates
        self._update_navigation_buttons_for_mode()
        
        # Action buttons
        self.dataset_mgmt_panel.edit_notes_btn.config(state='normal' if has_datasets else 'disabled')
        self.dataset_mgmt_panel.reset_config_btn.config(state='normal' if has_datasets else 'disabled')
        self.dataset_mgmt_panel.remove_dataset_btn.config(state='normal' if has_datasets else 'disabled')
        self.dataset_mgmt_panel.clear_all_btn.config(state='normal' if has_datasets else 'disabled')

    def _on_dataset_select(self, event=None):
        """Handle dataset selection from treeview."""
        selection = self.dataset_list_panel.treeview.selection()
        if selection:
            # Get the selected item
            selected_item = selection[0]
            
            # Get all datasets and find the matching one by index
            datasets = self.dataset_manager.get_all_datasets_ordered()
            
            # Get the index of the selected item in the treeview
            all_items = self.dataset_list_panel.treeview.get_children()
            try:
                selected_index = all_items.index(selected_item)
                
                if selected_index < len(datasets):
                    selected_dataset = datasets[selected_index]
                    self.dataset_manager.set_active_dataset(selected_dataset['id'])
                    
                    self._load_active_dataset_settings()
                    self._update_tag_editor()  # Update tag editor when selection changes
                    self._update_column_combos()
                    self._update_stats_display()
                    
                    # Update plot if canvas exists and we have data
                    if hasattr(self, 'canvas') and self.dataset_manager.get_active_dataset():
                        self._update_plot()
            
            except (ValueError, IndexError) as e:
                logger.error(f"Error handling dataset selection: {e}")

    def _handle_dataset_reorder(self, drag_item, target_item, drop_y):
        """Handle dataset reorder request from DatasetListPanel.
        
        This bridges between the panel's drag-and-drop UI and the existing
        dataset reordering logic.
        """
        self._reorder_datasets(drag_item, target_item, drop_y)
    
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
            logger.warning("edit_dataset_notes called with no active dataset")
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
    
    def reset_to_config_defaults(self):
        """Reset the active dataset to configuration defaults."""
        active_dataset = self.dataset_manager.get_active_dataset()
        if not active_dataset:
            logger.warning("reset_to_config_defaults called with no active dataset")
            return
        
        # Check if config is loaded
        if not self.dataset_manager.config_manager.is_loaded():
            messagebox.showwarning(
                "Config Not Available",
                f"Configuration file could not be loaded:\n{self.dataset_manager.config_manager.load_error}\n\n"
                f"Using programmatic defaults only."
            )
            return
        
        # Confirm with user
        result = messagebox.askyesno(
            "Reset to Config Defaults",
            f"Reset settings for '{active_dataset['tag']}' to configuration defaults?\n\n"
            f"This will reset:\n"
            f"  • Bin count\n"
            f"  • Column selections\n"
            f"  • Other analysis parameters\n\n"
            f"Current plot settings will be overwritten."
        )
        
        if result:
            # Re-apply config defaults
            instrument_type = active_dataset['instrument_type']
            data_processor = active_dataset['data_processor']
            
            instrument_config = self.dataset_manager.config_manager.get_instrument_config(instrument_type)
            
            # Reset to defaults
            bin_count = DEFAULT_BIN_COUNT
            size_column = data_processor.size_column
            
            if instrument_config:
                calibration = instrument_config.get('calibration', {})
                if 'bins' in calibration:
                    bin_count = calibration['bins']
                
                variants = instrument_config.get('variants', [])
                if variants and 'pbpKey' in variants[0]:
                    config_size_column = variants[0]['pbpKey']
                    if config_size_column in data_processor.get_columns():
                        size_column = config_size_column
            
            # Update the settings
            active_dataset['analysis_settings']['bin_count'] = bin_count
            active_dataset['analysis_settings']['size_column'] = size_column
            
            # Reload UI
            self._load_active_dataset_settings()
            self._update_column_combos()
            self._update_stats_display()
            
            # Update plot if exists
            if hasattr(self, 'canvas'):
                self._update_plot()
            
            messagebox.showinfo(
                "Reset Complete",
                f"Settings for '{active_dataset['tag']}' have been reset to configuration defaults."
            )

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
            logger.warning("remove_dataset called with no active dataset")
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
    
    def clear_all_datasets(self):
        """Clear all loaded datasets."""
        if not self.dataset_manager.has_datasets():
            return
        
        dataset_count = self.dataset_manager.get_dataset_count()
        dataset_names = [dataset['tag'] for dataset in self.dataset_manager.get_all_datasets_ordered()]
        
        if dataset_count == 1:
            message = f"This will remove the currently loaded dataset:\n• {dataset_names[0]}\n\nContinue?"
        else:
            dataset_list = '\n'.join([f"• {name}" for name in dataset_names[:5]])
            if dataset_count > 5:
                dataset_list += f"\n• ... and {dataset_count - 5} more"
            message = f"This will remove all {dataset_count} loaded datasets:\n\n{dataset_list}\n\nContinue?"
        
        result = messagebox.askyesno(
            "Clear All Datasets",
            message,
            icon='warning'
        )
        
        if result:
            self.dataset_manager.clear_all_datasets()
            self._clear_ui_for_no_datasets()
            self.scrollable_frame.update_scroll_region()
            logger.info(f"Cleared all {dataset_count} datasets")

    def _clear_ui_for_no_datasets(self):
        """Clear UI elements when no datasets are available."""
        # Clear column combos
        self.analysis_controls_panel.size_combo['values'] = []
        self.size_column_var.set('')
        
        # Clear stats
        self.stats_panel.set_stats("No datasets loaded")
        
        # Clear tag editor
        self._update_tag_editor()
        
        # Clear treeview
        for item in self.dataset_list_panel.treeview.get_children():
            self.dataset_list_panel.treeview.delete(item)
        
        self._update_report_button_state()
        self._update_navigation_buttons_for_mode()  # Update navigation buttons including save graph
        
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
                                              text="No plot to display\nLoad data to begin",
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
        self.show_gaussian_fit_var.set(settings.get('show_gaussian_fit', True))

        # Update data processor mode
        data_processor = active_dataset['data_processor']
        data_processor.set_data_mode(settings['data_mode'])
    
    def _save_active_dataset_settings(self):
        """Save current UI settings to the active dataset."""
        active_dataset = self.dataset_manager.get_active_dataset()
        if not active_dataset:
            return
        
        settings = {
            'data_mode': self.data_mode_var.get(),
            'bin_count': self.bin_count_var.get(),
            'size_column': self.size_column_var.get(),
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
                self.size_column_var.get()
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
    
    def _update_column_combos(self):
        """Update the column selection comboboxes."""
        active_dataset = self.dataset_manager.get_active_dataset()
        if not active_dataset:
            self.analysis_controls_panel.size_combo['values'] = []
            return
        
        columns = active_dataset['data_processor'].get_columns()
        
        self.analysis_controls_panel.size_combo['values'] = columns
        
        # Set default selections if auto-detected
        data_processor = active_dataset['data_processor']
        if data_processor.size_column:
            self.size_column_var.set(data_processor.size_column)
    
    def _update_stats_display(self):
        """Update the statistics display."""
        active_dataset = self.dataset_manager.get_active_dataset()
        if not active_dataset:
            self.stats_panel.set_stats("No active dataset")
            return
        
        stats = active_dataset['data_processor'].get_data_stats()
        instrument_info = stats.get('instrument_info', {})
        
        # Dataset info
        stats_str = f"Dataset: {active_dataset['tag']}\n"
        stats_str += f"File: {active_dataset['filename']}\n"
        stats_str += f"Instrument: {instrument_info.get('name', 'Unknown')}\n"
        stats_str += f"Rows: {stats.get('total_rows', 'N/A')}\n"
        stats_str += f"Columns: {stats.get('total_columns', 'N/A')}\n"
        stats_str += f"Mode: {stats.get('data_mode', 'N/A')}\n"
        
        # Firmware and software versions
        firmware_version = instrument_info.get('version', 'N/A')
        pads_version = instrument_info.get('pads_version', 'N/A')
        stats_str += f"\nFirmware Version: {firmware_version}\n"
        stats_str += f"PADS Version: {pads_version}\n"
        stats_str += f"Time Duration: N/A\n"
        
        # Size statistics
        if 'size_min' in stats:
            stats_str += f"\nSize Range:\n"
            stats_str += f"  Min: {stats['size_min']:.3f}\n"
            stats_str += f"  Max: {stats['size_max']:.3f}\n"
            stats_str += f"  Mean: {stats['size_mean']:.3f}\n"

        # Add notes section if they exist
        if active_dataset['notes']:
            stats_str += f"\n--- Notes ---\n"
            stats_str += f"{active_dataset['notes']}"
        
        self.stats_panel.set_stats(stats_str)
    
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
                self.size_column_var.get()
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
            self._update_navigation_buttons_for_mode()  # Update navigation buttons including save graph
            
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
                self._update_report_button_state()
                self._update_navigation_buttons_for_mode()  # Update navigation buttons including save graph
    
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
        
        # Generate default filename with instrument type, serial number, and timestamp
        instrument_type = active_dataset['data_processor'].get_instrument_type()
        serial_number = self.dataset_manager.instrument_serial_number or "UNKNOWN"
        timestamp = datetime.now().strftime("%Y%m%d_%H%M")
        default_filename = f"{instrument_type}_{serial_number}_verification_{timestamp}.pdf"

        # Get save location from user
        file_path = filedialog.asksaveasfilename(
            title="Save Report As",
            defaultextension=".pdf",
            initialfile=default_filename,
            filetypes=[("PDF files", "*.pdf"), ("All files", "*.*")]
        )
        
        if not file_path:
            return  # User cancelled
        
        try:
            # Generate plots for all datasets
            figures = []
            all_datasets = self.dataset_manager.get_all_datasets_ordered() #Use _ordered to maintain user order
            
            for dataset in all_datasets:
                figure = self._generate_plot_for_dataset(dataset)
                if figure:
                    figures.append(figure)
            
            if not figures:
                messagebox.showerror("Error", "Failed to generate any plots for the report.")
                return
            
            # Generate the multi-plot report
            success = self.report_template.create_report(
                output_path=file_path,
                plot_figures=figures, 
                instrument_serial_number=self.dataset_manager.instrument_serial_number
            )
            
            # Clean up generated figures
            for fig in figures:
                plt.close(fig)
            
            if success:
                messagebox.showinfo("Success", f"Report generated successfully!\nSaved to: {file_path}")
            else:
                messagebox.showerror("Error", "Failed to generate report. Check console for details.")
                
        except Exception as e:
            messagebox.showerror("Error", f"Failed to generate report: {str(e)}")
    
    def _get_current_timestamp(self):
        """Get current timestamp for report."""
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    
    def _generate_plot_for_dataset(self, dataset: Dict[str, Any]) -> Optional[matplotlib.figure.Figure]:
        """Generate a plot for a specific dataset with metadata."""
        try:
            data_processor = dataset['data_processor']
            settings = dataset['analysis_settings']
            
            # Get data
            size_data = data_processor.get_size_data()
            frequency_data = data_processor.get_frequency_data()
            
            if size_data is None:
                logger.warning(f"No size data for dataset {dataset['tag']}")
                return None
            
            # Build metadata
            metadata = {
                'bead_size': dataset['tag'],
                'serial_number': self.dataset_manager.instrument_serial_number,
                'filename': dataset['filename'],
                'timestamp': dataset['loaded_at'].strftime("%Y-%m-%d %H:%M:%S"),
                # Material and lot_number will come from config later
            }
            
            # Create plot title
            plot_title = f"Particle Size Distribution - {dataset['tag']} μm"
            
            # Generate the figure
            figure = self.plotter.create_histogram(
                size_data=size_data,
                frequency_data=frequency_data,
                bin_count=settings['bin_count'],
                title=plot_title,
                show_stats_lines=settings.get('show_stats_lines', False),
                data_mode=settings['data_mode'],
                show_gaussian_fit=settings.get('show_gaussian_fit', True),
                metadata=metadata
            )
            
            return figure
            
        except Exception as e:
            logger.error(f"Error generating plot for dataset {dataset.get('tag', 'unknown')}: {e}")
            return None

    def _update_report_button_state(self):
        """Update the report button state based on available data, plot, and mode."""
        self._update_report_button_state_for_mode()
        if hasattr(self, 'gaussian_info_btn'):
            # Enable Gaussian info button if we have a plot with Gaussian fit
            has_gaussian_fit = (hasattr(self, 'canvas') and 
                            hasattr(self.plotter, 'get_last_gaussian_fit') and
                            self.plotter.get_last_gaussian_fit() is not None)
            self.analysis_controls_panel.gaussian_info_btn.config(state='normal' if has_gaussian_fit else 'disabled')

    def _reorder_datasets(self, drag_item, target_item, drop_y):
        """Reorder datasets in both treeview and dataset manager."""
        try:
            # Get the dataset IDs from the treeview items BY LOOKING UP THE ACTUAL DATA
            all_items = list(self.dataset_list_panel.treeview.get_children())
            
            # Create a mapping from treeview items to dataset IDs
            item_to_dataset_id = {}
            all_datasets = self.dataset_manager.get_all_datasets_ordered()
            
            for i, item in enumerate(all_items):
                values = self.dataset_list_panel.treeview.item(item, 'values')
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
                target_bbox = self.dataset_list_panel.treeview.bbox(target_item)
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
            updated_items = list(self.dataset_list_panel.treeview.get_children())
            for item in updated_items:
                values = self.dataset_list_panel.treeview.item(item, 'values')
                if values:
                    tag, filename = values
                    if tag == drag_dataset['tag'] and filename == drag_dataset['filename']:
                        self.dataset_list_panel.treeview.selection_set(item)
                        self.dataset_list_panel.treeview.see(item)
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
        datasets = self.dataset_manager.get_all_datasets_ordered()
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
            sys.exit(0)