# Learning Notes: Neo4j Academic Papers

> Study material to help you decide what to put in **your own handwritten** learning log.
> This is *not* the log, so pick the ideas that clicked for you and write them in your own words.

---

## 1. Low-level concepts (Cypher and Neo4j mechanics)

### The property graph model
| Piece | Example from this project | Relational analogy |
|---|---|---|
| **Node** | one paper, one author | a row |
| **Label** | `:Paper`, `:Author`, `:Category`, `:Person`, `:Movie` | the table the row lives in |
| **Property** | `p.id`, `p.title`, `c.category` | a column value |
| **Relationship** | `(a)-[:AUTHORED]->(p)`, `(p)-[:IN_CATEGORY]->(c)` | a row in a join table (but stored as a direct pointer) |

Relationships always have **one type** and **a direction**, and they can carry properties too
(e.g. `ACTED_IN {roles: [...]}` in the Movies graph).

### `MATCH`
It's pattern matching on the graph and is the `SELECT ... FROM ... JOIN` of Cypher. You draw the shape with ASCII art:
`(p:Paper)-[:IN_CATEGORY]->(c:Category)`. **Every** way the pattern can match becomes a row.
That one fact explains the whole `count(p)` vs `count(DISTINCT p)` question (below).

### `MERGE` vs `CREATE`
- `CREATE` always makes a new node or relationship, even if an identical one exists, which gives duplicates.
- `MERGE` means "match it if it exists, otherwise create it." It's an *upsert*.
- `MERGE (p:Paper {id: row.id}) ON CREATE SET p.title = row.title` sets the title only the first time.
  (There's also `ON MATCH SET`.)
- Gotcha: `MERGE` matches the **whole** pattern you give it. `MERGE (a)-[:AUTHORED]->(p)` is safe because `a` and `p`
  were already bound. But `MERGE (:Author {name:'X'})-[:AUTHORED]->(:Paper {id:'Y'})` would create *new* nodes
  if the full path didn't already exist.

### `UNWIND $rows AS row` (parameters + batching)
- `$rows` is a **query parameter**: Python sends a list of dicts (`df.to_dict('records')`) separately from the query text.
- `UNWIND` turns that list into one row per element, so a single query inserts thousands of nodes.
- Parameters (not string-formatting values into the query) mean: no Cypher injection, and Neo4j can cache the query plan.

### Uniqueness constraints = indexes too
`CREATE CONSTRAINT papers IF NOT EXISTS FOR (p:Paper) REQUIRE p.id IS UNIQUE`
- Guarantees no two `Paper` nodes share an `id`.
- **Automatically creates an index** on `:Paper(id)`. That's why every `MERGE (p:Paper {id: ...})` and
  `MATCH (c:Category {category: ...})` is a fast index lookup instead of scanning every node.
  Without constraints the import would get slower and slower as the graph grew.

### `shortestPath` and variable-length `[*]`
```cypher
MATCH p = shortestPath((bacon:Person {name:"Kevin Bacon"})-[*]-(nora:Person {name:"Nora Ephron"}))
RETURN p
```
- `[*]` = any relationship type, any number of hops. `[*1..6]` would bound it, and `[:ACTED_IN*]` would restrict the type.
- No arrow (`-[*]-`) = ignore direction. Bacon *acted in* Apollo 13 and Tom Hanks *acted in* Apollo 13, so both arrows
  point at the movie. A directed pattern couldn't walk "backwards" from the movie to Tom Hanks.
- `p = ...` binds the whole **path** (nodes + relationships) to a variable.
- Returns **one** shortest path (BFS). `allShortestPaths` returns all of them.
- Neo4j Browser warned: *"The provided pattern is unbounded."* On a huge graph, an unbounded search can blow up.

### `WITH` and `WITH DISTINCT` in `add_papers`
```cypher
UNWIND $rows as row
MERGE (p:Paper {id:row.id}) ON CREATE SET p.title = row.title
WITH row, p
UNWIND row.category_list AS category_name      // 1 row  -> k rows (one per category)
MATCH (c:Category {category: category_name})
MERGE (p)-[:IN_CATEGORY]->(c)
WITH distinct row, p                           // k rows -> back to 1 row per paper
UNWIND row.cleaned_authors_list AS author      // 1 row  -> m rows (one per author)
MATCH (a:Author {name: author})
MERGE (a)-[:AUTHORED]->(p)
```
- `WITH` is a pipe between query parts, like a sub-`SELECT`. Only the variables you list carry forward.
- After the first `UNWIND`, a paper with 3 categories is **3 rows**. Without `WITH DISTINCT`, the author `UNWIND`
  would run 3 times (3 × m rows, with `MERGE` doing redundant work 3 times). `DISTINCT` collapses it back to one row
  per paper. That's what the comment "reduce cardinality" means.

### `count(DISTINCT p)` vs `count(p)`
- `MATCH (p:Paper)-[:IN_CATEGORY]->(c:Category) WHERE c.category STARTS WITH 'cs.'` gives one row **per relationship**.
- `count(p)` = **7,891** (memberships: a paper in cs.AI + cs.LG counts twice)
- `count(DISTINCT p)` = **5,812** (unique papers, the official answer)
- `sum(apoc.node.degree(c, "<IN_CATEGORY"))` over CS categories = 7,891, the same as `count(p)`, because it adds up the bars.
- Proof from the data: 4,020 papers have 1 CS category, 1,551 have 2, 205 have 3 … Σ papers = 5,812 and
  Σ (papers × categories) = 7,891.

### `STARTS WITH`
A string predicate: `c.category STARTS WITH 'cs.'`. It can use an index (a prefix search).
The sanity check showed all 40 categories that start with `cs` also start with `cs.`, so the dot is correct but not strictly needed here.
(Watch out in general: a prefix like `'math'` would also match `math-ph`, which is a physics archive alias!)

### APOC: `apoc.node.degree(c, "<IN_CATEGORY")`
- APOC = "Awesome Procedures On Cypher," Neo4j's official library of extra functions and procedures, installed as a plugin.
- `apoc.node.degree(node, "<TYPE")` returns how many `TYPE` relationships point **into** the node (`<`).
  `"TYPE>"` = outgoing, `"TYPE"` = both. Neo4j stores degree counts per node, so this is nearly free.
- It replaced the tutorial's deprecated `size((c)<-[:IN_CATEGORY]-())` syntax. Neo4j 5 removed pattern expressions
  inside `size()`. The modern built-in alternative is `COUNT { (c)<-[:IN_CATEGORY]-() }`.

### Batching writes
- Each `conn.query(...)` call = one **transaction**. All of a transaction's changes are held in memory (heap) until commit.
- If you send 100k papers in one transaction, you risk `OutOfMemory` or a transaction timeout. If you send 1 per
  transaction, you pay 100k network round-trips and commits.
- Batches of 5,000 to 10,000 balance the two. This run: 100k papers in 20 batches in ~7 seconds.

---

## 2. High-level concepts

### When does a graph DB beat a relational DB?
When the question is about **connections of unknown or variable depth**: shortest paths, "friends of friends of friends,"
recommendation ("people who co-authored with people who…"), fraud rings, network routing.
- In SQL each hop is another `JOIN`, and an unknown number of hops needs a recursive CTE.
- In Neo4j each hop is following a stored pointer ("index-free adjacency"). The cost depends on how much of the graph
  you touch, **not** on the total table size.

When is relational better? Big aggregations over flat data, reporting, strict schemas, transactions across many
unrelated rows, and mature tooling. Counting papers per category is easy in either.

### This data as relational tables
```
papers(id PK, title)
authors(name PK)                      -- in real life: an author_id surrogate key
categories(category PK)
paper_authors(author_name FK, paper_id FK, PK(author_name, paper_id))      -- AUTHORED
paper_categories(paper_id FK, category FK, PK(paper_id, category))         -- IN_CATEGORY
```
The CS count in SQL:
```sql
SELECT COUNT(DISTINCT paper_id) FROM paper_categories WHERE category LIKE 'cs.%';   -- 5,812
SELECT COUNT(*)                 FROM paper_categories WHERE category LIKE 'cs.%';   -- 7,891
```

### The Bacon path in SQL (Movies as tables)
`people(id, name)`, `movies(id, title)`, `roles(person_id, movie_id, type)` where type ∈ ACTED_IN, DIRECTED, …
```sql
WITH RECURSIVE reach(person_id, depth, path) AS (
    SELECT id, 0, CAST(name AS TEXT) FROM people WHERE name = 'Kevin Bacon'
  UNION ALL
    SELECT r2.person_id, reach.depth + 1, reach.path || ' -> ' || m.title || ' -> ' || p2.name
    FROM reach
    JOIN roles r1  ON r1.person_id = reach.person_id
    JOIN movies m  ON m.id = r1.movie_id
    JOIN roles r2  ON r2.movie_id = r1.movie_id AND r2.person_id <> r1.person_id
    JOIN people p2 ON p2.id = r2.person_id
    WHERE reach.depth < 6                         -- must bound it or it can loop forever
)
SELECT path, depth FROM reach
JOIN people p ON p.id = reach.person_id
WHERE p.name = 'Nora Ephron'
ORDER BY depth LIMIT 1;
```
Compare that to the 3-line Cypher query. SQL also needs cycle protection, and it explores *every* path up to depth 6
before picking the shortest, while `shortestPath` does a breadth-first search that stops at the first hit.

### Work in the DB vs in pandas
- **In the DB** (Cypher `count`, `WHERE`, `apoc.node.degree`): it only ships the answer over the network, uses indexes,
  works when the data doesn't fit in RAM, and is the single source of truth.
- **In pandas**: good for cleaning *before* loading (`ast.literal_eval` on authors, splitting categories), plotting,
  and quick exploration. But you'd have to pull 100k rows (or millions) across the wire first.
- This project does both: pandas for **ETL** (extract-transform-load), Neo4j for **querying relationships**.

---

## 3. Secrets: why `.env` + `.gitignore`
- The notebook originally had `pwd = ""` to fill in by hand. If you type the real password there and push the `.ipynb` to
  GitHub (or submit it), the password is public forever. Git history keeps it even if you delete it later, and bots scan
  GitHub for credentials within minutes.
- `.env` holds `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD`. `python-dotenv` loads it into environment variables.
  `.gitignore` lists `.env` so git never tracks it.
- **What could someone do with the Neo4j password?** Read all the data. Run `MATCH (n) DETACH DELETE n` and wipe it.
  Modify data quietly. Use APOC procedures (some can load URLs or files) to pivot further. And reuse the password
  elsewhere if it was reused. With a Sandbox or Aura instance, anyone on the internet can reach the Bolt port, so the
  password is the *only* lock.
- This run: the password was random (`openssl rand -hex 16`) and a grep confirmed it appears in 0 committed files.

---

## 4. Surprises and bugs hit during this run (aha-moment candidates)
1. **arXiv ids turned into floats.** `pd.read_csv` parsed `0809.1640` as `809.164`, dropping the leading zero and the
   trailing zero. It happened to cause no collisions here (100,000 unique either way), but it's a classic silent data
   bug. Fixed with `dtype={"id": str}`. *Lesson: identifiers are strings, even when they look like numbers
   (zip codes, phone numbers, arXiv ids).*
2. **`count(p)` ≠ number of papers.** The same `MATCH` gives 7,891 or 5,812 depending on one `DISTINCT`, because `MATCH`
   returns a row for every relationship. 1,792 CS papers are cross-listed in 2+ CS categories.
3. **cs.IT is huge (1,487) because it's an alias.** Every cs.IT paper is also tagged math.IT, and `math.MP`/`math-ph`
   have identical counts too. The data has duplicated meaning baked in.
4. **"Most papers" ≠ "most collaborators."** B. Aubert has 133 papers but only 5 co-authors, because BaBar physics papers
   list "B. Aubert et al." N. Gehrels has 63 papers but 541 co-authors. And `The BABAR Collaboration` is an "Author"
   node even though it isn't a person.
5. **The data is from 2007 to 2008** (ids `0704.*`–`0812.*`), so cs.AI + cs.LG is only the 8th most common CS pairing.
   Theory pairs (discrete math + algorithms + complexity) dominate.
6. **Docker wasn't running.** The daemon had to be started (`open -a Docker`) before `docker run`.
   The Neo4j Browser also has onboarding popups and autocomplete that covered the graph in the first automated
   screenshot; I pressed Escape, dismissed the tour, and cropped to the result frame.
7. **Deprecated names everywhere.** The package is `neo4j`, not `neo4j-driver`. `size((c)<-[:REL]-())` doesn't work in
   Neo4j 5, which is why the class uses `apoc.node.degree` (or `COUNT { ... }`).

---

## 5. Quiz yourself

**Q1.** What's the difference between `MERGE (a:Author {name: $n})` and `CREATE (a:Author {name: $n})` if that author already exists?
<details><summary>Answer</summary>MERGE finds the existing node and binds it; CREATE makes a duplicate node (or fails if a uniqueness constraint exists on <code>:Author(name)</code>).</details>

**Q2.** Why does `count(p)` return 7,891 but `count(DISTINCT p)` return 5,812 for the same CS `MATCH`?
<details><summary>Answer</summary>MATCH returns one row per (paper, CS category) relationship. Papers cross-listed in multiple CS categories appear in multiple rows; DISTINCT de-duplicates papers before counting.</details>

**Q3.** In `apoc.node.degree(c, "<IN_CATEGORY")`, what does the `<` mean, and what would `"IN_CATEGORY>"` return for a Category node?
<details><summary>Answer</summary><code>&lt;</code> = incoming relationships (papers pointing at the category). <code>IN_CATEGORY&gt;</code> = outgoing, which is 0 for a Category, because the arrows go Paper → Category.</details>

**Q4.** Why did the Bacon-path query use `-[*]-` with no arrowhead?
<details><summary>Answer</summary>Relationships go Person → Movie. Getting from Kevin Bacon to Tom Hanks means going into Apollo 13 and then <i>against</i> the arrow out to Tom Hanks. An undirected pattern lets the path traverse relationships either way.</details>

**Q5.** Name two reasons the import uses batches (`UNWIND $rows` with 5,000 rows) instead of one giant query or one query per row.
<details><summary>Answer</summary>One giant transaction must hold all changes in heap memory until commit (OOM or timeout risk). One row per query means 100k round-trips and commits (very slow). Batches balance memory against overhead, and parameters let Neo4j reuse the cached query plan.</details>
