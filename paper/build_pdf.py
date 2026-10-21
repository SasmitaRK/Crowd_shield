"""Build paper/crowd_shield_report.pdf from the Markdown report (needs `markdown` and `fpdf2`).

    python paper/build_pdf.py [path/to/fonts]

The fonts must cover symbols like ², ≈ and →; Arial from Windows or any TTF family with
regular, bold and italic files works.
"""

import re
import sys
from pathlib import Path

import markdown
from fpdf import FPDF, FontFace

HERE = Path(__file__).resolve().parent
FONTS = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("C:/Windows/Fonts")
md = (HERE / "crowd_shield_report.md").read_text(encoding="utf-8")
html = markdown.markdown(md, extensions=["tables"])
# fpdf2's HTML renderer: give tables borders and column widths, and drop inline <code> styling.
html = html.replace("<table>", '<table border="1" cellpadding="3" width="100%">')
html = re.sub(r"</?code>", "", html)
# Images: resolve paths relative to this folder and fit them to the text width.
html = re.sub(r'<img alt="([^"]*)" src="([^"]+)"',
              lambda m: f'<img width="470" alt="{m.group(1)}" src="{(HERE / m.group(2)).resolve().as_posix()}"', html)


class Report(FPDF):
    def footer(self):
        self.set_y(-12)
        self.set_font("body", "", 8)
        self.set_text_color(120, 120, 120)
        self.cell(0, 6, f"Crowd Shield technical report  ·  {self.page_no()}", align="C")


pdf = Report(format="A4")
pdf.add_font("body", "", str(FONTS / "arial.ttf"))
pdf.add_font("body", "B", str(FONTS / "arialbd.ttf"))
pdf.add_font("body", "I", str(FONTS / "ariali.ttf"))
pdf.add_font("body", "BI", str(FONTS / "arialbi.ttf"))
pdf.set_margins(20, 18, 20)
pdf.set_auto_page_break(True, 16)
pdf.add_page()
pdf.set_font("body", "", 10)
TEAL = (15, 118, 110)
styles = {"h1": FontFace(color=(15, 23, 42), size_pt=21, emphasis="BOLD"),
          "h2": FontFace(color=TEAL, size_pt=14, emphasis="BOLD"),
          "h3": FontFace(color=(15, 23, 42), size_pt=11.5, emphasis="BOLD")}
pdf.write_html(html, font_family="body", tag_styles=styles)
out = HERE / "crowd_shield_report.pdf"
pdf.output(str(out))
print(out, pdf.page_no(), "pages")
