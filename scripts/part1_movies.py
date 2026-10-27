"""Part 1: load the Movies graph and find the Bacon path to Nora Ephron."""
import json
import sys

from db import ROOT, get_driver, run

driver = get_driver()

# Load the movies dataset only if it isn't there yet (the script uses CREATE, so re-running would duplicate).
if run(driver, "MATCH (m:Movie) RETURN count(m) AS n")[0]["n"] == 0:
    script = (ROOT / "movies.cypher").read_text()
    # The file is one big CREATE statement (plus possibly trailing statements separated by ';').
    for stmt in [s.strip() for s in script.split(";") if s.strip()]:
        if stmt.startswith("//") and "\n" not in stmt:
            continue
        driver.execute_query(stmt)

print("Node counts by label:")
for r in run(driver, "MATCH (n:Person|Movie) RETURN labels(n) AS labels, count(*) AS count"):
    print("  ", r)

print("\nKeanu Reeves movies:")
for r in run(driver, 'MATCH (keanu:Person {name: "Keanu Reeves"})-[:ACTED_IN]->(m) '
                     'RETURN m.title AS title, m.released AS year ORDER BY year'):
    print("  ", r)

# shortestPath over any relationship type, in either direction, any length
records, _, _ = driver.execute_query('''
MATCH p = shortestPath(
  (bacon:Person {name: "Kevin Bacon"})-[*]-(nora:Person {name: "Nora Ephron"})
)
RETURN p
''')
path = records[0]["p"]

def label(node):
    return node.get("name") or node.get("title")

parts = [f"({label(path.nodes[0])})"]
for rel, nxt in zip(path.relationships, path.nodes[1:]):
    # show the true direction of each relationship
    if rel.start_node.element_id == nxt.element_id:
        parts.append(f"<-[:{rel.type}]-({label(nxt)})")
    else:
        parts.append(f"-[:{rel.type}]->({label(nxt)})")
text = "".join(parts)
print("\nBacon path:", text)
print("Path length (relationships):", len(path.relationships))

out = {
    "nodes": [{"name": label(n), "label": list(n.labels)[0]} for n in path.nodes],
    "rels": [{"type": r.type,
              "start": label(r.start_node), "end": label(r.end_node)} for r in path.relationships],
    "text": text,
    "length": len(path.relationships),
}
(ROOT / "output").mkdir(exist_ok=True)
(ROOT / "output" / "bacon_path.json").write_text(json.dumps(out, indent=2))
driver.close()
