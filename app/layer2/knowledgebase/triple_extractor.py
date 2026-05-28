"""
Triple extraction utilities for building a lightweight knowledge graph.

Design goals:
- Prefer LLM extraction when available (better coverage / language handling)
- Always provide a deterministic fallback (regex heuristics) so the system
  still works without an API key.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
import json
import re

from .graph_store import GraphEvidence, GraphTriple


def _safe_snippet(text: str, limit: int = 220) -> str:
    text = (text or "").strip()
    text = re.sub(r"\s+", " ", text)
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."


class TripleExtractor:
    def __init__(self, llm: Optional[Any] = None):
        # Expected: an object with async method `ainvoke(prompt: str)`
        self.llm = llm

    def extract_triples_fallback_only(
        self,
        chunk_text: str,
        filename: str,
        chunk_id: str,
        doc_hint: Optional[str] = None,
    ) -> List[GraphTriple]:
        """Synchronous fallback extraction (no LLM calls)."""
        return self._extract_triples_fallback(
            chunk_text=chunk_text,
            filename=filename,
            chunk_id=chunk_id,
            doc_hint=doc_hint,
        )

    async def extract_triples(
        self,
        chunk_text: str,
        filename: str,
        chunk_id: str,
        doc_hint: Optional[str] = None,
        max_triples: int = 8,
    ) -> List[GraphTriple]:
        """
        Extract triples from a chunk.
        - If LLM is available: request JSONL triples
        - Else: use fallback rules (fee/amount/limit/requirements)
        """
        if self.llm and hasattr(self.llm, "ainvoke"):
            triples = await self._extract_triples_llm(
                chunk_text=chunk_text,
                filename=filename,
                chunk_id=chunk_id,
                doc_hint=doc_hint,
                max_triples=max_triples,
            )
            if triples:
                return triples
        return self._extract_triples_fallback(
            chunk_text=chunk_text,
            filename=filename,
            chunk_id=chunk_id,
            doc_hint=doc_hint,
        )

    async def _extract_triples_llm(
        self,
        chunk_text: str,
        filename: str,
        chunk_id: str,
        doc_hint: Optional[str],
        max_triples: int,
    ) -> List[GraphTriple]:
        prompt = f"""You are extracting a small knowledge graph from Algerian banking policy text.

Output ONLY JSON Lines (one JSON object per line), no markdown, no commentary.
Each JSON object must have:
- subject (string)
- predicate (string)  (use concise relation names like REQUIRES, HAS_FEE, HAS_LIMIT, HAS_RATE, HAS_DURATION, APPLIES_TO, DEFINED_AS)
- object (string)
- confidence (number 0..1)

Rules:
- Extract at most {max_triples} triples.
- Focus on factual items a bank agent can answer: requirements, documents, fees, rates, limits, durations, eligibility.
- Keep entities in French if the chunk is French; otherwise keep original language.
- If unsure, lower confidence.

Document: {filename}
Document hint (may be empty): {doc_hint or ""}

Text chunk:
{chunk_text[:1800]}
"""
        try:
            resp = await self.llm.ainvoke(prompt)
            content = getattr(resp, "content", "") or ""
            lines = [ln.strip() for ln in content.splitlines() if ln.strip()]
            out: List[GraphTriple] = []
            for ln in lines[: max_triples * 2]:
                try:
                    obj = json.loads(ln)
                except Exception:
                    continue
                s = (obj.get("subject") or "").strip()
                p = (obj.get("predicate") or "").strip()
                o = (obj.get("object") or "").strip()
                if not s or not p or not o:
                    continue
                conf = obj.get("confidence", 0.6)
                try:
                    conf_f = float(conf)
                except Exception:
                    conf_f = 0.6

                out.append(
                    GraphTriple(
                        subject=s,
                        predicate=p,
                        object=o,
                        confidence=max(0.0, min(1.0, conf_f)),
                        evidence=GraphEvidence(
                            filename=filename,
                            chunk_id=chunk_id,
                            snippet=_safe_snippet(chunk_text),
                        ),
                    )
                )
                if len(out) >= max_triples:
                    break
            return out
        except Exception:
            return []

    def _extract_triples_fallback(
        self,
        chunk_text: str,
        filename: str,
        chunk_id: str,
        doc_hint: Optional[str],
    ) -> List[GraphTriple]:
        """
        Deterministic heuristic extraction.
        This does NOT aim to be complete; it aims to produce a usable MVP graph.
        """
        text = (chunk_text or "").strip()
        if len(text) < 80:
            return []

        evidence = GraphEvidence(filename=filename, chunk_id=chunk_id, snippet=_safe_snippet(text))

        # Use document hint as a default subject to tie facts to a source entity.
        default_subject = (doc_hint or filename.replace(".pdf", "")).strip()
        if not default_subject:
            default_subject = "Document"

        triples: List[GraphTriple] = []

        # 1) Amounts (DA/DZD/dinars)
        for m in re.finditer(r"(\d[\d\s\.,]{1,15})\s*(da|dzd|dinars?)\b", text, flags=re.IGNORECASE):
            amount = (m.group(1) or "").strip()
            unit = (m.group(2) or "").upper()
            obj = f"{amount} {unit}"
            triples.append(
                GraphTriple(
                    subject=default_subject,
                    predicate="HAS_AMOUNT",
                    object=obj,
                    confidence=0.55,
                    evidence=evidence,
                )
            )
            if len(triples) >= 8:
                return triples

        # 2) Rates (%)
        for m in re.finditer(r"(\d{1,2}(?:[.,]\d{1,2})?)\s*%", text):
            rate = (m.group(1) or "").replace(",", ".").strip()
            triples.append(
                GraphTriple(
                    subject=default_subject,
                    predicate="HAS_RATE",
                    object=f"{rate}%",
                    confidence=0.55,
                    evidence=evidence,
                )
            )
            if len(triples) >= 8:
                return triples

        # 3) Durations
        for m in re.finditer(r"\b(\d{1,3})\s*(mois|ans|années)\b", text, flags=re.IGNORECASE):
            n = (m.group(1) or "").strip()
            unit = (m.group(2) or "").lower()
            triples.append(
                GraphTriple(
                    subject=default_subject,
                    predicate="HAS_DURATION",
                    object=f"{n} {unit}",
                    confidence=0.5,
                    evidence=evidence,
                )
            )
            if len(triples) >= 8:
                return triples

        # 4) Requirements / documents (very common patterns in FR)
        req_patterns = [
            r"\b(pi[eè]ces?\s+à\s+fournir)\b[:\-]?\s*(.+)",
            r"\b(documents?\s+(?:à|a)\s+fournir)\b[:\-]?\s*(.+)",
            r"\b(conditions?\s+d['’]éligibilit[eé])\b[:\-]?\s*(.+)",
            r"\b(doit|doivent|nécessaire|obligatoire)\b\s+(.{0,80})",
        ]
        for pat in req_patterns:
            mm = re.search(pat, text, flags=re.IGNORECASE)
            if not mm:
                continue
            tail = (mm.group(mm.lastindex) or "").strip()
            tail = re.split(r"[\n\r•\-]{1,}", tail)[0].strip()
            if len(tail) < 8:
                continue
            triples.append(
                GraphTriple(
                    subject=default_subject,
                    predicate="REQUIRES",
                    object=tail,
                    confidence=0.5,
                    evidence=evidence,
                )
            )
            if len(triples) >= 8:
                return triples

        return triples
