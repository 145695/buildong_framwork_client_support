"""
RAG Evaluation System – BNA Knowledge Base
==========================================
Exact metrics required:

  1. Retrieval Precision   : proportion of retrieved chunks relevant to the
                             query, averaged over all test questions.
  2. Answer Relevance Score: LLM-judged relevance of each answer to its
                             question, on a 0-1 scale.
  3. Faithfulness Score    : percentage of answers fully grounded in the
                             retrieved context.
  4. Avg Response Latency  : mean end-to-end response time in seconds.

Outputs (auto-generated after every run):
  rag_eval_results.csv   – per-question raw scores
  rag_eval_results.json  – summary + per-question data
  rag_eval_charts.png    – 4-panel metric charts + latency distribution
  rag_eval_report.html   – standalone HTML report with embedded chart
"""

import asyncio
import base64
import csv
import json
import logging
import re
import time
from dataclasses import asdict, dataclass, field
from functools import wraps
from pathlib import Path
from typing import Any, Dict, List, Optional

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.gridspec import GridSpec
import numpy as np
import sys

sys.path.insert(0, str(Path(__file__).parent))

from app.layer2.knowledgebase.intelligent_rag_system import IntelligentRAGSystem
from app.layer2.knowledgebase.mistral_llm import MistralLLM

logging.basicConfig(level=logging.INFO, format="%(message)s", force=True)
logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# TEST QUESTIONS  (French, directly from policy documents)
# ─────────────────────────────────────────────────────────────────────────────
# WARNING: Verify every question maps to actual content in your PDFs before running.
# Source tags are for your traceability only; the evaluator does not use them.

TEST_QUESTIONS: List[Dict[str, str]] = [

    # ── CGB Particuliers ─────────────────────────────────────────────────────
    {"id":  1, "question": "Quel est le montant annuel des frais de tenue d'un compte chèque pour un particulier ?",                   "source": "CGB_Particuliers"},
    {"id":  2, "question": "Quels sont les frais appliqués pour une demande d'historique de compte ?",                                 "source": "CGB_Particuliers"},
    {"id":  3, "question": "Quel est le coût d'un retrait d'espèces par carte CIB en interbancaire ?",                                 "source": "CGB_Particuliers"},
    {"id":  4, "question": "Quel est le taux d'intérêt appliqué à un compte épargne dont le solde est inférieur à 1 000 000 DA ?",     "source": "CGB_Particuliers"},
    {"id":  5, "question": "Quels sont les frais de commission sur les opérations de change pour les particuliers ?",                   "source": "CGB_Particuliers"},

    # ── Brochure Entreprises ──────────────────────────────────────────────────
    {"id":  6, "question": "Quel est le montant des frais de tenue de compte en Dinars pour les entreprises par trimestre ?",           "source": "Brochure_Entreprises"},
    {"id":  7, "question": "Quel est le tarif de l'abonnement mensuel au service SOGECASH NET Pack Base ?",                             "source": "Brochure_Entreprises"},
    {"id":  8, "question": "Quels sont les frais pour un virement de compte à compte effectué dans la même agence BNA ?",               "source": "Brochure_Entreprises"},
    {"id":  9, "question": "Quelles sont les conditions tarifaires pour l'encaissement de chèques sur place pour les entreprises ?",    "source": "Brochure_Entreprises"},
    {"id": 10, "question": "Quel est le coût d'un chèque de banque émis pour le compte d'une entreprise ?",                            "source": "Brochure_Entreprises"},

    # ── Fiche Crédit Immobilier ───────────────────────────────────────────────
    {"id": 11, "question": "Quel est l'âge maximum pour être éligible à un crédit immobilier à la BNA ?",                              "source": "Fiche_Credit_Immobilier"},
    {"id": 12, "question": "Quel est le taux d'intérêt sans bonification appliqué aux clients non épargnants pour un crédit immobilier ?", "source": "Fiche_Credit_Immobilier"},
    {"id": 13, "question": "Quelle est la durée maximale de remboursement d'un crédit immobilier accordé par la BNA ?",                 "source": "Fiche_Credit_Immobilier"},
    {"id": 14, "question": "Un client de moins de 40 ans peut-il bénéficier d'un financement à 100 % pour son crédit immobilier ?",     "source": "Fiche_Credit_Immobilier"},
    {"id": 15, "question": "Quels sont les documents requis pour constituer un dossier de crédit immobilier à la BNA ?",                "source": "Fiche_Credit_Immobilier"},

    # ── Note TEG ─────────────────────────────────────────────────────────────
    {"id": 16, "question": "Quel est le seuil du taux d'intérêt excessif pour les découverts au premier semestre 2026 ?",              "source": "Note_TEG"},
    {"id": 17, "question": "Quel est le seuil du taux d'intérêt excessif applicable au leasing selon la note TEG ?",                   "source": "Note_TEG"},
    {"id": 18, "question": "Quel est le seuil du taux excessif pour les crédits à la consommation au premier semestre 2026 ?",          "source": "Note_TEG"},

    # ── Out-of-scope (grounding / faithfulness stress test) ───────────────────
    {"id": 19, "question": "Quelle est la recette traditionnelle pour préparer un couscous algérien ?",                                "source": None},
    {"id": 20, "question": "Quels sont les tarifs pour ouvrir un compte bancaire domicilié en France avec la BNA ?",                   "source": None},
]


