"""Shared helper: connect to Neo4j using credentials from .env."""
import os
import time
from pathlib import Path

from dotenv import load_dotenv
from neo4j import GraphDatabase

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

URI = os.getenv("NEO4J_URI")
USER = os.getenv("NEO4J_USER")
PASSWORD = os.getenv("NEO4J_PASSWORD")


def get_driver(wait_seconds=120):
    """Return a driver, retrying until the server accepts connections."""
    driver = GraphDatabase.driver(URI, auth=(USER, PASSWORD))
    deadline = time.time() + wait_seconds
    while True:
        try:
            driver.verify_connectivity()
            return driver
        except Exception:
            if time.time() > deadline:
                raise
            time.sleep(2)


def run(driver, query, **params):
    records, _, _ = driver.execute_query(query, params)
    return [r.data() for r in records]


if __name__ == "__main__":
    d = get_driver()
    print("Connected to", URI)
    print("APOC version:", run(d, "RETURN apoc.version() AS v")[0]["v"])
    d.close()
