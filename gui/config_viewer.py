# gui/config_viewer.py
"""
Configuration viewer dialog for displaying and managing JSON configuration files.
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import json
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

class ConfigurationViewerDialog:
    """Dialog for viewing and managing configuration files."""
    
    def __init__(self, parent, config_manager):
        self.parent = parent
        self.config_manager = config_manager
        self.dialog = None
        self.tree = None
        self.config_data = None
        
    def show_dialog(self):
        """Show the configuration viewer dialog."""
        if self.dialog:
            self.dialog.lift()
            return
        
        self.dialog = tk.Toplevel(self.parent)
        self.dialog.title("Configuration Manager")
        self.dialog.geometry("800x600")
        self.dialog.grab_set()  # Make modal
        
        # Handle dialog close
        self.dialog.protocol("WM_DELETE_WINDOW", self._on_dialog_close)
        
        self._create_widgets()
        self._create_layout()
        self._update_display()
    
    def _create_widgets(self):
        """Create all dialog widgets."""
        # Main frame
        self.main_frame = ttk.Frame(self.dialog)
        
        # Toolbar frame
        self.toolbar_frame = ttk.Frame(self.main_frame)
        
        # Load configuration button
        self.load_button = ttk.Button(
            self.toolbar_frame, 
            text="📁 Load Config", 
            command=self._load_config_file
        )
        
        # Preview button
        self.preview_button = ttk.Button(
            self.toolbar_frame, 
            text="👁️ Preview File", 
            command=self._preview_config_file
        )
        
        # Create sample button
        self.create_sample_button = ttk.Button(
            self.toolbar_frame, 
            text="📄 Create Sample", 
            command=self._create_sample_config
        )
        
        # Export current button
        self.export_button = ttk.Button(
            self.toolbar_frame, 
            text="💾 Export Current", 
            command=self._export_current_settings,
            state='disabled'  # Enable this when main app integration is complete
        )
        
        # Separator
        ttk.Separator(self.toolbar_frame, orient='vertical').pack(side='left', fill='y', padx=10)
        
        # Reload button
        self.reload_button = ttk.Button(
            self.toolbar_frame, 
            text="🔄 Reload", 
            command=self._reload_config,
            state='disabled'
        )
        
        # Clear button
        self.clear_button = ttk.Button(
            self.toolbar_frame, 
            text="🗑️ Clear", 
            command=self._clear_config
        )
        
        # Info frame
        self.info_frame = ttk.LabelFrame(self.main_frame, text="Configuration Information", padding=5)
        
        # Config info display
        self.info_text = tk.Text(self.info_frame, height=4, wrap='word', state='disabled')
        self.info_scrollbar = ttk.Scrollbar(self.info_frame, orient='vertical', command=self.info_text.yview)
        self.info_text.configure(yscrollcommand=self.info_scrollbar.set)
        
        # Tree view frame
        self.tree_frame = ttk.LabelFrame(self.main_frame, text="Configuration Contents", padding=5)
        
        # Create treeview with scrollbars
        self.tree = ttk.Treeview(self.tree_frame, columns=('value', 'type'), show='tree headings')
        
        # Configure columns
        self.tree.heading('#0', text='Setting')
        self.tree.heading('value', text='Value')
        self.tree.heading('type', text='Type')
        
        self.tree.column('#0', width=300, minwidth=200)
        self.tree.column('value', width=300, minwidth=150)
        self.tree.column('type', width=100, minwidth=80)
        
        # Scrollbars for tree
        self.tree_scrollbar_y = ttk.Scrollbar(self.tree_frame, orient='vertical', command=self.tree.yview)
        self.tree_scrollbar_x = ttk.Scrollbar(self.tree_frame, orient='horizontal', command=self.tree.xview)
        self.tree.configure(yscrollcommand=self.tree_scrollbar_y.set, xscrollcommand=self.tree_scrollbar_x.set)
        
        # Detail frame for selected item
        self.detail_frame = ttk.LabelFrame(self.main_frame, text="Selected Item Details", padding=5)
        
        self.detail_text = tk.Text(self.detail_frame, height=6, wrap='word', state='disabled')
        self.detail_scrollbar = ttk.Scrollbar(self.detail_frame, orient='vertical', command=self.detail_text.yview)
        self.detail_text.configure(yscrollcommand=self.detail_scrollbar.set)
        
        # Bind tree selection
        self.tree.bind('<<TreeviewSelect>>', self._on_tree_select)
        
        # Button frame
        self.button_frame = ttk.Frame(self.main_frame)
        
        # Close button
        self.close_button = ttk.Button(
            self.button_frame, 
            text="Close", 
            command=self._on_dialog_close
        )
    
    def _create_layout(self):
        """Layout all widgets in the dialog."""
        self.main_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Toolbar
        self.toolbar_frame.pack(fill='x', pady=(0, 10))
        self.load_button.pack(side='left', padx=(0, 5))
        self.preview_button.pack(side='left', padx=(0, 5))
        self.create_sample_button.pack(side='left', padx=(0, 5))
        self.export_button.pack(side='left', padx=(0, 15))
        self.reload_button.pack(side='left', padx=(0, 5))
        self.clear_button.pack(side='left')
        
        # Info frame
        self.info_frame.pack(fill='x', pady=(0, 10))
        self.info_text.pack(side='left', fill='both', expand=True)
        self.info_scrollbar.pack(side='right', fill='y')
        
        # Tree frame
        self.tree_frame.pack(fill='both', expand=True, pady=(0, 10))
        self.tree.grid(row=0, column=0, sticky='nsew')
        self.tree_scrollbar_y.grid(row=0, column=1, sticky='ns')
        self.tree_scrollbar_x.grid(row=1, column=0, sticky='ew')
        
        self.tree_frame.grid_columnconfigure(0, weight=1)
        self.tree_frame.grid_rowconfigure(0, weight=1)
        
        # Detail frame
        self.detail_frame.pack(fill='x', pady=(0, 10))
        self.detail_text.pack(side='left', fill='both', expand=True)
        self.detail_scrollbar.pack(side='right', fill='y')
        
        # Button frame
        self.button_frame.pack(fill='x')
        self.close_button.pack(side='right')
    
    def _load_config_file(self):
        """Load a configuration file."""
        file_path = filedialog.askopenfilename(
            title="Select Configuration File",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            parent=self.dialog
        )
        
        if file_path:
            success = self.config_manager.load_config(file_path)
            
            if success:
                self._update_display()
                self.reload_button.config(state='normal')
                messagebox.showinfo(
                    "Success", 
                    f"Configuration loaded successfully from:\n{file_path}",
                    parent=self.dialog
                )
            else:
                messagebox.showerror(
                    "Error", 
                    f"Failed to load configuration file:\n{file_path}\n\nCheck the console for details.",
                    parent=self.dialog
                )
    
    def _preview_config_file(self):
        """Preview a configuration file without loading it."""
        file_path = filedialog.askopenfilename(
            title="Select Configuration File to Preview",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            parent=self.dialog
        )
        
        if file_path:
            preview_info = self.config_manager.preview_config(file_path)
            self._show_preview_dialog(preview_info)
    
    def _show_preview_dialog(self, preview_info: Dict[str, Any]):
        """Show configuration file preview in a separate dialog."""
        preview_dialog = tk.Toplevel(self.dialog)
        preview_dialog.title("Configuration Preview")
        preview_dialog.geometry("600x500")
        preview_dialog.grab_set()
        
        if not preview_info["success"]:
            # Show error
            ttk.Label(
                preview_dialog, 
                text=f"Error: {preview_info['error']}", 
                foreground='red'
            ).pack(padx=20, pady=20)
            
            ttk.Button(
                preview_dialog, 
                text="Close", 
                command=preview_dialog.destroy
            ).pack(pady=10)
            return
        
        # Create preview content
        main_frame = ttk.Frame(preview_dialog)
        main_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        # File info
        info_frame = ttk.LabelFrame(main_frame, text="File Information", padding=5)
        info_frame.pack(fill='x', pady=(0, 10))
        
        ttk.Label(info_frame, text=f"File: {preview_info['file_path']}").pack(anchor='w')
        ttk.Label(info_frame, text=f"Size: {preview_info['file_size']} bytes").pack(anchor='w')
        ttk.Label(info_frame, text=f"Sections: {preview_info['section_count']}").pack(anchor='w')
        
        # Metadata
        metadata = preview_info.get('metadata', {})
        if metadata:
            meta_frame = ttk.LabelFrame(main_frame, text="Metadata", padding=5)
            meta_frame.pack(fill='x', pady=(0, 10))
            
            for key, value in metadata.items():
                ttk.Label(meta_frame, text=f"{key}: {value}").pack(anchor='w')
        
        # Sections and sample settings
        content_frame = ttk.LabelFrame(main_frame, text="Configuration Sections", padding=5)
        content_frame.pack(fill='both', expand=True, pady=(0, 10))
        
        content_text = tk.Text(content_frame, wrap='word')
        content_scrollbar = ttk.Scrollbar(content_frame, orient='vertical', command=content_text.yview)
        content_text.configure(yscrollcommand=content_scrollbar.set)
        
        content_text.pack(side='left', fill='both', expand=True)
        content_scrollbar.pack(side='right', fill='y')
        
        # Add content
        content_text.insert(tk.END, "Sections found:\n")
        for section in preview_info['sections']:
            content_text.insert(tk.END, f"  • {section}\n")
        
        content_text.insert(tk.END, "\nSample Settings:\n")
        for section, settings in preview_info.get('sample_settings', {}).items():
            content_text.insert(tk.END, f"\n[{section}]\n")
            for key, value in settings.items():
                content_text.insert(tk.END, f"  {key}: {value}\n")
        
        content_text.config(state='disabled')
        
        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x')
        
        def load_this_file():
            preview_dialog.destroy()
            success = self.config_manager.load_config(preview_info['file_path'])
            if success:
                self._update_display()
                self.reload_button.config(state='normal')
                messagebox.showinfo("Success", "Configuration loaded successfully!", parent=self.dialog)
        
        ttk.Button(button_frame, text="Load This Config", command=load_this_file).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text="Close", command=preview_dialog.destroy).pack(side='right')
    
    def _create_sample_config(self):
        """Create a sample configuration file."""
        file_path = filedialog.asksaveasfilename(
            title="Save Sample Configuration As",
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            parent=self.dialog
        )
        
        if file_path:
            success = self.config_manager.create_sample_config(file_path)
            
            if success:
                messagebox.showinfo(
                    "Success", 
                    f"Sample configuration created successfully:\n{file_path}",
                    parent=self.dialog
                )
                
                # Ask if user wants to load it
                if messagebox.askyesno(
                    "Load Sample?", 
                    "Would you like to load the sample configuration now?",
                    parent=self.dialog
                ):
                    self.config_manager.load_config(file_path)
                    self._update_display()
                    self.reload_button.config(state='normal')
            else:
                messagebox.showerror(
                    "Error", 
                    f"Failed to create sample configuration:\n{file_path}",
                    parent=self.dialog
                )
    
    def _export_current_settings(self):
        """Export current application settings as configuration."""
        # This will be implemented when integrated with main application
        messagebox.showinfo(
            "Not Implemented", 
            "Export current settings will be available when integrated with the main application.",
            parent=self.dialog
        )
    
    def _reload_config(self):
        """Reload the current configuration file."""
        if self.config_manager.config_file_path:
            success = self.config_manager.load_config(self.config_manager.config_file_path)
            if success:
                self._update_display()
                messagebox.showinfo("Success", "Configuration reloaded successfully!", parent=self.dialog)
            else:
                messagebox.showerror("Error", "Failed to reload configuration!", parent=self.dialog)
    
    def _clear_config(self):
        """Clear the current configuration."""
        if messagebox.askyesno(
            "Clear Configuration", 
            "Are you sure you want to clear the current configuration?",
            parent=self.dialog
        ):
            self.config_manager.config_data = {}
            self.config_manager.config_file_path = None
            self._update_display()
            self.reload_button.config(state='disabled')
    
    def _update_display(self):
        """Update the display with current configuration."""
        # Update info display
        self._update_info_display()
        
        # Update tree display
        self._update_tree_display()
        
        # Clear detail display
        self._update_detail_display()
    
    def _update_info_display(self):
        """Update the configuration information display."""
        self.info_text.config(state='normal')
        self.info_text.delete(1.0, tk.END)
        
        config_info = self.config_manager.get_config_info()
        
        if config_info["loaded"]:
            info_text = f"✅ Configuration Loaded\n"
            info_text += f"File: {config_info['file_path']}\n"
            
            metadata = config_info.get('metadata', {})
            if 'description' in metadata:
                info_text += f"Description: {metadata['description']}\n"
            if 'config_version' in metadata:
                info_text += f"Version: {metadata['config_version']}\n"
            
            info_text += f"Sections: {len(config_info['sections'])}, Settings: {config_info['total_settings']}"
        else:
            info_text = "ℹ️ No Configuration Loaded\nUse 'Load Config' to load a configuration file or 'Create Sample' to generate a template."
        
        self.info_text.insert(1.0, info_text)
        self.info_text.config(state='disabled')
    
    def _update_tree_display(self):
        """Update the tree view with configuration data."""
        # Clear existing items
        for item in self.tree.get_children():
            self.tree.delete(item)
        
        config = self.config_manager.get_config()
        if not config:
            return
        
        # Populate tree with configuration data
        self._populate_tree('', config)
        
        # Expand all items by default
        self._expand_all_items()
    
    def _populate_tree(self, parent, data, key_prefix=''):
        """Recursively populate the tree with configuration data."""
        if isinstance(data, dict):
            for key, value in data.items():
                full_key = f"{key_prefix}.{key}" if key_prefix else key
                
                if isinstance(value, (dict, list)):
                    # Create parent node for containers
                    container_type = "Object" if isinstance(value, dict) else "Array"
                    item_id = self.tree.insert(
                        parent, 'end', 
                        text=key, 
                        values=('', container_type),
                        tags=(container_type.lower(),)
                    )
                    self._populate_tree(item_id, value, full_key)
                else:
                    # Create leaf node for values
                    value_str = str(value) if value is not None else 'null'
                    value_type = type(value).__name__
                    
                    # Truncate long values for display
                    if len(value_str) > 100:
                        display_value = value_str[:97] + "..."
                    else:
                        display_value = value_str
                    
                    self.tree.insert(
                        parent, 'end',
                        text=key,
                        values=(display_value, value_type),
                        tags=(value_type,)
                    )
                    
        elif isinstance(data, list):
            for i, item in enumerate(data):
                full_key = f"{key_prefix}[{i}]" if key_prefix else f"[{i}]"
                
                if isinstance(item, (dict, list)):
                    container_type = "Object" if isinstance(item, dict) else "Array"
                    item_id = self.tree.insert(
                        parent, 'end',
                        text=f"[{i}]",
                        values=('', container_type),
                        tags=(container_type.lower(),)
                    )
                    self._populate_tree(item_id, item, full_key)
                else:
                    value_str = str(item) if item is not None else 'null'
                    value_type = type(item).__name__
                    
                    if len(value_str) > 100:
                        display_value = value_str[:97] + "..."
                    else:
                        display_value = value_str
                    
                    self.tree.insert(
                        parent, 'end',
                        text=f"[{i}]",
                        values=(display_value, value_type),
                        tags=(value_type,)
                    )
        
        # Configure tags for styling
        self.tree.tag_configure('object', foreground='blue')
        self.tree.tag_configure('array', foreground='green')
        self.tree.tag_configure('str', foreground='red')
        self.tree.tag_configure('int', foreground='purple')
        self.tree.tag_configure('float', foreground='purple')
        self.tree.tag_configure('bool', foreground='orange')
    
    def _expand_all_items(self):
        """Expand all items in the tree."""
        def expand_item(item):
            self.tree.item(item, open=True)
            for child in self.tree.get_children(item):
                expand_item(child)
        
        for item in self.tree.get_children():
            expand_item(item)
    
    def _on_tree_select(self, event):
        """Handle tree item selection."""
        selection = self.tree.selection()
        if not selection:
            self._update_detail_display()
            return
        
        item = selection[0]
        self._update_detail_display(item)
    
    def _update_detail_display(self, item=None):
        """Update the detail display for the selected item."""
        self.detail_text.config(state='normal')
        self.detail_text.delete(1.0, tk.END)
        
        if not item:
            self.detail_text.insert(1.0, "Select an item in the tree to view details.")
            self.detail_text.config(state='disabled')
            return
        
        # Get item details
        item_text = self.tree.item(item, 'text')
        item_values = self.tree.item(item, 'values')
        
        # Build detail string
        detail_str = f"Setting: {item_text}\n"
        
        if item_values:
            value, value_type = item_values
            detail_str += f"Type: {value_type}\n"
            
            if value and value != '':
                detail_str += f"Value: {value}\n"
                
                # Add additional details based on type
                if value_type in ['str', 'int', 'float']:
                    detail_str += f"Length: {len(str(value))}\n"
                elif value_type == 'bool':
                    detail_str += f"Boolean value: {value}\n"
        
        # Get path to this item
        path = self._get_item_path(item)
        detail_str += f"\nPath: {path}\n"
        
        # Check if this item has children
        children = self.tree.get_children(item)
        if children:
            detail_str += f"\nChildren: {len(children)} items\n"
            
            # List child names
            child_names = [self.tree.item(child, 'text') for child in children[:10]]
            if len(children) > 10:
                child_names.append(f"... and {len(children) - 10} more")
            detail_str += "Child items: " + ", ".join(child_names)
        
        self.detail_text.insert(1.0, detail_str)
        self.detail_text.config(state='disabled')
    
    def _get_item_path(self, item):
        """Get the full path to a tree item."""
        path_parts = []
        current = item
        
        while current:
            item_text = self.tree.item(current, 'text')
            path_parts.insert(0, item_text)
            current = self.tree.parent(current)
        
        return " → ".join(path_parts)
    
    def _on_dialog_close(self):
        """Handle dialog close."""
        self.dialog.destroy()
        self.dialog = None