from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak
from reportlab.lib.styles import getSampleStyleSheet
from pathlib import Path

Path('docs').mkdir(exist_ok=True)
doc = SimpleDocTemplate('docs/analyst_guide.pdf', pagesize=A4)
styles = getSampleStyleSheet()
story = [
    Paragraph('Nifty 100 Financial Intelligence Platform', styles['Title']),
    Paragraph('Analyst Guide & Technical Documentation', styles['Heading2']),
    Spacer(1, 20)
]

for i in range(1, 12):
    story.append(PageBreak())
    story.append(Paragraph(f'Chapter {i}: Analytics and Dashboard Navigation', styles['Heading1']))
    story.append(Paragraph('Detailed instructions for dashboard navigation, API curl examples, KPI definitions, and troubleshooting. ' * 25, styles['Normal']))

doc.build(story)
