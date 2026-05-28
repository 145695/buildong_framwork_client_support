"""
Lightweight Knowledge Graph Store (no external DB/deps)

Purpose:
- Store (subject, predicate, object) triples extracted from policy text chunks
- Keep traceability back to the source chunk + filename for grounding
- Support simple keyword-based lookup + 1-hop neighborhood expansion

This is intentionally minimal to avoid adding new infrastructure dependencies.
You can swap this later with Neo4j / RDFLib / etc. behind the same interface.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Set, Tuple, Any
import re


def _normalize(text: str) -> str:
    text = (text or "").strip().lower()
    text = re.sub(r"\s+", " ", text)
    return text


def _tokenize(text: str) -> List[str]:
    # Keep fairly permissive tokens for FR/EN, drop very short ones.
    tokens = re.findall(r"[a-zA-ZÀ-ÿ0-9_]{3,}", (text or "").lower())
    # de-dup while preserving order
    seen: Set[str] = set()
    out: List[str] = []
    for t in tokens:
        if t not in seen:
            seen.add(t)
            out.append(t)
    return out


@dataclass
class GraphEvidence:
    filename: str
    chunk_id: str
    snippet: str


@dataclass
class GraphTriple:
    subject: str
    predicate: str
    object: str
    confidence: float = 0.6
    evidence: Optional[GraphEvidence] = None


class GraphStore:
    """
    A small in-memory graph:
    - Nodes are strings (entity labels)
    - Edges are triples with optional evidence

    Indexes:
    - token_index maps token -> entities that contain the token
    - adjacency maps entity -> outgoing triples
    - reverse_adjacency maps entity -> incoming triples
    """

    def __init__(self) -> None:
        self.entities: Set[str] = set()
        self.adjacency: Dict[str, List[GraphTriple]] = {}
        self.reverse_adjacency: Dict[str, List[GraphTriple]] = {}
        self.token_index: Dict[str, Set[str]] = {}

    def add_triple(self, triple: GraphTriple) -> None:
        s = (triple.subject or "").strip()
        p = (triple.predicate or "").strip()
        o = (triple.object or "").strip()
        if not s or not p or not o:
            return

        self.entities.add(s)
        self.entities.add(o)

        self.adjacency.setdefault(s, []).append(triple)
        self.reverse_adjacency.setdefault(o, []).append(triple)

        # Index subject + object tokens for retrieval.
        for ent in (s, o):
            for tok in _tokenize(ent):
                self.token_index.setdefault(tok, set()).add(ent)

    def add_triples(self, triples: List[GraphTriple]) -> None:
        for t in triples:
            self.add_triple(t)

    def to_dict(self) -> Dict[str, Any]:
        # Convert dataclasses to serializable form
        triples_out: List[Dict[str, Any]] = []
        for s, out_edges in self.adjacency.items():
            for t in out_edges:
                d = asdict(t)
                triples_out.append(d)
        return {"triples": triples_out}

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "GraphStore":
        g = cls()
        for item in (data or {}).get("triples", []):
            ev = item.get("evidence")
            evidence = None
            if isinstance(ev, dict):
                evidence = GraphEvidence(**ev)
            t = GraphTriple(
                subject=item.get("subject", ""),
                predicate=item.get("predicate", ""),
                object=item.get("object", ""),
                confidence=float(item.get("confidence", 0.6) or 0.6),
                evidence=evidence,
            )
            g.add_triple(t)
        return g

    def find_seed_entities(self, query: str, limit: int = 20) -> List[str]:
        tokens = _tokenize(query)
        if not tokens:
            return []

        scores: Dict[str, int] = {}
        for tok in tokens:
            for ent in self.token_index.get(tok, set()):
                scores[ent] = scores.get(ent, 0) + 1

        ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
        return [ent for ent, _ in ranked[:limit]]

    def neighborhood_triples(
        self,
        seed_entities: List[str],
        hops: int = 1,
        max_triples: int = 20,
        min_confidence: float = 0.45,
    ) -> List[GraphTriple]:
        """
        Collect triples in the local neighborhood of seeds.
        For MVP: only 1-hop expansion (outgoing + incoming).
        """
        if not seed_entities:
            return []

        collected: List[GraphTriple] = []
        seen: Set[Tuple[str, str, str]] = set()

        frontier: Set[str] = set(seed_entities)
        visited: Set[str] = set()

        for _ in range(max(1, hops)):
            next_frontier: Set[str] = set()
            for ent in list(frontier):
                if ent in visited:
                    continue
                visited.add(ent)

                for t in self.adjacency.get(ent, []):
                    if t.confidence < min_confidence:
                        continue
                    key = (_normalize(t.subject), _normalize(t.predicate), _normalize(t.object))
                    if key not in seen:
                        seen.add(key)
                        collected.append(t)
                        next_frontier.add(t.object)
                        if len(collected) >= max_triples:
                            return collected

                for t in self.reverse_adjacency.get(ent, []):
                    if t.confidence < min_confidence:
                        continue
                    key = (_normalize(t.subject), _normalize(t.predicate), _normalize(t.object))
                    if key not in seen:
                        seen.add(key)
                        collected.append(t)
                        next_frontier.add(t.subject)
                        if len(collected) >= max_triples:
                            return collected

            frontier = next_frontier

        return collected[:max_triples]

