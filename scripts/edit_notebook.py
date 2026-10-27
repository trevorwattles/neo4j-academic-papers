"""Edit the class starter notebook so it runs top-to-bottom headless against the .env database.

Starts from scripts/neo4j_lab.original.ipynb (the untouched class notebook) every time,
so this script is idempotent.
"""
from pathlib import Path

import nbformat
from nbformat.v4 import new_code_cell, new_markdown_cell

ROOT = Path(__file__).resolve().parent.parent
nb = nbformat.read(ROOT / "scripts" / "neo4j_lab.original.ipynb", as_version=4)
cells = nb.cells

def src(i):
    return cells[i].source

# --- sanity: make sure we're editing the cells we think we are ---
assert "bolt_uri" in src(3)
assert "neo4j-driver" in src(4)
assert "curl" in src(9)
assert "read_csv" in src(10)
assert "top_cat_df.plot.bar" in src(20)
assert "YOUR CODE HERE" in src(21) and "YOUR CODE HERE" in src(22) and "YOUR CODE HERE" in src(23)

cells[1].source += (
    "\n\n> **This run:** instead of a Sandbox, Neo4j 5 runs locally in Docker with the APOC plugin "
    "(see `README.md`). Credentials live in a `.env` file that is **not** committed to git."
)

# Credentials from .env instead of hardcoded strings (variable names unchanged)
cells[3].source = '''# (Run this and read to understand)
# Credentials are loaded from a .env file (never hardcode passwords in a notebook!)
# .env contains NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD and is listed in .gitignore.
import os
from dotenv import load_dotenv

load_dotenv()

bolt_uri = os.getenv("NEO4J_URI", "")   # BOLT URL, e.g. bolt://localhost:7687
user = os.getenv("NEO4J_USER", "")
pwd = os.getenv("NEO4J_PASSWORD", "")

if not (bolt_uri and user and pwd):
     raise ValueError('PLEASE CHANGE THE VALUES SO YOU CAN CONNECT TO THE DATABASE!')
'''

# neo4j-driver is the deprecated package name; the package is now just `neo4j`
cells[4].source = "%pip install -q neo4j python-dotenv"

# Download only if missing; fall back to the LFS media URL if we got a pointer file
cells[9].source = '''# Download part of the 4 gig file from the tutorial (skipped if already downloaded)
import os
if not os.path.exists("metadata.csv") or os.path.getsize("metadata.csv") < 1_000_000:
    !curl -sL "https://github.com/byu-cs-452/byu-cs-452-class-content/raw/main/bigdata/metadata.csv" > metadata.csv
if os.path.getsize("metadata.csv") < 1_000_000:  # got a Git LFS pointer instead of the data
    !curl -sL "https://media.githubusercontent.com/media/byu-cs-452/byu-cs-452-class-content/main/bigdata/metadata.csv" > metadata.csv
print(f"metadata.csv: {os.path.getsize('metadata.csv') / 1e6:.1f} MB")
'''

# Keep arXiv ids as strings: pandas would parse 0809.1640 as the float 809.164
cells[10].source = '''# Read the data in from a csv file
# dtype={'id': str} keeps arXiv ids like "0809.1640" intact (otherwise pandas parses them as the float 809.164)
df = pd.read_csv("metadata.csv", dtype={"id": str})
print(df.shape)
'''

# Save the required pass-off chart
cells[20].source = src(20).rstrip() + '''
plt.savefig("indegree_by_category.png", bbox_inches="tight", dpi=150)
plt.show()
'''

# ---------- YOUR CODE HERE cells ----------
cells[21].source = '''# Can you show the indegree of just computer science type category papers?

# WHERE ... STARTS WITH 'cs.' keeps only computer-science categories (cs.AI, cs.LG, ...)
# apoc.node.degree(c, "<IN_CATEGORY") counts the IN_CATEGORY relationships pointing INTO c (= papers in c)
query_string = \'\'\'
MATCH (c:Category)
WHERE c.category STARTS WITH 'cs.'
RETURN c.category, apoc.node.degree(c, "<IN_CATEGORY") AS inDegree
ORDER BY inDegree DESC
\'\'\'

cs_cat_df = pd.DataFrame([dict(_) for _ in conn.query(query_string)])
print(f"{len(cs_cat_df)} CS categories")
cs_cat_df
'''

