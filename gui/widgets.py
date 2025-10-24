"""
Custom tkinter widgets and container helpers.
"""

import tkinter as tk
from tkinter import ttk
from typing import Optional, Callable


class VBox(ttk.Frame):
    """Vertical box container - stacks children top-to-bottom using pack."""
    
    def __init__(self, parent, padding=0, **kwargs):
        super().__init__(parent, padding=padding, **kwargs)
    
    def add(self, widget, **pack_options):
        """Add a widget to the VBox with default top packing."""
        default_options = {'side': 'top', 'fill': 'x', 'pady': 2}
        default_options.update(pack_options)
        widget.pack(**default_options)
        return widget


class HBox(ttk.Frame):
    """Horizontal box container - arranges children left-to-right using pack."""
    
    def __init__(self, parent, padding=0, **kwargs):
        super().__init__(parent, padding=padding, **kwargs)
    
    def add(self, widget, **pack_options):
        """Add a widget to the HBox with default left packing."""
        default_options = {'side': 'left', 'padx': 2}
        default_options.update(pack_options)
        widget.pack(**default_options)
        return widget


class LabeledRow(ttk.Frame):
    """A row with a fixed-width label and a widget, for consistent alignment."""
    
    def __init__(self, parent, label_text, label_width=20, **kwargs):
        super().__init__(parent, **kwargs)
        
        self.label = ttk.Label(self, text=label_text, width=label_width)
        self.label.pack(side='left', anchor='w')
        
        # Container for the widget (so it can expand)
        self.widget_container = ttk.Frame(self)
        self.widget_container.pack(side='left', fill='x', expand=True, padx=(5, 0))
    
    def add_widget(self, widget_class, **widget_kwargs):
        """Create and add a widget to the row."""
        widget = widget_class(self.widget_container, **widget_kwargs)
        widget.pack(fill='x', expand=True)
        return widget


class AnalysisModePanel(ttk.LabelFrame):
    """Panel for analysis mode selection with load buttons and serial number input."""
    
    def __init__(self, parent, 
                 on_load_calibration: Callable,
                 on_load_verification: Callable,
                 serial_var: tk.StringVar,
                 **kwargs):
        super().__init__(parent, text="Analysis Mode", padding=5, **kwargs)
        
        # Store callbacks
        self.on_load_calibration = on_load_calibration
        self.on_load_verification = on_load_verification
        
        # Buttons container
        buttons_container = ttk.Frame(self)
        buttons_container.pack(fill='x', pady=(0, 5))
        
        self.calibration_button = ttk.Button(
            buttons_container,
            text="Load for Calibration",
            command=on_load_calibration
        )
        self.calibration_button.pack(side='left', padx=(0, 10), fill='x', expand=True)
        
        self.verification_button = ttk.Button(
            buttons_container,
            text="Load for Verification",
            command=on_load_verification
        )
        self.verification_button.pack(side='left', fill='x', expand=True)
        
        # Mode description label
        self.mode_description = ttk.Label(
            self,
            text="Current Mode: Calibration",
            font=('TkDefaultFont', 8),
            foreground='blue'
        )
        self.mode_description.pack(anchor='w', pady=(5, 0))
        
        # Serial number input
        serial_frame = ttk.Frame(self)
        serial_frame.pack(fill='x', pady=(10, 0))
        
        ttk.Label(serial_frame, text="Instrument Serial Number:").pack(side='left', padx=(0, 5))
        
        self.serial_entry = ttk.Entry(serial_frame, textvariable=serial_var, width=20)
        self.serial_entry.pack(side='left')


class QueueStatusPanel(ttk.Frame):
    """Panel for displaying queue status messages."""
    
    def __init__(self, parent, font_style, **kwargs):
        super().__init__(parent, **kwargs)
        
        self.status_label = ttk.Label(self, text="", font=font_style)
        self.status_label.pack(anchor='w', fill='x')
    
    def set_status(self, text, foreground='black'):
        """Update the status message."""
        self.status_label.config(text=text, foreground=foreground)


