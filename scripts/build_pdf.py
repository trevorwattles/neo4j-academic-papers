"""Build the pass-off PDF from the screenshots + live query results."""
import json
from datetime import date

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (Image, KeepTogether, PageBreak, Paragraph, Preformatted,
                                SimpleDocTemplate, Spacer, Table, TableStyle)
from reportlab.lib.utils import ImageReader

from db import ROOT, get_driver, run

driver = get_driver()

Q_UNIQUE = """MATCH (p:Paper)-[:IN_CATEGORY]->(c:Category)
WHERE c.category STARTS WITH 'cs.'
RETURN count(DISTINCT p) AS uniqueCsPapers"""
Q_MEMBER = """MATCH (p:Paper)-[:IN_CATEGORY]->(c:Category)
WHERE c.category STARTS WITH 'cs.'
RETURN count(p) AS csCategoryMemberships"""
Q_SUM = """MATCH (c:Category)
WHERE c.category STARTS WITH 'cs.'
RETURN sum(apoc.node.degree(c, "<IN_CATEGORY")) AS sumCsInDegree"""
Q_TOTAL = "MATCH (p:Paper) RETURN count(p) AS totalPapers"
Q_MULTI = """MATCH (p:Paper)-[:IN_CATEGORY]->(c:Category)
WHERE c.category STARTS WITH 'cs.'
WITH p, count(c) AS n WHERE n > 1
RETURN count(p) AS multi"""
Q_PAIRS = """MATCH (c1:Category)<-[:IN_CATEGORY]-(p:Paper)-[:IN_CATEGORY]->(c2:Category)
WHERE c1.category STARTS WITH 'cs.' AND c2.category STARTS WITH 'cs.'
  AND c1.category < c2.category
RETURN c1.category AS category1, c2.category AS category2, count(p) AS sharedPapers
ORDER BY sharedPapers DESC LIMIT 10"""
Q_BACON = """MATCH p = shortestPath(
  (bacon:Person {name: "Kevin Bacon"})-[*]-(nora:Person {name: "Nora Ephron"})
)
RETURN p"""

unique_cs = run(driver, Q_UNIQUE)[0]["uniqueCsPapers"]
member_cs = run(driver, Q_MEMBER)[0]["csCategoryMemberships"]
sum_cs = run(driver, Q_SUM)[0]["sumCsInDegree"]
total = run(driver, Q_TOTAL)[0]["totalPapers"]
multi = run(driver, Q_MULTI)[0]["multi"]
pairs = run(driver, Q_PAIRS)
driver.close()
assert member_cs == sum_cs
bacon = json.loads((ROOT / "output" / "bacon_path.json").read_text())

(ROOT / "output" / "results.json").write_text(json.dumps({
    "totalPapers": total, "uniqueCsPapers": unique_cs, "csCategoryMemberships": member_cs,
    "sumCsInDegree": sum_cs, "papersInMultipleCsCategories": multi, "csPairs": pairs}, indent=2))

# ---------- styles ----------
ss = getSampleStyleSheet()
H1 = ParagraphStyle("H1", parent=ss["Heading1"], fontSize=15, spaceBefore=6, spaceAfter=6,
                    textColor=colors.HexColor("#1f3b57"))
BODY = ParagraphStyle("Body", parent=ss["BodyText"], fontSize=10, leading=14)
CODE = ParagraphStyle("Code", fontName="Courier", fontSize=8.5, leading=11,
                      backColor=colors.HexColor("#f3f3f1"), borderColor=colors.HexColor("#d9d8d3"),
                      borderWidth=0.5, borderPadding=6, spaceBefore=4, spaceAfter=10)
BIG = ParagraphStyle("Big", fontName="Helvetica-Bold", fontSize=40, leading=46,
                     alignment=TA_CENTER, textColor=colors.HexColor("#2a78d6"))
SMALLC = ParagraphStyle("SmallC", parent=BODY, alignment=TA_CENTER, fontSize=9.5,
                        textColor=colors.HexColor("#52514e"))
MID = ParagraphStyle("Mid", fontName="Helvetica-Bold", fontSize=24, leading=30,
                     alignment=TA_CENTER, textColor=colors.HexColor("#52514e"))

W = letter[0] - 1.5 * inch

def img(path, max_w=W, max_h=4.6 * inch):
    iw, ih = ImageReader(str(path)).getSize()
    scale = min(max_w / iw, max_h / ih)
    return Image(str(path), width=iw * scale, height=ih * scale)

def code(text):
    return Preformatted(text, CODE)