# ─────────────────────────────────────────────────────────────────────────────
# RETRY DECORATOR
# ─────────────────────────────────────────────────────────────────────────────

def retry_async(max_attempts: int = 5, base_delay: float = 30.0):
    """
    Retry with rate-limit-aware backoff.
    On 429 errors waits base_delay * attempt seconds (30s, 60s, 90s …).
    On other errors waits 2s * attempt.
    """
    def decorator(fn):
        @wraps(fn)
        async def wrapper(*args, **kwargs):
            last_err = None
            for attempt in range(1, max_attempts + 1):
                try:
                    return await fn(*args, **kwargs)
                except Exception as e:
                    last_err = e
                    is_rate_limit = "429" in str(e) or "rate_limit" in str(e).lower() or "rate limit" in str(e).lower()
                    wait = base_delay * attempt if is_rate_limit else 2.0 * attempt
                    logger.warning(
                        f"  attempt {attempt}/{max_attempts} failed "
                        f"({'rate limit – waiting' if is_rate_limit else 'error – waiting'} {wait:.0f}s): {e}"
                    )
                    if attempt < max_attempts:
                        await asyncio.sleep(wait)
            raise RuntimeError(f"All {max_attempts} attempts failed. Last: {last_err}")
        return wrapper
    return decorator


# ─────────────────────────────────────────────────────────────────────────────
# RESULT DATACLASS
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class EvalResult:
    question_id: int
    question: str
    source_doc: Optional[str]

    # RAG outputs
    answer: str = ""
    sources: List[str] = field(default_factory=list)
    retrieved_chunks_count: int = 0
    latency_seconds: float = 0.0

    # GraphRAG (new KB) – optional, metrics unchanged
    graph_facts_count: int = 0
    graph_facts_preview: str = ""
    vector_backend: str = ""  # faiss | bruteforce | keyword | none

    # The 4 required metrics
    retrieval_precision: float = 0.0    # proportion of relevant chunks (0–1)
    answer_relevance: float = 0.0       # LLM-judged relevance (0–1)
    faithfulness: float = 0.0           # grounded in context: 1.0 or 0.0
    # latency_seconds already above

    error: str = ""


# ─────────────────────────────────────────────────────────────────────────────
# JUDGE LLM  (separate, stronger model — no circular evaluation)
# ─────────────────────────────────────────────────────────────────────────────

