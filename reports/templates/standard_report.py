"""
Standard report template for particle size analysis.
"""

from typing import Dict, Any, Optional
import matplotlib.figure
from ..pdf_generator import PDFReportGenerator

class StandardReportTemplate:
    """Standard template for particle analysis reports."""
    
    def __init__(self):
        self.generator = PDFReportGenerator()
    
    def create_report(self,
                     output_path: str,
                     plot_figure: matplotlib.figure.Figure,
                     data_stats: Dict[str, Any],
                     analysis_params: Dict[str, Any],
                     file_info: Optional[Dict[str, Any]] = None,
                     custom_title: Optional[str] = None) -> bool:
        """
        Create a standard particle analysis report.
        
        Args:
            output_path: Where to save the PDF
            plot_figure: The main distribution plot
            data_stats: Statistics from data processor
            analysis_params: Analysis settings used
            file_info: Information about source file
            custom_title: Optional custom report title
            
        Returns:
            bool: Success status
        """
        
        # Enhance file info if provided
        enhanced_file_info = file_info or {}
        if custom_title:
            enhanced_file_info['custom_title'] = custom_title
        
        # Ensure all required parameters are present
        enhanced_params = self._prepare_analysis_params(analysis_params)
        
        return self.generator.generate_report(
            output_path=output_path,
            plot_figure=plot_figure,
            data_stats=data_stats,
            analysis_params=enhanced_params,
            file_info=enhanced_file_info
        )
    
    def _prepare_analysis_params(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Ensure analysis parameters have default values."""
        defaults = {
            'data_mode': 'pre_aggregated',
            'bin_count': 50,
            'size_column': 'Unknown',
            'frequency_column': None,
            'skip_rows': 0,
            'show_stats_lines': True
        }
        
        # Merge with provided params
        enhanced = defaults.copy()
        enhanced.update(params)
        
        return enhanced