story = [
    Paragraph("GraphDB (Neo4j): Academic Papers", ss["Title"]),
    Paragraph(f"Trevor Wattles &nbsp;·&nbsp; CS 452 &nbsp;·&nbsp; {date.today():%B %-d, %Y}", SMALLC),
    Spacer(1, 14),

    Paragraph("1. Bacon Path for Nora Ephron (Movies dataset)", H1),
    Paragraph("Screenshot from the Neo4j Browser (Neo4j 5 + APOC, running locally in Docker):", BODY),
    Spacer(1, 4),
    img(ROOT / "bacon_path_nora_ephron.png", max_h=3.9 * inch),
    Spacer(1, 6),
    code(Q_BACON),
    Paragraph(f"<b>Path (length {bacon['length']}):</b> " +
              bacon["text"].replace("<", "&lt;").replace(">", "&gt;"), BODY),
    PageBreak(),

    Paragraph("2. inDegree vs Category Name (top 20 categories)", H1),
    img(ROOT / "indegree_by_category.png", max_h=4.2 * inch),
    Spacer(1, 4),
    code('MATCH (c:Category)\nRETURN c.category, apoc.node.degree(c, "<IN_CATEGORY") AS inDegree\n'
         'ORDER BY inDegree DESC LIMIT 20'),

    KeepTogether([
        Paragraph("3. Total number of papers in CS categories", H1),
        Table([[Paragraph(f"{unique_cs:,}", BIG), Paragraph(f"{member_cs:,}", MID)],
               [Paragraph("<b>unique CS papers (official answer)</b><br/>count(DISTINCT p)", SMALLC),
                Paragraph("CS paper–category memberships<br/>count(p): cross-listed papers counted "
                          "once per CS category", SMALLC)]],
              colWidths=[W * 0.55, W * 0.45],
              style=TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                                ("LINEAFTER", (0, 0), (0, -1), 0.5, colors.HexColor("#d9d8d3"))])),
        Spacer(1, 6),
        Paragraph(f"For context: {total:,} papers total in the dataset, so "
                  f"{unique_cs / total:.1%} of all papers are in at least one CS category.", SMALLC),
    ]),
    PageBreak(),

    Paragraph("4. The queries", H1),
    Paragraph("<b>(A) Official answer: unique papers in at least one CS category</b>", BODY),
    code(Q_UNIQUE),
    Paragraph(f"Result: <b>{unique_cs:,}</b>", BODY),
    Spacer(1, 6),
    Paragraph("<b>(B) Paper–category memberships (a paper in cs.AI and cs.LG counts twice)</b>", BODY),
    code(Q_MEMBER),
    Paragraph(f"Result: <b>{member_cs:,}</b>", BODY),
    Spacer(1, 6),
    Paragraph("<b>(C) Cross-check with sum() over APOC in-degrees (equals B)</b>", BODY),
    code(Q_SUM),
    Paragraph(f"Result: <b>{sum_cs:,}</b>", BODY),

    Paragraph("5. Unique papers or once per CS category?", H1),
    Paragraph(
        f"The <b>official answer is {unique_cs:,}</b>, from query (A), which counts <b>unique</b> papers. "
        "<font face='Courier'>MATCH (p:Paper)-[:IN_CATEGORY]-&gt;(c:Category)</font> produces one row for "
        "<i>every</i> paper–category relationship, so a paper listed in several CS categories appears in "
        "several rows. <font face='Courier'>count(DISTINCT p)</font> removes those duplicates before counting.", BODY),
    Spacer(1, 4),
    Paragraph(
        f"Query (B) uses plain <font face='Courier'>count(p)</font>, so it counts a paper <b>once per CS "
        f"category it is in</b> and gets {member_cs:,}. Query (C) sums the bar heights of the CS categories "
        f"and gets the same number for the same reason. The difference of <b>{member_cs - unique_cs:,}</b> comes "
        f"from the {multi:,} CS papers that are cross-listed in two or more CS categories "
        "(e.g. cs.LG + cs.AI).", BODY),

    PageBreak(),
    Paragraph("6. Something fun: which CS categories are cross-listed together most?", H1),
    code(Q_PAIRS),
]
rows = [["#", "Category 1", "Category 2", "Shared papers"]] + \
       [[str(i + 1), r["category1"], r["category2"], f"{r['sharedPapers']:,}"] for i, r in enumerate(pairs)]
story.append(Table(rows, colWidths=[0.4 * inch, 1.6 * inch, 1.6 * inch, 1.3 * inch], hAlign="LEFT",
                   style=TableStyle([
                       ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                       ("FONTSIZE", (0, 0), (-1, -1), 9.5),
                       ("LINEBELOW", (0, 0), (-1, 0), 0.8, colors.HexColor("#52514e")),
                       ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f6f6f4")]),
                       ("ALIGN", (3, 0), (3, -1), "RIGHT"),
                   ])))
story.append(Spacer(1, 8))
top = pairs[0]
FUN_INTERPRETATION = (ROOT / "output" / "fun_interpretation.txt")
story.append(Paragraph(
    FUN_INTERPRETATION.read_text().strip() if FUN_INTERPRETATION.exists() else
    f"The most common CS pairing is {top['category1']} + {top['category2']} ({top['sharedPapers']:,} papers).",
    BODY))
story.append(Spacer(1, 6))
story.append(Paragraph(
    "<i>How it works:</i> the pattern <font face='Courier'>(c1)&lt;-[:IN_CATEGORY]-(p)-[:IN_CATEGORY]-&gt;(c2)</font> "
    "finds two category memberships of the same paper. <font face='Courier'>c1.category &lt; c2.category</font> "
    "keeps each unordered pair once and removes self-pairs.", BODY))

doc = SimpleDocTemplate(str(ROOT / "neo4j_academic_papers_passoff.pdf"), pagesize=letter,
                        leftMargin=0.75 * inch, rightMargin=0.75 * inch,
                        topMargin=0.7 * inch, bottomMargin=0.7 * inch,
                        title="GraphDB (Neo4j): Academic Papers - Trevor Wattles", author="Trevor Wattles")
doc.build(story)
print("built PDF; unique", unique_cs, "memberships", member_cs, "total", total, "multi", multi)
