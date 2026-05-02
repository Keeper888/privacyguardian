import os
import time
from dataclasses import dataclass, asdict
from typing import List, Optional

from pymongo import MongoClient
from pymongo.collection import Collection

from .embeddings import embed


@dataclass
class SensitivityRule:
    label: str
    context: str
    example: str
    reason: str
    embedding: List[float]
    created_at: float


@dataclass
class Match:
    label: str
    example: str
    reason: str
    score: float


class VectorStore:
    def __init__(self):
        uri = os.environ["MONGODB_URI"]
        db_name = os.environ.get("MONGODB_DB", "guardian_agent")
        coll_name = os.environ.get("MONGODB_COLLECTION", "sensitivity_memory")
        self.index_name = os.environ.get("MONGODB_VECTOR_INDEX", "sensitivity_vector_idx")
        self.threshold = float(os.environ.get("SEMANTIC_THRESHOLD", "0.82"))

        self.client = MongoClient(uri)
        self.collection: Collection = self.client[db_name][coll_name]

    def remember(self, label: str, context: str, example: str, reason: str) -> str:
        rule = SensitivityRule(
            label=label,
            context=context,
            example=example,
            reason=reason,
            embedding=embed(f"{example}. Context: {context}. Reason: {reason}"),
            created_at=time.time(),
        )
        result = self.collection.insert_one(asdict(rule))
        return str(result.inserted_id)

    def search(self, text: str, k: int = 5) -> List[Match]:
        query_vec = embed(text)
        pipeline = [
            {
                "$vectorSearch": {
                    "index": self.index_name,
                    "path": "embedding",
                    "queryVector": query_vec,
                    "numCandidates": 50,
                    "limit": k,
                }
            },
            {
                "$project": {
                    "_id": 0,
                    "label": 1,
                    "example": 1,
                    "reason": 1,
                    "score": {"$meta": "vectorSearchScore"},
                }
            },
        ]
        results = list(self.collection.aggregate(pipeline))
        return [
            Match(
                label=r["label"],
                example=r["example"],
                reason=r["reason"],
                score=r["score"],
            )
            for r in results
            if r["score"] >= self.threshold
        ]

    def count(self) -> int:
        return self.collection.count_documents({})

    def clear(self):
        self.collection.delete_many({})