cs_chart = new_code_cell('''# Bar chart of papers per CS category (horizontal so the ~40 labels stay readable)
plot_df = cs_cat_df.sort_values("inDegree")
fig, ax = plt.subplots(figsize=(8, 10))
ax.barh(plot_df["c.category"], plot_df["inDegree"], color="#2a78d6", height=0.7)
for y, v in enumerate(plot_df["inDegree"]):
    ax.text(v, y, f" {v:,}", va="center", fontsize=8, color="#52514e")
ax.set_title("Papers in each CS category (inDegree)", loc="left")
ax.set_xlabel("Papers (incoming IN_CATEGORY relationships)")
ax.spines[["top", "right"]].set_visible(False)
ax.grid(axis="x", color="#e5e4e0", linewidth=0.8)
ax.set_axisbelow(True)
plt.savefig("indegree_cs_categories.png", bbox_inches="tight", dpi=150)
plt.show()
''')

sanity = [
    new_markdown_cell(
        "### Sanity check: is `'cs.'` the right prefix?\n"
        "List every category that starts with just `'cs'` (no dot). If something like a non-CS "
        "category also started with `cs`, it would show up here with a `False` in the `isCsDot` column."
    ),
    new_code_cell('''query_string = \'\'\'
MATCH (c:Category)
WHERE c.category STARTS WITH 'cs'
RETURN c.category AS category, c.category STARTS WITH 'cs.' AS isCsDot
ORDER BY category
\'\'\'
prefix_df = pd.DataFrame([dict(_) for _ in conn.query(query_string)])
print(f"{len(prefix_df)} categories start with 'cs'; {(~prefix_df.isCsDot).sum()} of them do NOT start with 'cs.'")
print(", ".join(prefix_df.category))
'''),
]

cells[22].source = '''# Write an aggregate query to count all papers
# https://neo4j.com/docs/cypher-manual/current/functions/aggregating/

# count(p) is an aggregating function: it collapses all matched Paper rows into one number
query_string = \'\'\'
MATCH (p:Paper)
RETURN count(p) AS totalPapers
\'\'\'
total_papers = conn.query(query_string)[0]["totalPapers"]
print(f"Total papers: {total_papers:,}")
'''

cells[23].source = '''# Write a query to sum or count the total number of papers in CS type categories

# (A) OFFICIAL ANSWER - unique papers that are in at least one CS category.
#     A paper cross-listed in cs.AI and cs.LG matches twice, but count(DISTINCT p) counts it once.
query_unique = \'\'\'
MATCH (p:Paper)-[:IN_CATEGORY]->(c:Category)
WHERE c.category STARTS WITH 'cs.'
RETURN count(DISTINCT p) AS uniqueCsPapers
\'\'\'

# (B) Paper-category memberships - a paper in cs.AI and cs.LG counts twice.
query_memberships = \'\'\'
MATCH (p:Paper)-[:IN_CATEGORY]->(c:Category)
WHERE c.category STARTS WITH 'cs.'
RETURN count(p) AS csCategoryMemberships
\'\'\'

# (C) Same as (B) but via APOC: add up the inDegree of every CS category with sum()
query_sum_degree = \'\'\'
MATCH (c:Category)
WHERE c.category STARTS WITH 'cs.'
RETURN sum(apoc.node.degree(c, "<IN_CATEGORY")) AS sumCsInDegree
\'\'\'

unique_cs = conn.query(query_unique)[0]["uniqueCsPapers"]
memberships_cs = conn.query(query_memberships)[0]["csCategoryMemberships"]
sum_degree_cs = conn.query(query_sum_degree)[0]["sumCsInDegree"]

print(f"(A) Unique CS papers (OFFICIAL):          {unique_cs:,}")
print(f"(B) CS paper-category memberships:        {memberships_cs:,}")
print(f"(C) sum of CS category inDegrees (APOC):  {sum_degree_cs:,}")
print(f"(B) == (C)? {memberships_cs == sum_degree_cs}")
print(f"Difference (B) - (A): {memberships_cs - unique_cs:,} extra counts from papers cross-listed in 2+ CS categories")
'''

# How many CS papers are in more than one CS category? (backs up the explanation)
crosslist = new_code_cell('''# How many CS categories is each CS paper in? (explains the gap between A and B)
query_string = \'\'\'
MATCH (p:Paper)-[:IN_CATEGORY]->(c:Category)
WHERE c.category STARTS WITH 'cs.'
WITH p, count(c) AS numCsCategories
RETURN numCsCategories, count(p) AS papers
ORDER BY numCsCategories
\'\'\'
crosslist_df = pd.DataFrame([dict(_) for _ in conn.query(query_string)])
crosslist_df["contributes_to_B"] = crosslist_df.numCsCategories * crosslist_df.papers
print(crosslist_df.to_string(index=False))
print("sum(papers) =", crosslist_df.papers.sum(), " sum(contributes_to_B) =", crosslist_df.contributes_to_B.sum())
''')

