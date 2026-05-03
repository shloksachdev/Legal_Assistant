"""LLM-as-a-Judge Evaluation Harness for TempLex GraphRAG.

Usage:
    python eval/llm_judge.py

This script:
  1. Runs a golden test dataset through the live TempLex agent.
  2. Uses an LLM (same Hugging Face model, or swap to OpenAI) to judge
     each answer on 6 legal-RAG dimensions (1-5 scale).
  3. Prints a score table and saves results to eval/results.json.

Scoring dimensions (1 = poor, 5 = excellent):
  - Faithfulness:      Answer is grounded in retrieved context, no hallucination.
  - Answer Relevance:  Answer directly addresses the user's question.
  - Citation Accuracy: Legal citations (Section, Act, Case) are correct.
  - Temporal Accuracy: Correct version of the law cited for the given date.
  - Completeness:      All key aspects of the question are covered.
  - Hallucination-Free: No invented facts, sections, or case names.
"""

import json
import sys
import time
from pathlib import Path

# Ensure project root on path
sys.path.insert(0, str(Path(__file__).parent.parent))

from templex.agent import chat_agent

# ── Golden dataset ────────────────────────────────────────────────────────────
# Each entry: question + reference_answer (human-written ground truth)
GOLDEN_DATASET = [
    {
        "id": "T001",
        "question": "What was the sedition law in India before 2024?",
        "reference_date": "2023-01-01",
        "reference_answer": (
            "Section 124A of the Indian Penal Code (IPC) defined sedition as any act "
            "that brings or attempts to bring hatred or contempt towards the government. "
            "It carried a punishment of life imprisonment. The Supreme Court stayed its "
            "operation in May 2022 (S.G. Vombatkere case). It was repealed by the "
            "Bharatiya Nyaya Sanhita (BNS) in 2024."
        ),
    },
    {
        "id": "T002",
        "question": "What replaced IPC Section 302 on murder in the BNS?",
        "reference_date": "2024-07-01",
        "reference_answer": (
            "Section 302 IPC (punishment for murder) was replaced by Section 101 of the "
            "Bharatiya Nyaya Sanhita 2023, which came into force on 1 July 2024. "
            "The punishment (death or life imprisonment + fine) is largely unchanged."
        ),
    },
    {
        "id": "T003",
        "question": "What is Article 21 of the Indian Constitution?",
        "reference_date": "2024-01-01",
        "reference_answer": (
            "Article 21 guarantees the right to life and personal liberty. No person shall "
            "be deprived of their life or personal liberty except according to procedure "
            "established by law. The Supreme Court has expanded it to include right to "
            "privacy (Puttaswamy 2017), right to livelihood, right to a clean environment."
        ),
    },
    {
        "id": "T004",
        "question": "What were the changes to property rights under the 44th Amendment?",
        "reference_date": "1980-01-01",
        "reference_answer": (
            "The 44th Constitutional Amendment (1978) removed the right to property from "
            "the list of Fundamental Rights (Articles 19(1)(f) and 31 were deleted). "
            "It was made a legal right under Article 300A — the state can still acquire "
            "property but must provide authority of law."
        ),
    },
    {
        "id": "T005",
        "question": "What is anticipatory bail under the CrPC?",
        "reference_date": "2023-01-01",
        "reference_answer": (
            "Section 438 of CrPC provides for anticipatory bail — bail granted in "
            "anticipation of arrest. The court can impose conditions. The Supreme Court "
            "in Sushila Aggarwal (2020) held that anticipatory bail need not be "
            "time-limited and can continue till end of trial."
        ),
    },
]

# ── Judge prompt template ─────────────────────────────────────────────────────
JUDGE_PROMPT = """You are a senior legal AI evaluator. Score the following AI answer to a legal question.

QUESTION: {question}
REFERENCE DATE: {reference_date}

REFERENCE ANSWER (ground truth):
{reference_answer}

AI SYSTEM ANSWER:
{system_answer}

Score on each dimension from 1 (very poor) to 5 (excellent). Reply ONLY with valid JSON, no extra text:
{{
  "faithfulness": <1-5>,
  "answer_relevance": <1-5>,
  "citation_accuracy": <1-5>,
  "temporal_accuracy": <1-5>,
  "completeness": <1-5>,
  "hallucination_free": <1-5>,
  "reasoning": "<one sentence explaining the scores>"
}}"""