class JudgeLLM:
    """
    Uses mistral-small for evaluation — same tier as the RAG pipeline.
    A short inter-call delay prevents burst rate-limiting.
    """
    CALL_DELAY = 1.0   # seconds between every judge API call

    def __init__(self):
        self.llm = MistralLLM(model_name="mistral-small", temperature=0)

    @retry_async(max_attempts=5, base_delay=30.0)
    async def _call(self, prompt: str) -> str:
        await asyncio.sleep(self.CALL_DELAY)
        resp = await self.llm.ainvoke(prompt)
        return resp.content.strip()

    # ── Metric 1: chunk relevance ─────────────────────────────────────────────
    async def is_chunk_relevant(self, question: str, chunk_text: str) -> bool:
        """True if the chunk contains information useful for answering the question."""
        prompt = (
            "Tu es un évaluateur de pertinence documentaire.\n"
            "Réponds UNIQUEMENT par 'oui' ou 'non'.\n\n"
            f"Question : {question}\n\n"
            f"Extrait : {chunk_text}\n\n"
            "Cet extrait contient-il des informations utiles pour répondre à la question ?"
        )
        raw = await self._call(prompt)
        return raw.lower().startswith("oui")

    # ── Metric 2: answer relevance ────────────────────────────────────────────
    async def rate_answer_relevance(self, question: str, answer: str) -> float:
        """Returns a 0.0–1.0 score reflecting how relevant the answer is."""
        if not answer.strip():
            return 0.0
        prompt = (
            "Tu es un évaluateur. Note la pertinence de la réponse par rapport à la question.\n"
            "Utilise une échelle de 1 à 5 :\n"
            "  1 = totalement hors sujet\n"
            "  2 = légèrement pertinente\n"
            "  3 = modérément pertinente\n"
            "  4 = très pertinente\n"
            "  5 = parfaitement pertinente\n"
            "Réponds UNIQUEMENT avec un chiffre entre 1 et 5.\n\n"
            f"Question : {question}\n\n"
            f"Réponse : {answer}"
        )
        raw = await self._call(prompt)
        m = re.search(r"[1-5]", raw)
        if not m:
            logger.warning(f"  Could not parse relevance score: {raw!r}")
            return 0.5
        return (int(m.group()) - 1) / 4.0   # normalize → 0–1

    # ── Metric 3: faithfulness ────────────────────────────────────────────────
    async def rate_faithfulness(self, answer: str, chunks: List[Dict], graph_facts: str = "") -> float:
        """1.0 if the answer is fully grounded in the retrieved context, else 0.0."""
        if not answer.strip():
            return 0.0
        chunk_context = "\n\n".join(
            f"[Extrait {i+1}] {c.get('content', '')}"
            for i, c in enumerate(chunks[:5])
        )
        context = ""
        if graph_facts.strip():
            context += f"[FAITS (graphe)]\n{graph_facts.strip()}\n\n"
        context += chunk_context
        prompt = (
            "Tu es un évaluateur de fidélité.\n"
            "La réponse est-elle ENTIÈREMENT basée sur les extraits fournis,\n"
            "sans aucune information inventée ou extérieure ?\n"
            "Réponds UNIQUEMENT par 'oui' ou 'non'.\n\n"
            f"Extraits :\n{context}\n\n"
            f"Réponse : {answer}"
        )
        raw = await self._call(prompt)
        return 1.0 if raw.lower().startswith("oui") else 0.0


# ─────────────────────────────────────────────────────────────────────────────
# EVALUATOR
# ─────────────────────────────────────────────────────────────────────────────

