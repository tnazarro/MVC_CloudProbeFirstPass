"""
PDF report generation module for particle data analysis.
"""

import io
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any
import matplotlib.pyplot as plt
import matplotlib.figure

try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import letter, A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle
    from reportlab.platypus import PageBreak
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False

logger = logging.getLogger(__name__)

class PDFReportGenerator:
    """Generates PDF reports for particle data analysis."""
    
    def __init__(self):
        if not REPORTLAB_AVAILABLE:
            raise ImportError(
                "ReportLab is required for PDF generation. "
                "Install it with: pip install reportlab"
            )
        
        self.styles = getSampleStyleSheet()
        self._setup_custom_styles()
    
    def _setup_custom_styles(self):
        """Setup custom paragraph styles for the report."""
        # Title style
        self.styles.add(ParagraphStyle(
            name='CustomTitle',
            parent=self.styles['Title'],
            fontSize=18,
            textColor=colors.darkblue,
            spaceAfter=20,
            alignment=1  # Center alignment
        ))
        
        # Subtitle style
        self.styles.add(ParagraphStyle(
            name='Subtitle',
            parent=self.styles['Heading2'],
            fontSize=14,
            textColor=colors.darkblue,
            spaceBefore=15,
            spaceAfter=10
        ))
        
        # Data style for statistics
        self.styles.add(ParagraphStyle(
            name='DataText',
            parent=self.styles['Normal'],
            fontSize=10,
            fontName='Courier'
        ))
    
    def generate_report(self, 
                       output_path: str,
                       plot_figure: matplotlib.figure.Figure,
                       data_stats: Dict[str, Any],
                       analysis_params: Dict[str, Any],
                       file_info: Optional[Dict[str, Any]] = None) -> bool:
        """
        Generate a PDF report with plot and statistics.
        
        Args:
            output_path: Path where PDF should be saved
            plot_figure: Matplotlib figure to include in report
            data_stats: Dictionary of data statistics
            analysis_params: Analysis parameters (bins, mode, etc.)
            file_info: Optional file information
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Create the PDF document
            doc = SimpleDocTemplate(
                output_path,
                pagesize=A4,
                rightMargin=72,
                leftMargin=72,
                topMargin=72,
                bottomMargin=18
            )
            
            # Build the story (content)
            story = []
            
            # Title and header
            story.extend(self._create_header(file_info))
            
            # Analysis summary
            story.extend(self._create_analysis_summary(analysis_params))
            
            # Statistics section
            story.extend(self._create_statistics_section(data_stats))
            
            # Plot section
            story.extend(self._create_plot_section(plot_figure))
            
            # Footer/metadata
            story.extend(self._create_footer())
            
            # Build the PDF
            doc.build(story)
            
            logger.info(f"PDF report generated successfully: {output_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to generate PDF report: {e}")
            return False
    
    def _create_header(self, file_info: Optional[Dict[str, Any]]) -> list:
        """Create the report header section."""
        elements = []
        
        # Main title
        title = Paragraph("Particle Size Distribution Analysis Report", self.styles['CustomTitle'])
        elements.append(title)
        elements.append(Spacer(1, 12))
        
        # Report generation info
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        info_text = f"<b>Report Generated:</b> {timestamp}"
        
        if file_info and 'filename' in file_info:
            info_text += f"<br/><b>Source File:</b> {file_info['filename']}"
        
        elements.append(Paragraph(info_text, self.styles['Normal']))
        elements.append(Spacer(1, 20))
        
        return elements
    
    def _create_analysis_summary(self, analysis_params: Dict[str, Any]) -> list:
        """Create the analysis parameters summary section."""
        elements = []
        
        elements.append(Paragraph("Analysis Parameters", self.styles['Subtitle']))
        
        # Create parameter table
        param_data = []
        
        if 'data_mode' in analysis_params:
            mode_display = "Pre-aggregated (Size + Frequency)" if analysis_params['data_mode'] == 'pre_aggregated' else "Raw Measurements (Size only)"
            param_data.append(['Data Mode:', mode_display])
        
        if 'bin_count' in analysis_params:
            param_data.append(['Histogram Bins:', str(analysis_params['bin_count'])])
        
        if 'size_column' in analysis_params:
            param_data.append(['Size Column:', analysis_params['size_column']])
        
        if 'frequency_column' in analysis_params:
            param_data.append(['Frequency Column:', analysis_params['frequency_column'] or 'N/A'])
        
        if 'skip_rows' in analysis_params and analysis_params['skip_rows'] > 0:
            param_data.append(['Rows Skipped:', str(analysis_params['skip_rows'])])
        
        if 'show_stats_lines' in analysis_params:
            stats_display = "Yes" if analysis_params['show_stats_lines'] else "No"
            param_data.append(['Statistical Lines:', stats_display])
        
        if param_data:
            param_table = Table(param_data, colWidths=[2*inch, 3*inch])
            param_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (0, -1), colors.lightgrey),
                ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
                ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ]))
            elements.append(param_table)
        
        elements.append(Spacer(1, 20))
        return elements
    
    def _create_statistics_section(self, data_stats: Dict[str, Any]) -> list:
        """Create the data statistics section."""
        elements = []
        
        elements.append(Paragraph("Data Statistics", self.styles['Subtitle']))
        
        # Create statistics table
        stats_data = []
        
        # Basic data info
        if 'total_rows' in data_stats:
            stats_data.append(['Total Rows:', str(data_stats['total_rows'])])
        
        if 'total_columns' in data_stats:
            stats_data.append(['Total Columns:', str(data_stats['total_columns'])])
        
        # Size statistics
        if 'size_min' in data_stats:
            stats_data.append(['Size Range (Min):', f"{data_stats['size_min']:.3f}"])
            stats_data.append(['Size Range (Max):', f"{data_stats['size_max']:.3f}"])
            stats_data.append(['Size Mean:', f"{data_stats['size_mean']:.3f}"])
        
        # Mode-specific statistics
        if data_stats.get('data_mode') == 'raw_measurements':
            if 'total_measurements' in data_stats:
                stats_data.append(['Total Measurements:', str(data_stats['total_measurements'])])
            if 'unique_measurements' in data_stats:
                stats_data.append(['Unique Values:', str(data_stats['unique_measurements'])])
        
        elif data_stats.get('data_mode') == 'pre_aggregated':
            if 'total_frequency' in data_stats:
                stats_data.append(['Total Frequency:', f"{data_stats['total_frequency']:.0f}"])
            if 'frequency_mean' in data_stats:
                stats_data.append(['Mean Frequency:', f"{data_stats['frequency_mean']:.2f}"])
        
        if stats_data:
            stats_table = Table(stats_data, colWidths=[2*inch, 2*inch])
            stats_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (0, -1), colors.lightblue),
                ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
                ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ]))
            elements.append(stats_table)
        
        elements.append(Spacer(1, 20))
        return elements
    
    def _create_plot_section(self, plot_figure: matplotlib.figure.Figure) -> list:
        """Create the plot section with embedded matplotlib figure."""
        elements = []
        
        elements.append(Paragraph("Distribution Plot", self.styles['Subtitle']))
        
        try:
            # Save figure to bytes buffer
            img_buffer = io.BytesIO()
            plot_figure.savefig(img_buffer, format='png', dpi=300, bbox_inches='tight')
            img_buffer.seek(0)
            
            # Create ReportLab Image
            img = Image(img_buffer, width=6*inch, height=4.5*inch)
            elements.append(img)
            
            # Add plot description
            plot_desc = Paragraph(
                "The histogram above shows the particle size distribution with statistical reference lines. "
                "Red line indicates the mean, orange dashed lines show ±1 standard deviation, "
                "and purple dotted lines show ±2 standard deviations.",
                self.styles['Normal']
            )
            elements.append(Spacer(1, 12))
            elements.append(plot_desc)
            
        except Exception as e:
            logger.error(f"Failed to embed plot in PDF: {e}")
            error_text = Paragraph(
                f"<b>Error:</b> Could not embed plot in report. {str(e)}",
                self.styles['Normal']
            )
            elements.append(error_text)
        
        elements.append(Spacer(1, 20))
        return elements
    
    def _create_footer(self) -> list:
        """Create the report footer section."""
        elements = []
        
        # Add page break before footer if needed
        elements.append(Spacer(1, 30))
        
        # Software info
        footer_text = Paragraph(
            "<i>Report generated by Particle Data Analyzer v1.0</i>",
            self.styles['Normal']
        )
        elements.append(footer_text)
        
        return elements