class DatasetManagementPanel(ttk.LabelFrame):
    """Panel with dataset management action buttons."""
    
    def __init__(self, parent,
                 on_reset_config: Callable,
                 on_edit_notes: Callable,
                 on_remove: Callable,
                 on_help: Callable,
                 **kwargs):
        super().__init__(parent, text="Dataset Management", padding=5, **kwargs)
        
        actions_frame = ttk.Frame(self)
        actions_frame.pack(fill='x', pady=5)
        
        self.reset_config_btn = ttk.Button(
            actions_frame,
            text="Reset to Config Defaults",
            command=on_reset_config,
            state='disabled'
        )
        self.reset_config_btn.pack(side='left', padx=(0, 5))
        
        self.edit_notes_btn = ttk.Button(
            actions_frame,
            text="Edit Notes",
            command=on_edit_notes,
            state='disabled'
        )
        self.edit_notes_btn.pack(side='left', padx=(0, 5))
        
        self.remove_dataset_btn = ttk.Button(
            actions_frame,
            text="Remove",
            command=on_remove,
            state='disabled'
        )
        self.remove_dataset_btn.pack(side='left', padx=(0, 5))
        
        self.help_btn = ttk.Button(
            actions_frame,
            text="?",
            width=3,
            command=on_help
        )
        self.help_btn.pack(side='right')


class AnalysisControlsPanel(ttk.Frame):
    """Panel containing column selection, bin count, and gaussian fit controls."""
    
    def __init__(self, parent,
                 size_column_var: tk.StringVar,
                 frequency_column_var: tk.StringVar,
                 bin_count_var: tk.IntVar,
                 on_column_change: Callable,
                 on_bin_change: Callable,
                 on_gaussian_info: Callable,
                 min_bins: int,
                 max_bins: int,
                 **kwargs):
        super().__init__(parent, **kwargs)
        
        # Separator before analysis controls
        ttk.Separator(self, orient='horizontal').pack(fill='x', pady=5)
        
        # Size column selection
        size_row = LabeledRow(self, "Size Column:", label_width=15)
        size_row.pack(fill='x', pady=2)
        self.size_combo = size_row.add_widget(
            ttk.Combobox,
            textvariable=size_column_var,
            state='readonly'
        )
        self.size_combo.bind('<<ComboboxSelected>>', on_column_change)
        
        # Frequency column selection #TODO: Remove
        freq_row = LabeledRow(self, "Frequency Column:", label_width=15)
        freq_row.pack(fill='x', pady=2)
        self.frequency_combo = freq_row.add_widget(
            ttk.Combobox,
            textvariable=frequency_column_var,
            state='readonly'
        )
        self.frequency_combo.bind('<<ComboboxSelected>>', on_column_change)
        
        # Bin count
        bin_row = LabeledRow(self, "Bins:", label_width=15)
        bin_row.pack(fill='x', pady=2)
        
        bin_controls = ttk.Frame(bin_row.widget_container)
        bin_controls.pack(fill='x', expand=True)
        
        self.bin_entry = ttk.Entry(bin_controls, textvariable=bin_count_var, width=8)
        self.bin_entry.pack(side='left')
        self.bin_entry.bind('<Return>', on_bin_change)
        self.bin_entry.bind('<FocusOut>', on_bin_change)
        
        bin_hint = ttk.Label(
            bin_controls,
            text=f"({min_bins}-{max_bins})",
            font=('TkDefaultFont', 8),
            foreground='gray'
        )
        bin_hint.pack(side='left', padx=(5, 0))
        
        self.gaussian_info_btn = ttk.Button(
            bin_controls,
            text="📊 Fit Info",
            command=on_gaussian_info,
            state='disabled',
            width=10
        )
        self.gaussian_info_btn.pack(side='right', padx=(10, 0))


class ActionButtonsPanel(ttk.Frame):
    """Panel containing plot and report action buttons."""
    
    def __init__(self, parent,
                 on_plot: Callable,
                 on_report: Callable,
                 reports_available: bool,
                 **kwargs):
        super().__init__(parent, **kwargs)
        
        self.plot_button = ttk.Button(
            self,
            text="Create Plot",
            command=on_plot,
            state='disabled'
        )
        self.plot_button.pack(fill='x', pady=(10, 5))
        
        self.report_button = ttk.Button(
            self,
            text="Generate Report" if reports_available else "Generate Report (ReportLab not installed)",
            command=on_report,
            state='disabled'
        )
        self.report_button.pack(fill='x', pady=5)