explain = new_markdown_cell('''### Unique papers vs. per-category counts

- **(A) `count(DISTINCT p)` is the official answer**: the number of *unique papers* that appear in at least one CS category.
- **(B) `count(p)`** counts *rows* of the pattern `(p)-[:IN_CATEGORY]->(c)`. The pattern produces one row per paper-category relationship, so a paper cross-listed in `cs.AI` **and** `cs.LG` is counted **twice**. This number is really "CS category memberships," not papers.
- **(C) `sum(apoc.node.degree(...))`** adds up the bar heights from the CS bar chart. Every bar counts each of its papers, so cross-listed papers are again counted once per CS category, and (C) equals (B).
- The difference (B) − (A) is exactly the extra counts from papers in 2+ CS categories (see the table above: Σ papers = A, Σ numCsCategories × papers = B).
- Why Cypher behaves this way: `MATCH` returns **every** way the pattern can match, and aggregation runs over those rows. `DISTINCT` deduplicates before counting.
''')

fun = [
    new_markdown_cell("# Something fun\n"
                      "### 1. Which pairs of CS categories show up together on the same paper most often?"),
    new_code_cell('''# Two IN_CATEGORY relationships from the same paper p to two different CS categories.
# c1.category < c2.category keeps each unordered pair once (no (A,B)+(B,A) double counting, no (A,A)).
query_string = \'\'\'
MATCH (c1:Category)<-[:IN_CATEGORY]-(p:Paper)-[:IN_CATEGORY]->(c2:Category)
WHERE c1.category STARTS WITH 'cs.' AND c2.category STARTS WITH 'cs.'
  AND c1.category < c2.category
RETURN c1.category AS category1, c2.category AS category2, count(p) AS sharedPapers
ORDER BY sharedPapers DESC LIMIT 10
\'\'\'
cs_pairs_df = pd.DataFrame([dict(_) for _ in conn.query(query_string)])
cs_pairs_df.to_csv("fun_cs_category_pairs.csv", index=False)
cs_pairs_df
'''),
    new_markdown_cell("### 2. Who are the most prolific authors, and how many distinct co-authors do they have?"),
    new_code_cell('''# Out-degree of AUTHORED = number of papers; then walk Author->Paper<-Author to collect co-authors.
query_string = \'\'\'
MATCH (a:Author)-[:AUTHORED]->(p:Paper)
WITH a, count(p) AS papers
ORDER BY papers DESC LIMIT 10
OPTIONAL MATCH (a)-[:AUTHORED]->(:Paper)<-[:AUTHORED]-(co:Author)
WHERE co <> a
RETURN a.name AS author, papers, count(DISTINCT co) AS distinctCoauthors
ORDER BY papers DESC, distinctCoauthors DESC
\'\'\'
prolific_df = pd.DataFrame([dict(_) for _ in conn.query(query_string)])
prolific_df.to_csv("fun_prolific_authors.csv", index=False)
prolific_df
'''),
]

fun.insert(2, new_markdown_cell(
    "**What this shows:** the strongest CS pairing is `cs.DM` (discrete math) + `cs.DS` (data structures & algorithms), "
    "and the top three pairs are all theory (DM / DS / CC = computational complexity). `cs.AI` + `cs.LG` is only 8th. "
    "That makes sense because this sample is arXiv papers from **April 2007 to December 2008** (ids `0704.*`-`0812.*`), "
    "years before deep learning made `cs.LG` the biggest category on arXiv."))
fun.append(new_markdown_cell(
    "**What this shows:** \"most papers\" is not the same as \"most collaborators\". `B. Aubert` has 133 papers but only "
    "5 distinct co-authors, because huge particle-physics collaborations (BaBar) list papers as *\"B. Aubert et al.\"* "
    "or under a collaboration name. N. Gehrels (NASA Swift/Fermi) has 63 papers but 541 co-authors. Some \"authors\" "
    "are not even people (`The BABAR Collaboration`, `D0 Collaboration`), a data-cleaning issue a real project would fix."))
fun.append(new_markdown_cell(
    "**Bonus observation:** `cs.IT` is by far the biggest CS bar (1,487 papers) because every `cs.IT` paper is also "
    "tagged `math.IT`; arXiv treats them as aliases of the same Information Theory archive. Likewise `math.MP` and "
    "`math-ph` have identical counts (4,334) in the top-20 chart."))

# Assemble: cells 0..21, chart, sanity, 22, 23, crosslist, explain, fun
nb.cells = cells[:22] + [cs_chart] + sanity + [cells[22], cells[23], crosslist, explain] + fun
for c in nb.cells:
    if c.cell_type == "code":
        c.outputs, c.execution_count = [], None
nb.metadata["kernelspec"] = {"name": "neo4j-cs452", "display_name": "Python (neo4j-cs452)", "language": "python"}
nbformat.write(nb, ROOT / "neo4j_lab.ipynb")
print("wrote neo4j_lab.ipynb with", len(nb.cells), "cells")
