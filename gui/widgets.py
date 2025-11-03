"""
Custom tkinter widgets and container helpers for clean layout management.
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

class DatasetListPanel(ttk.LabelFrame):
    """
    Panel containing dataset treeview, tag editor, and inline management.
    
    Handles drag-and-drop reordering internally, but delegates actual
    dataset operations to callbacks.
    """
    
    def __init__(self, parent,
                 current_tag_var: tk.StringVar,
                 on_dataset_select: Callable,
                 on_tag_save: Callable,
                 on_dataset_reorder: Callable,
                 validate_float_func,
                 treeview_height=8,
                 **kwargs):
        super().__init__(parent, text="Loaded Datasets", padding=5, **kwargs)
        
        # Store callbacks
        self.on_dataset_select = on_dataset_select
        self.on_tag_save = on_tag_save
        self.on_dataset_reorder = on_dataset_reorder
        self.current_tag_var = current_tag_var
        
        # Drag-and-drop state
        self.drag_item = None
        self.drag_start_y = None
        
        # === TREEVIEW WITH SCROLLBARS ===
        list_container = ttk.Frame(self)
        list_container.pack(fill='x', pady=(0, 5))
        
        # Create treeview
        self.treeview = ttk.Treeview(
            list_container,
            columns=('tag', 'filename'),
            show='tree headings',
            height=treeview_height,
            selectmode='browse'
        )
        
        # Configure columns
        self.treeview.heading('#0', text='')
        self.treeview.heading('tag', text='Bead Size (μm)')
        self.treeview.heading('filename', text='Filename')
        
        self.treeview.column('#0', width=15, minwidth=15, stretch=False)
        self.treeview.column('tag', width=80, minwidth=60, stretch=True)
        self.treeview.column('filename', width=120, minwidth=80, stretch=True)
        
        # Scrollbars (using grid - only exception)
        scrollbar_y = ttk.Scrollbar(list_container, orient='vertical', command=self.treeview.yview)
        scrollbar_x = ttk.Scrollbar(list_container, orient='horizontal', command=self.treeview.xview)
        
        self.treeview.configure(yscrollcommand=scrollbar_y.set, xscrollcommand=scrollbar_x.set)
        
        # Grid layout for treeview and scrollbars
        self.treeview.grid(row=0, column=0, sticky='nsew')
        scrollbar_y.grid(row=0, column=1, sticky='ns')
        scrollbar_x.grid(row=1, column=0, sticky='ew')
        
        list_container.grid_rowconfigure(0, weight=1)
        list_container.grid_columnconfigure(0, weight=1)
        
        # Bind events
        self.treeview.bind('<ButtonPress-1>', self._on_button_press)
        self.treeview.bind('<B1-Motion>', self._on_drag_motion)
        self.treeview.bind('<ButtonRelease-1>', self._on_button_release)
        self.treeview.bind('<<TreeviewSelect>>', lambda e: self.on_dataset_select())
        
        # === TAG EDITOR ===
        tag_editor_frame = ttk.LabelFrame(self, text="Bead Size (μm)", padding=5)
        tag_editor_frame.pack(fill='x', pady=(0, 5))
        
        ttk.Label(tag_editor_frame, text="Bead Size (μm):").pack(side='left', padx=(0, 5))
        
        self.tag_entry = ttk.Entry(
            tag_editor_frame,
            textvariable=current_tag_var,
            state='disabled',
            validate='key',
            validatecommand=(validate_float_func, '%P')
        )
        self.tag_entry.pack(side='left', fill='x', expand=True, padx=(0, 5))
        
        self.tag_save_btn = ttk.Button(
            tag_editor_frame,
            text="💾",
            width=3,
            command=on_tag_save,
            state='disabled'
        )
        self.tag_save_btn.pack(side='right')
    
    # === DRAG-AND-DROP METHODS ===
    
    def _on_button_press(self, event):
        """Handle mouse button press for drag start."""
        item = self.treeview.identify_row(event.y)
        if item:
            self.drag_item = item
            self.drag_start_y = event.y
    
    def _on_drag_motion(self, event):
        """Handle drag motion for visual feedback."""
        if self.drag_item:
            target_item = self.treeview.identify_row(event.y)
            if target_item and target_item != self.drag_item:
                # Change cursor to indicate valid drop target
                self.treeview.configure(cursor="hand2")
            else:
                # Reset cursor when not over valid target
                self.treeview.configure(cursor="")
    
    def _on_button_release(self, event):
        """Handle mouse button release to complete drag-and-drop."""
        # Always reset cursor first
        self.treeview.configure(cursor="")
        
        if self.drag_item:
            target_item = self.treeview.identify_row(event.y)
            
            if target_item and target_item != self.drag_item:
                # Delegate the actual reordering to the callback
                self.on_dataset_reorder(self.drag_item, target_item, event.y)
            
            # Clean up drag state
            self.drag_item = None
            self.drag_start_y = None
    
    # === PUBLIC INTERFACE ===
    
    def get_selected_item(self):
        """Get the currently selected treeview item."""
        selection = self.treeview.selection()
        return selection[0] if selection else None
    
    def clear_selection(self):
        """Clear treeview selection."""
        self.treeview.selection_remove(self.treeview.selection())


class DatasetManagementPanel(ttk.LabelFrame):
    """Panel with dataset management action buttons."""
    
    def __init__(self, parent,
                 on_reset_config: Callable,
                 on_edit_notes: Callable,
                 on_remove: Callable,
                 on_clear_all: Callable,
                 on_help: Callable,
                 **kwargs):
        super().__init__(parent, text="Dataset Management", padding=5, **kwargs)
        
        # Row 1: Configuration and editing actions
        row1_frame = ttk.Frame(self)
        row1_frame.pack(fill='x', pady=(0, 5))
        
        self.reset_config_btn = ttk.Button(
            row1_frame,
            text="Reset to Config Defaults",
            command=on_reset_config,
            state='disabled'
        )
        self.reset_config_btn.pack(side='left', padx=(0, 5))
        
        self.edit_notes_btn = ttk.Button(
            row1_frame,
            text="Edit Notes",
            command=on_edit_notes,
            state='disabled'
        )
        self.edit_notes_btn.pack(side='left', padx=(0, 5))
        
        # Row 2: Destructive actions and help
        row2_frame = ttk.Frame(self)
        row2_frame.pack(fill='x')
        
        self.remove_dataset_btn = ttk.Button(
            row2_frame,
            text="Remove",
            command=on_remove,
            state='disabled'
        )
        self.remove_dataset_btn.pack(side='left', padx=(0, 5))
        
        self.clear_all_btn = ttk.Button(
            row2_frame,
            text="Clear All",
            command=on_clear_all,
            state='disabled'
        )
        self.clear_all_btn.pack(side='left', padx=(0, 5))
        
        self.help_btn = ttk.Button(
            row2_frame,
            text="?",
            width=3,
            command=on_help
        )
        self.help_btn.pack(side='right')


class StatsPanel(ttk.LabelFrame):
    """Panel for displaying dataset statistics."""
    
    def __init__(self, parent, text_height=8, text_width=30, **kwargs):
        super().__init__(parent, text="Data Info", padding=5, **kwargs)
        
        self.stats_text = tk.Text(self, height=text_height, width=text_width)
        self.stats_text.pack(fill='both', expand=True)
    
    def set_stats(self, stats_text: str):
        """Update the statistics display."""
        self.stats_text.delete('1.0', tk.END)
        self.stats_text.insert('1.0', stats_text)
    
    def clear(self):
        """Clear the statistics display."""
        self.stats_text.delete('1.0', tk.END)


class AnalysisControlsPanel(ttk.Frame):
    """Panel containing column selection, bin count, and gaussian fit controls."""
    
    def __init__(self, parent,
                 size_column_var: tk.StringVar,
                 bin_count_var: tk.IntVar,
                 on_column_change: Callable,
                 on_bin_change: Callable,
                 on_gaussian_info: Callable,
                 min_bins: int,
                 max_bins: int,
                 **kwargs):
        super().__init__(parent, **kwargs)
        
        # Size column selection
        size_row = LabeledRow(self, "Size Column:", label_width=15)
        size_row.pack(fill='x', pady=2)
        self.size_combo = size_row.add_widget(
            ttk.Combobox,
            textvariable=size_column_var,
            state='readonly'
        )
        self.size_combo.bind('<<ComboboxSelected>>', on_column_change)
        
        # Bin count
        bin_row = LabeledRow(self, "Bins:", label_width=15)
        bin_row.pack(fill='x', pady=2)

        self.bin_entry = ttk.Entry(bin_row, textvariable=bin_count_var, width=8)
        self.bin_entry.pack(side='left')
        self.bin_entry.bind('<Return>', on_bin_change)
        self.bin_entry.bind('<FocusOut>', on_bin_change)
        
        bin_hint = ttk.Label(
            bin_row,
            text=f"({min_bins}-{max_bins})",
            font=('TkDefaultFont', 8),
            foreground='gray'
        )
        bin_hint.pack(side='left', padx=(5, 0))
        
        self.gaussian_info_btn = ttk.Button(
            bin_row,
            text="📊 Fit Info",
            command=on_gaussian_info,
            state='disabled',
            width=10
        )
        self.gaussian_info_btn.pack(side='right', padx=(10, 0))


class ActionButtonsPanel(ttk.Frame):
    """Panel containing report action button."""
    
    def __init__(self, parent,
                 on_report: Callable,
                 reports_available: bool,
                 **kwargs):
        super().__init__(parent, **kwargs)
        
        self.report_button = ttk.Button(
            self,
            text="Generate Report" if reports_available else "Generate Report (ReportLab not installed)",
            command=on_report,
            state='disabled'
        )
        self.report_button.pack(fill='x', pady=5)

class PlotNavigationPanel(ttk.Frame):
    """Panel containing plot navigation and save controls."""
    
    def __init__(self, parent,
                 on_previous: Callable,
                 on_next: Callable,
                 on_save: Callable,
                 **kwargs):
        super().__init__(parent, **kwargs)
        
        self.prev_btn = ttk.Button(
            self,
            text="◀ Previous Dataset",
            command=on_previous,
            state='disabled'
        )
        self.prev_btn.pack(side='left')
        
        self.save_btn = ttk.Button(
            self,
            text="💾 Save Graph",
            command=on_save,
            state='disabled'
        )
        self.save_btn.pack(side='left', expand=True)
        
        self.next_btn = ttk.Button(
            self,
            text="Next Dataset ▶",
            command=on_next,
            state='disabled'
        )
        self.next_btn.pack(side='right')