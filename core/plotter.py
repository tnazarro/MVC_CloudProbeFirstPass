# core/plotter.py
"""
Plotting module for particle data visualization.
"""

import matplotlib.pyplot as plt
import matplotlib.figure
import numpy as np
import logging
from typing import Optional, Tuple
from config.constants import PLOT_WIDTH, PLOT_HEIGHT, PLOT_DPI, DEFAULT_BIN_COUNT

logger = logging.getLogger(__name__)

class ParticlePlotter:
    """Handles plotting of particle sizing data."""
    
    def __init__(self):
        self.figure = None
        self.ax = None
        self._setup_matplotlib()
    
    def _setup_matplotlib(self):
        """Configure matplotlib settings."""
        plt.style.use('default')  # Use default style for now
    
    def create_histogram(self, size_data: np.ndarray, frequency_data: Optional[np.ndarray] = None, 
                        bin_count: int = DEFAULT_BIN_COUNT, title: str = "Particle Size Distribution") -> matplotlib.figure.Figure:
        """
        Create a histogram plot of particle size data.
        
        Args:
            size_data: Array of particle sizes
            frequency_data: Optional array of frequencies (if None, uses count histogram)
            bin_count: Number of bins for the histogram
            title: Plot title
            
        Returns:
            matplotlib Figure object
        """
        try:
            # Create figure and axis
            self.figure = plt.figure(figsize=(PLOT_WIDTH, PLOT_HEIGHT), dpi=PLOT_DPI)
            self.ax = self.figure.add_subplot(111)
            
            if frequency_data is not None:
                # Weighted histogram using frequency data
                self.ax.hist(size_data, bins=bin_count, weights=frequency_data, 
                           alpha=0.7, edgecolor='black', linewidth=0.5)
                self.ax.set_ylabel('Frequency')
            else:
                # Simple count histogram
                self.ax.hist(size_data, bins=bin_count, alpha=0.7, 
                           edgecolor='black', linewidth=0.5)
                self.ax.set_ylabel('Count')
            
            self.ax.set_xlabel('Particle Size')
            self.ax.set_title(title)
            self.ax.grid(True, alpha=0.3)
            
            # Add some basic statistics to the plot
            self._add_stats_text(size_data, frequency_data)
            
            self.figure.tight_layout()
            logger.info(f"Created histogram with {bin_count} bins")
            
            return self.figure
            
        except Exception as e:
            logger.error(f"Error creating histogram: {e}")
            return None
    
    def _add_stats_text(self, size_data: np.ndarray, frequency_data: Optional[np.ndarray]):
        """Add statistics text box to the plot."""
        try:
            if frequency_data is not None:
                # Calculate weighted statistics
                weights = frequency_data / np.sum(frequency_data)
                mean_size = np.average(size_data, weights=frequency_data)
                # For weighted std, we need a more complex calculation
                variance = np.average((size_data - mean_size)**2, weights=frequency_data)
                std_size = np.sqrt(variance)
            else:
                mean_size = np.mean(size_data)
                std_size = np.std(size_data)
            
            stats_text = f'Mean: {mean_size:.2f}\nStd: {std_size:.2f}\nN: {len(size_data)}'
            
            # Add text box
            self.ax.text(0.02, 0.98, stats_text, transform=self.ax.transAxes, 
                        verticalalignment='top', bbox=dict(boxstyle='round', 
                        facecolor='white', alpha=0.8))
            
        except Exception as e:
            logger.error(f"Error adding stats text: {e}")
    
    def update_bin_count(self, size_data: np.ndarray, frequency_data: Optional[np.ndarray], 
                        new_bin_count: int):
        """Update the histogram with a new bin count."""
        if self.figure is None:
            return
        
        self.ax.clear()
        self.create_histogram(size_data, frequency_data, new_bin_count)
    
    def save_plot(self, filename: str, dpi: int = 300):
        """Save the current plot to file."""
        if self.figure is None:
            logger.error("No plot to save")
            return False
        
        try:
            self.figure.savefig(filename, dpi=dpi, bbox_inches='tight')
            logger.info(f"Plot saved to {filename}")
            return True
        except Exception as e:
            logger.error(f"Error saving plot: {e}")
            return False