class RAGEvaluator:

    def __init__(self):
        self.rag: Optional[IntelligentRAGSystem] = None
        self.judge = JudgeLLM()
        self.results: List[EvalResult] = []

    async def initialize(self):
        logger.info("[EVAL] Initialising RAG system …")
        self.rag = IntelligentRAGSystem()
        await self.rag.load_documents()
        logger.info(f"[EVAL] {len(self.rag.document_chunks)} chunks loaded")

    # ── single question ───────────────────────────────────────────────────────

    async def _evaluate_one(self, entry: Dict[str, Any]) -> EvalResult:
        qid      = entry["id"]
        question = entry["question"]
        src      = entry.get("source")

        logger.info(f"\n{'─'*65}")
        logger.info(f"Q{qid:02d} → {question}")

        r = EvalResult(question_id=qid, question=question, source_doc=src)

        # Run RAG
        t0 = time.perf_counter()
        try:
            out = await self.rag.ask_question(question)
        except Exception as e:
            r.error = str(e)
            logger.error(f"  RAG error: {e}")
            self.results.append(r)
            return r

        r.latency_seconds = time.perf_counter() - t0
        r.answer  = out.get("answer", "")
        r.sources = out.get("sources", [])
        r.vector_backend = out.get("vector_backend", "") or getattr(self.rag, "_vector_backend", "")

        chunks: List[Dict] = out.get("retrieved_chunks", [])
        chunks_available = bool(chunks)
        if not chunks_available:
            logger.warning(
                "  WARNING: 'retrieved_chunks' not in RAG output → "
                "Retrieval Precision will be skipped (N/A) for this question.\n"
                "  Fix: return 'retrieved_chunks' from IntelligentRAGSystem.ask_question()."
            )
        r.retrieved_chunks_count = len(chunks)

        # GraphRAG: collect a small set of KG facts used as additional context
        graph_facts = ""
        try:
            if getattr(self.rag, "graph_store", None) is not None:
                seeds = self.rag.graph_store.find_seed_entities(question, limit=20)
                triples = self.rag.graph_store.neighborhood_triples(
                    seeds, hops=1, max_triples=12, min_confidence=0.45
                )
                r.graph_facts_count = len(triples)
                if triples:
                    graph_facts = "\n".join([f"- {t.subject} | {t.predicate} | {t.object}" for t in triples])
                    r.graph_facts_preview = graph_facts[:240] + ("…" if len(graph_facts) > 240 else "")
        except Exception:
            graph_facts = ""

        if r.vector_backend:
            logger.info(f"  🔎  vector_backend: {r.vector_backend}")
        logger.info(f"  ⏱  {r.latency_seconds:.2f}s | chunks: {len(chunks)}")
        logger.info(f"  📄  {r.answer[:160]}…")

        # ── Metric 1 : Retrieval Precision ────────────────────────────────────
        if chunks_available:
            relevant = 0
            for i, chunk in enumerate(chunks):
                try:
                    is_rel = await self.judge.is_chunk_relevant(question, chunk.get("content", ""))
                    logger.info(f"  chunk {i+1}: {'PASS' if is_rel else 'FAIL'}")
                    relevant += int(is_rel)
                except Exception as e:
                    logger.error(f"  chunk {i+1}: judge failed → {e}")
            r.retrieval_precision = relevant / len(chunks)
        else:
            r.retrieval_precision = float("nan")   # N/A — excluded from average
        logger.info(f"  [EVAL] Retrieval Precision = {r.retrieval_precision if not (isinstance(r.retrieval_precision, float) and r.retrieval_precision != r.retrieval_precision) else 'N/A'}")

        # ── Metric 2 : Answer Relevance ───────────────────────────────────────
        logger.info("  [EVAL] Judging answer relevance …")
        r.answer_relevance = await self.judge.rate_answer_relevance(question, r.answer)
        logger.info(f"  [EVAL] Answer Relevance    = {r.answer_relevance:.3f}")

        # ── Metric 3 : Faithfulness ───────────────────────────────────────────
        if chunks_available:
            logger.info("  🔗  Judging faithfulness …")
            r.faithfulness = await self.judge.rate_faithfulness(r.answer, chunks, graph_facts=graph_facts)
            logger.info(f"  🔗  Faithfulness        = {r.faithfulness:.3f}")
        else:
            r.faithfulness = float("nan")   # N/A — no context to ground against
            logger.info("  🔗  Faithfulness        = N/A (no chunks)")

        self.results.append(r)
        return r

    # ── full run ──────────────────────────────────────────────────────────────

    async def run(self, delay: float = 2.0):
        await self.initialize()
        total = len(TEST_QUESTIONS)
        logger.info(f"\n[EVAL] Evaluating {total} questions …\n")

        for i, entry in enumerate(TEST_QUESTIONS, 1):
            logger.info(f"{'='*65}")
            logger.info(f"  Progress: {i}/{total}")
            await self._evaluate_one(entry)
            if i < total:
                logger.info(f"  [EVAL] Waiting {delay}s before next question …")
                await asyncio.sleep(delay)

        self._print_summary()
        self._save_csv()
        self._save_json()
        chart_path = self._generate_charts()
        self._generate_html_report(chart_path)

    # ─────────────────────────────────────────────────────────────────────────
    # SUMMARY HELPERS
    # ─────────────────────────────────────────────────────────────────────────

    def _summary(self) -> Dict[str, Any]:
        valid = [r for r in self.results if not r.error]
        n     = len(valid)

        def avg(attr):
            vals = [getattr(r, attr) for r in valid]
            vals = [v for v in vals if not (isinstance(v, float) and v != v)]  # drop NaN
            return float(np.mean(vals)) if vals else 0.0

        lats = [r.latency_seconds for r in valid]
        prec_available = any(
            not (isinstance(r.retrieval_precision, float) and r.retrieval_precision != r.retrieval_precision)
            for r in valid
        )
        return {
            "total_questions":     len(self.results),
            "successful":          n,
            "errors":              len(self.results) - n,
            "retrieval_precision": round(avg("retrieval_precision"), 4) if prec_available else "N/A",
            "answer_relevance":    round(avg("answer_relevance"),    4),
            "faithfulness_pct":    round(avg("faithfulness") * 100,  2),
            "avg_latency_s":       round(float(np.mean(lats)), 3) if lats else 0.0,
            "std_latency_s":       round(float(np.std(lats)),  3) if lats else 0.0,
            "max_latency_s":       round(float(np.max(lats)),  3) if lats else 0.0,
            "chunks_available":    prec_available,
        }

    def _print_summary(self):
        s = self._summary()
        W = 70
        print("\n" + "=" * W)
        print("  📊  BNA RAG EVALUATION SUMMARY")
        print("=" * W)
        print(f"  {'Metric':<35} {'Value'}")
        print("  " + "-" * (W - 2))
        if isinstance(s["retrieval_precision"], str):
            print(f"  {'Retrieval Precision':<35} {s['retrieval_precision']}")
        else:
            print(f"  {'Retrieval Precision':<35} {s['retrieval_precision']:.4f}")
        print(f"  {'Answer Relevance Score':<35} {s['answer_relevance']:.4f}  (scale 0–1)")
        print(f"  {'Faithfulness Score':<35} {s['faithfulness_pct']:.1f}%  (% grounded answers)")
        print(f"  {'Avg Response Latency':<35} {s['avg_latency_s']:.3f}s  (±{s['std_latency_s']:.3f}s, max {s['max_latency_s']:.3f}s)")
        print("  " + "-" * (W - 2))
        print(f"  Questions: {s['total_questions']}  |  Successful: {s['successful']}  |  Errors: {s['errors']}")
        print("=" * W)

        # per-question breakdown
        print(f"\n  {'ID':<4} {'Precision':>10} {'Relevance':>10} {'Faithful':>10} {'Latency':>9}  Source")
        print("  " + "-" * 62)
        for r in self.results:
            if r.error:
                print(f"  {r.question_id:<4} {'ERROR':>10}  {r.question[:35]}")
            else:
                print(
                    f"  {r.question_id:<4}"
                    f" {r.retrieval_precision:>10.3f}"
                    f" {r.answer_relevance:>10.3f}"
                    f" {r.faithfulness:>10.3f}"
                    f" {r.latency_seconds:>8.2f}s"
                    f"  {r.source_doc or 'hors-scope'}"
                )
        print()

    # ─────────────────────────────────────────────────────────────────────────
    # SAVE CSV / JSON
    # ─────────────────────────────────────────────────────────────────────────

    def _save_csv(self, path: str = "rag_eval_results.csv"):
        fields = [
            "question_id", "question", "source_doc",
            "retrieval_precision", "answer_relevance", "faithfulness",
            "latency_seconds", "retrieved_chunks_count",
            "answer", "sources", "error",
        ]
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=fields)
            w.writeheader()
            for r in self.results:
                row = asdict(r)
                row["sources"] = "; ".join(row.get("sources") or [])
                w.writerow({k: row.get(k, "") for k in fields})
        logger.info(f"[EVAL] CSV  → {path}")

    def _save_json(self, path: str = "rag_eval_results.json"):
        payload = {"summary": self._summary(), "results": [asdict(r) for r in self.results]}
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        logger.info(f"[EVAL] JSON → {path}")

    # ─────────────────────────────────────────────────────────────────────────
    # CHARTS  (4-panel PNG)
    # ─────────────────────────────────────────────────────────────────────────

    def _generate_charts(self, out_dir: str = ".") -> str:
        out_path = Path(out_dir) / "rag_eval_charts.png"
        valid    = [r for r in self.results if not r.error]

        ids    = [f"Q{r.question_id}" for r in valid]
        xpos   = np.arange(len(ids))
        C = {"precision": "#4C72B0", "relevance": "#55A868",
             "faith":     "#C44E52", "latency":   "#8172B2"}

        fig = plt.figure(figsize=(18, 16))
        fig.patch.set_facecolor("#F8F9FA")
        gs  = GridSpec(2, 2, figure=fig, hspace=0.50, wspace=0.35)

        def annotate(ax, bars):
            for b in bars:
                h = b.get_height()
                ax.text(b.get_x() + b.get_width() / 2, h + 0.015,
                        f"{h:.2f}", ha="center", va="bottom", fontsize=7)

        def style(ax, title, ylabel="Score (0–1)", ylim=(0, 1.12)):
            ax.set_xticks(xpos)
            ax.set_xticklabels(ids, fontsize=7, rotation=45, ha="right")
            ax.set_ylim(*ylim)
            ax.set_title(title, fontweight="bold", fontsize=11)
            ax.set_ylabel(ylabel)
            ax.set_facecolor("#FFFFFF")
            ax.spines["top"].set_visible(False)
            ax.spines["right"].set_visible(False)

        # ── Panel 1 : Retrieval Precision ─────────────────────────────────────
        ax1   = fig.add_subplot(gs[0, 0])
        bars1 = ax1.bar(xpos, [r.retrieval_precision for r in valid],
                        color=C["precision"], edgecolor="white", linewidth=0.8)
        ax1.axhline(np.mean([r.retrieval_precision for r in valid]),
                    color="red", linestyle="--", linewidth=1.3,
                    label=f"Moy = {np.mean([r.retrieval_precision for r in valid]):.3f}")
        annotate(ax1, bars1)
        style(ax1, "Retrieval Precision")
        ax1.legend(fontsize=9)

        # ── Panel 2 : Answer Relevance Score ──────────────────────────────────
        ax2   = fig.add_subplot(gs[0, 1])
        bars2 = ax2.bar(xpos, [r.answer_relevance for r in valid],
                        color=C["relevance"], edgecolor="white", linewidth=0.8)
        ax2.axhline(np.mean([r.answer_relevance for r in valid]),
                    color="red", linestyle="--", linewidth=1.3,
                    label=f"Moy = {np.mean([r.answer_relevance for r in valid]):.3f}")
        annotate(ax2, bars2)
        style(ax2, "Answer Relevance Score")
        ax2.legend(fontsize=9)

        # ── Panel 3 : Faithfulness Score (% grounded) ────────────────────────
        ax3   = fig.add_subplot(gs[1, 0])
        faith_pct = [r.faithfulness * 100 for r in valid]
        bars3 = ax3.bar(xpos, faith_pct,
                        color=C["faith"], edgecolor="white", linewidth=0.8)
        ax3.axhline(np.mean(faith_pct), color="red", linestyle="--", linewidth=1.3,
                    label=f"Moy = {np.mean(faith_pct):.1f}%")
        for b in bars3:
            h = b.get_height()
            ax3.text(b.get_x() + b.get_width() / 2, h + 1,
                     f"{h:.0f}%", ha="center", va="bottom", fontsize=7)
        style(ax3, "Faithfulness Score  (% grounded in context)",
              ylabel="% Grounded", ylim=(0, 115))
        ax3.legend(fontsize=9)

        # ── Panel 4 : Average Response Latency ───────────────────────────────
        ax4   = fig.add_subplot(gs[1, 1])
        lats  = [r.latency_seconds for r in valid]
        bars4 = ax4.bar(xpos, lats, color=C["latency"],
                        edgecolor="white", linewidth=0.8)
        avg_lat = np.mean(lats)
        ax4.axhline(avg_lat, color="red", linestyle="--", linewidth=1.3,
                    label=f"Moy = {avg_lat:.2f}s")
        for b in bars4:
            h = b.get_height()
            ax4.text(b.get_x() + b.get_width() / 2, h + 0.02,
                     f"{h:.1f}s", ha="center", va="bottom", fontsize=7)
        style(ax4, "Average Response Latency (seconds)",
              ylabel="Secondes", ylim=(0, max(lats) * 1.25 if lats else 5))
        ax4.legend(fontsize=9)

        fig.suptitle(
            f"BNA – Rapport d'Évaluation RAG  ({len(valid)} questions)",
            fontsize=14, fontweight="bold", y=1.01, color="#1A1A2E"
        )

        plt.savefig(out_path, dpi=150, bbox_inches="tight",
                    facecolor=fig.get_facecolor())
        plt.close(fig)
        logger.info(f"📊  Charts → {out_path}")
        return str(out_path)

    # ─────────────────────────────────────────────────────────────────────────
    # HTML REPORT  (standalone, chart embedded as base64)
    # ─────────────────────────────────────────────────────────────────────────

    def _generate_html_report(self, chart_path: str, out_dir: str = "."):
        out_path = Path(out_dir) / "rag_eval_report.html"
        s = self._summary()

        with open(chart_path, "rb") as f:
            img_b64 = base64.b64encode(f.read()).decode()

        def badge(val: float, pct: bool = False) -> str:
            display = f"{val*100:.1f}%" if pct else f"{val:.3f}"
            color   = ("#28a745" if val >= 0.75 else
                       "#ffc107" if val >= 0.50 else "#dc3545")
            return (f'<span style="background:{color};color:#fff;'
                    f'border-radius:4px;padding:2px 8px;font-size:13px">'
                    f'{display}</span>')

        def lat_badge(v: float) -> str:
            color = "#28a745" if v < 2 else "#ffc107" if v < 5 else "#dc3545"
            return (f'<span style="background:{color};color:#fff;'
                    f'border-radius:4px;padding:2px 8px;font-size:13px">'
                    f'{v:.2f}s</span>')

        rows = ""
        for r in self.results:
            if r.error:
                rows += (f'<tr style="background:#fff3cd"><td>{r.question_id}</td>'
                         f'<td colspan="5">{r.question[:70]}…'
                         f'<br><small style="color:red">{r.error}</small></td></tr>')
            else:
                rows += (
                    f"<tr>"
                    f"<td>{r.question_id}</td>"
                    f'<td title="{r.question}">{r.question[:60]}…</td>'
                    f"<td>{badge(r.retrieval_precision)}</td>"
                    f"<td>{badge(r.answer_relevance)}</td>"
                    f"<td>{badge(r.faithfulness, pct=True)}</td>"
                    f"<td>{lat_badge(r.latency_seconds)}</td>"
                    f"<td>{r.source_doc or '<em>hors-scope</em>'}</td>"
                    f"</tr>"
                )

        html = f"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<title>BNA RAG Evaluation Report</title>