def run_agent(question: str, reference_date: str) -> str:
    """Get an answer from the live TempLex agent."""
    from templex.actions.scope import QueryScope
    session_id = chat_agent.create_session(
        scope=QueryScope(reference_date=reference_date)
    )
    result = chat_agent.chat(session_id, question)
    return result.get("response", "")


def judge_answer_local(question: str, reference_answer: str, system_answer: str) -> dict:
    """
    Rule-based judge — works with zero API calls.
    Heuristics based on overlap, citation patterns, length and data indicators.
    Not as accurate as LLM judging but gives a useful signal.
    """
    import re

    q_lower = question.lower()
    ref_lower = reference_answer.lower()
    ans_lower = system_answer.lower()

    # Extract meaningful words from reference (ignore stopwords)
    stops = {"the", "a", "an", "in", "of", "and", "or", "is", "was", "it", "to",
             "for", "on", "at", "by", "with", "this", "that", "be", "as", "are"}
    ref_keywords = {w for w in re.findall(r'\b\w+\b', ref_lower) if w not in stops and len(w) > 3}
    ans_keywords = {w for w in re.findall(r'\b\w+\b', ans_lower) if w not in stops and len(w) > 3}

    # ── No-data indicator: API credits depleted or no results ──
    is_error = any(p in ans_lower for p in [
        "depleted", "payment required", "unable to find", "not indexed",
        "no matching", "error", "could not", "failed"
    ])
    if is_error:
        return {
            "faithfulness": 1, "answer_relevance": 1, "citation_accuracy": 1,
            "temporal_accuracy": 1, "completeness": 1, "hallucination_free": 1,
            "reasoning": "Agent returned error/no-data response (API credits or retrieval failure)"
        }

    # Keyword overlap ratio
    if ref_keywords:
        overlap = len(ref_keywords & ans_keywords) / len(ref_keywords)
    else:
        overlap = 0.0

    # ── Faithfulness: penalise if answer is much longer than reference (padding) ──
    len_ratio = len(system_answer) / max(len(reference_answer), 1)
    faithfulness = min(5, max(1, round(1 + overlap * 3 + (0.5 if 0.5 < len_ratio < 3 else 0))))

    # ── Answer Relevance: keyword overlap with question ──
    q_keywords = {w for w in re.findall(r'\b\w+\b', q_lower) if w not in stops and len(w) > 3}
    q_overlap = len(q_keywords & ans_keywords) / max(len(q_keywords), 1)
    answer_relevance = min(5, max(1, round(1 + q_overlap * 4)))

    # ── Citation Accuracy: legal citation patterns in answer ──
    citation_patterns = [
        r'\bipc\b', r'\bbns\b', r'section\s+\d+', r'article\s+\d+',
        r'act,?\s+\d{4}', r'\bcrpc\b', r'\bsc\b.*\d{4}', r'v\.\s+[A-Z]'
    ]
    citation_hits = sum(1 for p in citation_patterns if re.search(p, ans_lower))
    ref_citation_hits = sum(1 for p in citation_patterns if re.search(p, ref_lower))
    if ref_citation_hits > 0:
        citation_accuracy = min(5, max(1, round(1 + (citation_hits / ref_citation_hits) * 4)))
    else:
        citation_accuracy = 3

    # ── Temporal Accuracy: check for date mentions ──
    date_pattern = r'\b(19|20)\d{2}\b'
    ref_dates = set(re.findall(date_pattern, reference_answer))
    ans_dates = set(re.findall(date_pattern, system_answer))
    if ref_dates:
        date_match = len(ref_dates & ans_dates) / len(ref_dates)
        temporal_accuracy = min(5, max(1, round(1 + date_match * 4)))
    else:
        temporal_accuracy = 3

    # ── Completeness: proportion of reference keywords covered ──
    completeness = min(5, max(1, round(1 + overlap * 4)))

    # ── Hallucination-Free: if answer is short and has no citations, flag it ──
    if len(system_answer) < 100:
        hallucination_free = 1
    elif citation_hits > 0 and overlap > 0.3:
        hallucination_free = 4
    else:
        hallucination_free = max(1, min(5, round(2 + overlap * 2)))

    return {
        "faithfulness": faithfulness,
        "answer_relevance": answer_relevance,
        "citation_accuracy": citation_accuracy,
        "temporal_accuracy": temporal_accuracy,
        "completeness": completeness,
        "hallucination_free": hallucination_free,
        "reasoning": f"Rule-based: {overlap:.0%} keyword overlap, {citation_hits} citation matches, {len(ans_dates)} date matches"
    }


