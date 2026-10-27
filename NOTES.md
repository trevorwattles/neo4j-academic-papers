# NOTES: assumptions and decisions made during this run

Date: 2026-10-27

## Database
- No `.env` existed, so Neo4j runs **locally in Docker** (`neo4j:5`, container `neo4j-cs452`) with the APOC plugin
  (APOC 5.26.32 verified with `RETURN apoc.version()`).
- A random 32-hex-character password was generated with `openssl rand -hex 16` and written **only** to `.env`
  (`chmod 600`, gitignored). The notebook and scripts read it with `python-dotenv`.
- Added `NEO4J_server_memory_heap_max__size=2G` to the `docker run` so the 100k-paper import has headroom.
  The default `batch_size` values (10,000 authors / 5,000 papers) worked fine; the whole import took ~7 s, so no reduction was needed.
- The Movies graph and the ArXiv graph live in the **same** database. That's fine because they use different labels
  (`Person`/`Movie` vs `Paper`/`Author`/`Category`) and are not connected, so the Bacon `shortestPath` can't wander into ArXiv data.

## Part 1: Movies
- Loaded `movies.cypher` from `neo4j-graph-examples/movies`. The current version of that script uses `MERGE` + constraints
  (not one giant `CREATE`), so it is idempotent. Result: 38 `Movie` + 133 `Person` = **171 nodes**.
- Bacon path: `(Kevin Bacon)-[:ACTED_IN]->(Apollo 13)<-[:ACTED_IN]-(Tom Hanks)-[:ACTED_IN]->(You've Got Mail)<-[:DIRECTED]-(Nora Ephron)`, length 4.
  Note `shortestPath` returns *one* shortest path; other length-4 paths may exist (e.g. via *Sleepless in Seattle*).
- The screenshot is from the **real Neo4j Browser** (automated with Playwright/headless Chromium, `scripts/screenshot_bacon.py`).
  First attempt showed an autocomplete dropdown and a "Work in tabs" onboarding popup over the graph; fixed by pressing
  Escape, dismissing the tour, and cropping to the result frame. The networkx fallback was not needed.

## Part 2: Notebook changes (all made by `scripts/edit_notebook.py`, starting from the untouched original)
- Credentials cell loads `.env` (variable names `bolt_uri`, `user`, `pwd` and the `ValueError` check unchanged).
- `!pip3 install neo4j-driver` → `%pip install -q neo4j python-dotenv` (`neo4j-driver` is the deprecated package name).
- Download cell skips if `metadata.csv` already exists and falls back to the `media.githubusercontent.com` LFS URL if
  the file is a tiny LFS pointer. (This run, the `github.com/.../raw/...` URL returned the real 131 MB file.)
- **`pd.read_csv(..., dtype={"id": str})`**: by default pandas parses arXiv ids like `0809.1640` as the float `809.164`.
  No ids collided in this dataset (100,000 unique either way), so **counts are unaffected**, but ~10% of ids were
  visibly mangled. Keeping them as strings stores the real arXiv id on each `Paper` node.
- Bar chart cell now also `plt.savefig("indegree_by_category.png", bbox_inches="tight", dpi=150)`.
- Filled the three `# YOUR CODE HERE` cells, added a CS bar chart, a `'cs'` prefix sanity check, a cross-listing breakdown,
  an explanation cell, and a "Something fun" section.
- Executed headless with `jupyter nbconvert --execute --inplace` using a registered kernel `neo4j-cs452` (the project venv).
- Grep confirmed the password value appears in **0** committed files.

## Answers
- Total papers: **100,000**
- **Official:** unique papers in ≥1 CS category, `count(DISTINCT p)` = **5,812**
- Paper-category memberships, `count(p)` = **7,891** (= `sum(apoc.node.degree(c,"<IN_CATEGORY"))` over CS categories)
- Difference 2,079 comes from 1,792 papers in 2+ CS categories.
- The `'cs.'` prefix is correct: all 40 categories starting with `cs` also start with `cs.`.

## Interpretation choices
- "Total number of papers from all CS categories" is interpreted as unique papers (`DISTINCT`) for the official answer,
  because a paper is one paper no matter how many CS categories it is cross-listed in.
- "Something fun" in the PDF uses the CS category co-occurrence query; the notebook also includes a prolific-authors query.
