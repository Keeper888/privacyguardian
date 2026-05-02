"""One-shot: create the Atlas Vector Search index for guardian_agent.sensitivity_memory.

Usage:
    python -m agent.memory.setup_index

Requires MONGODB_URI in agent/.env. Cluster must be M0 free tier or higher
(Atlas Vector Search is supported on M0).
"""

import os
import sys
import time
from pathlib import Path

from dotenv import load_dotenv
from pymongo import MongoClient
from pymongo.operations import SearchIndexModel

load_dotenv(Path(__file__).resolve().parent.parent / ".env")


def main() -> int:
    uri = os.environ["MONGODB_URI"]
    db_name = os.environ.get("MONGODB_DB", "guardian_agent")
    coll_name = os.environ.get("MONGODB_COLLECTION", "sensitivity_memory")
    index_name = os.environ.get("MONGODB_VECTOR_INDEX", "sensitivity_vector_idx")
    dim = int(os.environ.get("EMBEDDING_DIM", "1536"))

    client = MongoClient(uri)
    coll = client[db_name][coll_name]

    if coll.estimated_document_count() == 0:
        coll.insert_one({"_bootstrap": True, "embedding": [0.0] * dim})
        coll.delete_many({"_bootstrap": True})

    existing = {idx["name"] for idx in coll.list_search_indexes()}
    if index_name in existing:
        print(f"✓ index '{index_name}' already exists on {db_name}.{coll_name}")
        return 0

    model = SearchIndexModel(
        definition={
            "fields": [
                {
                    "type": "vector",
                    "path": "embedding",
                    "numDimensions": dim,
                    "similarity": "cosine",
                }
            ]
        },
        name=index_name,
        type="vectorSearch",
    )

    print(f"creating vector index '{index_name}' on {db_name}.{coll_name}…")
    coll.create_search_index(model=model)

    deadline = time.time() + 180
    while time.time() < deadline:
        for idx in coll.list_search_indexes(name=index_name):
            if idx.get("queryable"):
                print(f"✓ index '{index_name}' ready ({dim}-dim, cosine)")
                return 0
        time.sleep(3)

    print("⚠ index created but not yet queryable after 3min — check Atlas UI")
    return 1


if __name__ == "__main__":
    sys.exit(main())