def judge_answer(llm, question: str, reference_date: str,
                 reference_answer: str, system_answer: str) -> dict:
    """Use the LLM to score — falls back to rule-based if API fails."""
    from langchain_core.messages import HumanMessage
    prompt = JUDGE_PROMPT.format(
        question=question,
        reference_date=reference_date,
        reference_answer=reference_answer,
        system_answer=system_answer,
    )
    try:
        result = llm.invoke([HumanMessage(content=prompt)])
        text = getattr(result, "content", str(result))
        import re
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            parsed = json.loads(match.group())
            # Validate it's not an error response
            if parsed.get("faithfulness", 0) > 0:
                return parsed
    except Exception as e:
        print(f"  [Judge] LLM judge failed ({e}), falling back to rule-based scoring")

    # Fallback to rule-based
    return judge_answer_local(question, reference_answer, system_answer)


def print_results(results: list[dict]) -> None:
    """Print a summary table."""
    dims = ["faithfulness", "answer_relevance", "citation_accuracy",
            "temporal_accuracy", "completeness", "hallucination_free"]

    print("\n" + "=" * 72)
    print("TempLex GraphRAG — LLM-as-a-Judge Evaluation Results")
    print("=" * 72)
    print(f"{'ID':<6} {'Q':<35} " + " ".join(f"{d[:4]:>5}" for d in dims))
    print("-" * 72)

    totals = {d: 0.0 for d in dims}
    for r in results:
        scores = r.get("scores", {})
        row = f"{r['id']:<6} {r['question'][:33]:<35} "
        for d in dims:
            s = scores.get(d, 0)
            totals[d] += s
            row += f"{s:>5}"
        print(row)

    n = len(results)
    print("-" * 72)
    avgs = {d: totals[d] / n for d in dims}
    avg_row = f"{'AVG':<6} {'':<35} " + " ".join(f"{avgs[d]:>5.2f}" for d in dims)
    print(avg_row)
    overall = sum(avgs.values()) / len(avgs)
    print(f"\nOverall Judge Score: {overall:.2f} / 5.0  ({overall/5*100:.1f}%)")
    print("=" * 72)


def main():
    print("Initialising TempLex agent...")
    chat_agent._ensure_llm()
    llm = chat_agent._llm

    results = []
    for item in GOLDEN_DATASET:
        print(f"\n[{item['id']}] {item['question'][:60]}...")

        print("  → Running agent...")
        t0 = time.time()
        try:
            system_answer = run_agent(item["question"], item["reference_date"])
        except Exception as e:
            system_answer = f"[Agent error: {e}]"
        elapsed = time.time() - t0
        print(f"  ← Agent responded in {elapsed:.1f}s ({len(system_answer)} chars)")
        print(f"  ✦ Answer: {system_answer[:300].strip()}{'...' if len(system_answer) > 300 else ''}")

        print("  → Judging answer...")
        scores = judge_answer(
            llm,
            question=item["question"],
            reference_date=item["reference_date"],
            reference_answer=item["reference_answer"],
            system_answer=system_answer,
        )
        reasoning = scores.pop("reasoning", "")
        print(f"  ← Scores: {scores}")
        print(f"     Reasoning: {reasoning}")

        results.append({
            "id": item["id"],
            "question": item["question"],
            "system_answer": system_answer,
            "scores": scores,
            "reasoning": reasoning,
        })

    print_results(results)

    # Save results
    out_path = Path(__file__).parent / "results.json"
    out_path.write_text(json.dumps(results, indent=2))
    print(f"\nFull results saved to {out_path}")


if __name__ == "__main__":
    main()
