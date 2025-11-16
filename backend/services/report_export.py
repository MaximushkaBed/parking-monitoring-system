"""
Report export module
Exports analytics reports to PDF, Excel, and CSV formats
"""

import io
from typing import Dict, List, Optional
from datetime import datetime
import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_CENTER, TA_LEFT
import matplotlib
matplotlib.use('Agg')  # Non-interactive backend
import matplotlib.pyplot as plt
import logging

logger = logging.getLogger(__name__)


class ReportExporter:
    """
    Export parking analytics reports to various formats
    """
    
    def __init__(self):
        """Initialize report exporter"""
        self.styles = getSampleStyleSheet()
        
        # Custom styles
        self.title_style = ParagraphStyle(
            'CustomTitle',
            parent=self.styles['Heading1'],
            fontSize=24,
            textColor=colors.HexColor('#1a1a1a'),
            spaceAfter=30,
            alignment=TA_CENTER
        )
        
        self.heading_style = ParagraphStyle(
            'CustomHeading',
            parent=self.styles['Heading2'],
            fontSize=16,
            textColor=colors.HexColor('#333333'),
            spaceAfter=12,
            spaceBefore=12
        )
    
    def export_to_csv(
        self,
        data: Dict,
        filename: str = "parking_report.csv"
    ) -> bytes:
        """
        Export data to CSV
        
        Args:
            data: Analytics data dictionary
            filename: Output filename
            
        Returns:
            CSV file content as bytes
        """
        logger.info(f"Exporting to CSV: {filename}")
        
        # Prepare data for CSV
        rows = []
        
        # Summary section
        if 'summary' in data:
            summary = data['summary']
            rows.append(['Summary', ''])
            rows.append(['Total Places', summary.get('total_places', 0)])
            rows.append(['Occupied', summary.get('occupied', 0)])
            rows.append(['Free', summary.get('free', 0)])
            rows.append(['Occupancy Rate (%)', f"{summary.get('occupancy_rate', 0):.2f}"])
            rows.append(['', ''])
        
        # Duration statistics
        if 'duration' in data:
            duration = data['duration']
            rows.append(['Duration Statistics', ''])
            rows.append(['Average Duration (hours)', f"{duration.get('average_hours', 0):.2f}"])
            rows.append(['Median Duration (hours)', f"{duration.get('median_seconds', 0) / 3600:.2f}"])
            rows.append(['Min Duration (hours)', f"{duration.get('min_seconds', 0) / 3600:.2f}"])
            rows.append(['Max Duration (hours)', f"{duration.get('max_seconds', 0) / 3600:.2f}"])
            rows.append(['', ''])
        
        # Turnover
        if 'turnover' in data:
            turnover = data['turnover']
            rows.append(['Turnover', ''])
            rows.append(['Turnover Rate (vehicles/day/place)', f"{turnover.get('turnover_rate', 0):.2f}"])
            rows.append(['Period (days)', f"{turnover.get('period_days', 0):.1f}"])
            rows.append(['', ''])
        
        # Peak hours
        if 'peak_hours' in data:
            rows.append(['Peak Hours', 'Occupancy Count'])
            for hour, count in sorted(data['peak_hours'].items()):
                rows.append([f"{hour}:00", count])
            rows.append(['', ''])
        
        # Anomalies
        if 'anomalies' in data and data['anomalies']:
            rows.append(['Anomalies (Long-stay vehicles)', ''])
            rows.append(['Place ID', 'Track ID', 'Duration (hours)', 'Status'])
            for anomaly in data['anomalies']:
                rows.append([
                    anomaly.get('place_id'),
                    anomaly.get('track_id'),
                    f"{anomaly.get('duration_hours', 0):.2f}",
                    anomaly.get('status')
                ])
        
        # Create DataFrame and export to CSV
        df = pd.DataFrame(rows)
        
        # Convert to CSV bytes
        csv_buffer = io.StringIO()
        df.to_csv(csv_buffer, index=False, header=False)
        csv_bytes = csv_buffer.getvalue().encode('utf-8')
        
        logger.info(f"CSV export completed: {len(csv_bytes)} bytes")
        return csv_bytes
    
    def export_to_excel(
        self,
        data: Dict,
        filename: str = "parking_report.xlsx"
    ) -> bytes:
        """
        Export data to Excel
        
        Args:
            data: Analytics data dictionary
            filename: Output filename
            
        Returns:
            Excel file content as bytes
        """
        logger.info(f"Exporting to Excel: {filename}")
        
        excel_buffer = io.BytesIO()
        
        with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
            # Summary sheet
            if 'summary' in data:
                summary_data = {
                    'Metric': ['Total Places', 'Occupied', 'Free', 'Occupancy Rate (%)'],
                    'Value': [
                        data['summary'].get('total_places', 0),
                        data['summary'].get('occupied', 0),
                        data['summary'].get('free', 0),
                        f"{data['summary'].get('occupancy_rate', 0):.2f}"
                    ]
                }
                df_summary = pd.DataFrame(summary_data)
                df_summary.to_excel(writer, sheet_name='Summary', index=False)
            
            # Duration statistics sheet
            if 'duration' in data:
                duration = data['duration']
                duration_data = {
                    'Metric': [
                        'Average Duration (hours)',
                        'Median Duration (hours)',
                        'Min Duration (hours)',
                        'Max Duration (hours)',
                        'Std Deviation (hours)'
                    ],
                    'Value': [
                        f"{duration.get('average_hours', 0):.2f}",
                        f"{duration.get('median_seconds', 0) / 3600:.2f}",
                        f"{duration.get('min_seconds', 0) / 3600:.2f}",
                        f"{duration.get('max_seconds', 0) / 3600:.2f}",
                        f"{duration.get('std_seconds', 0) / 3600:.2f}"
                    ]
                }
                df_duration = pd.DataFrame(duration_data)
                df_duration.to_excel(writer, sheet_name='Duration', index=False)
            
            # Peak hours sheet
            if 'peak_hours' in data:
                peak_data = {
                    'Hour': [f"{h}:00" for h in range(24)],
                    'Occupancy Count': [data['peak_hours'].get(h, 0) for h in range(24)]
                }
                df_peak = pd.DataFrame(peak_data)
                df_peak.to_excel(writer, sheet_name='Peak Hours', index=False)
            
            # Anomalies sheet
            if 'anomalies' in data and data['anomalies']:
                anomalies_data = {
                    'Place ID': [a.get('place_id') for a in data['anomalies']],
                    'Track ID': [a.get('track_id') for a in data['anomalies']],
                    'Duration (hours)': [f"{a.get('duration_hours', 0):.2f}" for a in data['anomalies']],
                    'Status': [a.get('status') for a in data['anomalies']]
                }
                df_anomalies = pd.DataFrame(anomalies_data)
                df_anomalies.to_excel(writer, sheet_name='Anomalies', index=False)
            
            # Heatmap sheet (if available)
            if 'heatmap' in data and 'by_place' in data['heatmap']:
                heatmap_data = {
                    'Place ID': list(data['heatmap']['by_place'].keys()),
                    'Usage Score': list(data['heatmap']['by_place'].values())
                }
                df_heatmap = pd.DataFrame(heatmap_data)
                df_heatmap.to_excel(writer, sheet_name='Heatmap', index=False)
        
        excel_bytes = excel_buffer.getvalue()
        logger.info(f"Excel export completed: {len(excel_bytes)} bytes")
        return excel_bytes
    
    def export_to_pdf(
        self,
        data: Dict,
        filename: str = "parking_report.pdf"
    ) -> bytes:
        """
        Export data to PDF with charts
        
        Args:
            data: Analytics data dictionary
            filename: Output filename
            
        Returns:
            PDF file content as bytes
        """
        logger.info(f"Exporting to PDF: {filename}")
        
        pdf_buffer = io.BytesIO()
        doc = SimpleDocTemplate(pdf_buffer, pagesize=A4)
        story = []
        
        # Title
        period = data.get('period', {})
        title_text = f"Parking Analytics Report"
        if period:
            start = period.get('start', '')
            end = period.get('end', '')
            if start and end:
                title_text += f"<br/>{start[:10]} to {end[:10]}"
        
        story.append(Paragraph(title_text, self.title_style))
        story.append(Spacer(1, 0.3*inch))
        
        # Summary section
        if 'summary' in data:
            story.append(Paragraph("Summary", self.heading_style))
            
            summary = data['summary']
            summary_data = [
                ['Metric', 'Value'],
                ['Total Places', str(summary.get('total_places', 0))],
                ['Occupied', str(summary.get('occupied', 0))],
                ['Free', str(summary.get('free', 0))],
                ['Occupancy Rate', f"{summary.get('occupancy_rate', 0):.2f}%"]
            ]
            
            summary_table = Table(summary_data, colWidths=[3*inch, 2*inch])
            summary_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 12),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ]))
            
            story.append(summary_table)
            story.append(Spacer(1, 0.3*inch))
        
        # Duration statistics
        if 'duration' in data:
            story.append(Paragraph("Duration Statistics", self.heading_style))
            
            duration = data['duration']
            duration_data = [
                ['Metric', 'Value'],
                ['Average Duration', f"{duration.get('average_hours', 0):.2f} hours"],
                ['Median Duration', f"{duration.get('median_seconds', 0) / 3600:.2f} hours"],
                ['Min Duration', f"{duration.get('min_seconds', 0) / 3600:.2f} hours"],
                ['Max Duration', f"{duration.get('max_seconds', 0) / 3600:.2f} hours"]
            ]
            
            duration_table = Table(duration_data, colWidths=[3*inch, 2*inch])
            duration_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 12),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ]))
            
            story.append(duration_table)
            story.append(Spacer(1, 0.3*inch))
        
        # Peak hours chart
        if 'peak_hours' in data:
            story.append(Paragraph("Peak Hours", self.heading_style))
            
            # Create chart
            fig, ax = plt.subplots(figsize=(8, 4))
            hours = list(range(24))
            counts = [data['peak_hours'].get(h, 0) for h in hours]
            
            ax.bar(hours, counts, color='steelblue')
            ax.set_xlabel('Hour of Day')
            ax.set_ylabel('Occupancy Count')
            ax.set_title('Parking Occupancy by Hour')
            ax.set_xticks(hours[::2])
            ax.grid(axis='y', alpha=0.3)
            
            # Save chart to buffer
            chart_buffer = io.BytesIO()
            plt.savefig(chart_buffer, format='png', dpi=150, bbox_inches='tight')
            plt.close(fig)
            chart_buffer.seek(0)
            
            # Add chart to PDF
            img = Image(chart_buffer, width=6*inch, height=3*inch)
            story.append(img)
            story.append(Spacer(1, 0.3*inch))
        
        # Anomalies
        if 'anomalies' in data and data['anomalies']:
            story.append(PageBreak())
            story.append(Paragraph("Anomalies (Long-stay Vehicles)", self.heading_style))
            
            anomaly_data = [['Place ID', 'Track ID', 'Duration (hours)', 'Status']]
            for anomaly in data['anomalies'][:20]:  # Limit to 20
                anomaly_data.append([
                    str(anomaly.get('place_id')),
                    str(anomaly.get('track_id')),
                    f"{anomaly.get('duration_hours', 0):.2f}",
                    anomaly.get('status')
                ])
            
            anomaly_table = Table(anomaly_data, colWidths=[1.5*inch, 1.5*inch, 1.5*inch, 1.5*inch])
            anomaly_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ]))
            
            story.append(anomaly_table)
        
        # Build PDF
        doc.build(story)
        pdf_bytes = pdf_buffer.getvalue()
        
        logger.info(f"PDF export completed: {len(pdf_bytes)} bytes")
        return pdf_bytes


def create_report_exporter() -> ReportExporter:
    """Factory function to create report exporter"""
    return ReportExporter()