<style>
  body{{font-family:'Segoe UI',Arial,sans-serif;background:#f4f6f9;margin:0;padding:28px;color:#1a1a2e}}
  h1{{color:#1a1a2e;border-bottom:3px solid #4C72B0;padding-bottom:8px;margin-bottom:20px}}
  .grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;margin-bottom:28px}}
  .card{{background:#fff;border-radius:10px;padding:18px 22px;box-shadow:0 2px 8px rgba(0,0,0,.08)}}
  .card .lbl{{font-size:11px;color:#888;text-transform:uppercase;letter-spacing:1px}}
  .card .val{{font-size:28px;font-weight:700;margin-top:6px;color:#4C72B0}}
  .card .sub{{font-size:11px;color:#aaa;margin-top:3px}}
  img{{max-width:100%;border-radius:10px;box-shadow:0 2px 12px rgba(0,0,0,.12);margin:8px 0 28px}}
  table{{width:100%;border-collapse:collapse;background:#fff;border-radius:10px;
         overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,.08)}}
  th{{background:#1a1a2e;color:#fff;padding:11px 14px;font-size:12px;text-align:left}}
  td{{padding:9px 14px;font-size:13px;border-bottom:1px solid #f0f0f0;vertical-align:middle}}
  tr:last-child td{{border-bottom:none}}
  tr:hover td{{background:#f8f9ff}}
  footer{{margin-top:32px;font-size:11px;color:#bbb;text-align:center}}
</style>
</head>
<body>
<h1>🏦 BNA – Rapport d'Évaluation du Système RAG</h1>

<div class="grid">
  <div class="card">
    <div class="lbl">Retrieval Precision</div>
    <div class="val">{s['retrieval_precision']:.3f}</div>
    <div class="sub">proportion de chunks pertinents</div>
  </div>
  <div class="card">
    <div class="lbl">Answer Relevance Score</div>
    <div class="val">{s['answer_relevance']:.3f}</div>
    <div class="sub">pertinence LLM-jugée (0–1)</div>
  </div>
  <div class="card">
    <div class="lbl">Faithfulness Score</div>
    <div class="val">{s['faithfulness_pct']:.1f}%</div>
    <div class="sub">réponses ancrées dans le contexte</div>
  </div>
  <div class="card">
    <div class="lbl">Avg Response Latency</div>
    <div class="val">{s['avg_latency_s']:.2f}s</div>
    <div class="sub">±{s['std_latency_s']:.2f}s · max {s['max_latency_s']:.2f}s</div>
  </div>
</div>

<img src="data:image/png;base64,{img_b64}" alt="RAG Evaluation Charts">

<table>
  <thead>
    <tr>
      <th>#</th><th>Question</th>
      <th>Retrieval<br>Precision</th>
      <th>Answer<br>Relevance</th>
      <th>Faithfulness</th>
      <th>Latency</th>
      <th>Source</th>
    </tr>
  </thead>
  <tbody>{rows}</tbody>
</table>

<footer>
  BNA RAG Evaluator · {s['total_questions']} questions ·
  {s['successful']} réussies · {s['errors']} erreurs
</footer>
</body>
</html>"""

        with open(out_path, "w", encoding="utf-8") as f:
            f.write(html)
        logger.info(f"🌐  HTML → {out_path}")


# ─────────────────────────────────────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    asyncio.run(RAGEvaluator().run())
