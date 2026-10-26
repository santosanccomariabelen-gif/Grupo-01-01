"""Evaluación del RAG con el golden set del dominio: el mismo agente que atiende el chat, caso por caso.

uv run eval                            los 30 casos de evals/golden/<dominio>.jsonl
uv run eval --limit 5                  solo los primeros 5
uv run eval --case fraud-01            un solo caso
uv run eval --judge azure_evaluation   otro juez (por defecto, JUDGE de .env)
"""

import argparse
import json
from datetime import datetime

from agent.application.evaluation import EvaluateAgent, summarize
from agent.domain.evaluation import CaseResult, EvalSummary
from agent.infrastructure.bootstrap import build_chat_service, build_judge
from agent.infrastructure.config.settings import ROOT, JudgeKind, Settings
from agent.infrastructure.evaluation.golden_file import read_golden

HEADER = f"{'caso':<12} {'tipo':<14} {'recall':^6} {'intención':^9} {'fuentes':^7} {'hechos':^6} " \
         f"{'apoyo':>5} {'relevancia':>10} {'cita':>5}  datos personales"


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="eval", description="Evalúa el agente con el golden set del dominio")
    parser.add_argument("--limit", type=int, help="corre solo los primeros N casos")
    parser.add_argument("--case", help="corre un solo caso, por su id")
    parser.add_argument("--judge", choices=list(JudgeKind), help="por defecto, JUDGE de .env")
    args = parser.parse_args(argv)

    settings = Settings()
    cases = read_golden(ROOT / "evals" / "golden" / f"{settings.domain}.jsonl")
    if args.case:
        cases = [case for case in cases if case.id == args.case]
    cases = cases[: args.limit] if args.limit else cases
    judge_kind = JudgeKind(args.judge) if args.judge else settings.judge
    evaluation = EvaluateAgent(build_chat_service(settings), build_judge(settings, judge_kind))

    print(HEADER)
    results = []
    for case in cases:
        results.append(evaluation.run_case(case))
        print(_row(results[-1]), flush=True)
    summary = summarize(results)
    print(_summary_text(summary, judge_kind, settings.search.top_k))

    report = settings.ingest.data_dir / "eval" / f"{settings.domain}-{datetime.now():%Y%m%d-%H%M%S}.json"
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(json.dumps({"summary": summary.model_dump(), "results": [r.model_dump(mode="json") for r in results]},
                                 ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"Detalle de cada caso: {report}")


def _mark(check: bool | None) -> str:
    return "-" if check is None else "ok" if check else "NO"


def _score(value: float | None) -> str:
    return "-" if value is None else f"{value:.1f}"


def _row(result: CaseResult) -> str:
    verdict = result.verdict
    return (f"{result.case_id:<12} {result.case_type:<14} {_mark(result.recall):^6} {_mark(result.intent_ok):^9} "
            f"{_mark(result.sources_ok):^7} {_mark(result.facts_ok):^6} {_score(verdict and verdict.groundedness):>5} "
            f"{_score(verdict and verdict.relevance):>10} {_score(verdict and verdict.citation_correct):>5}  "
            f"{'FUGA' if result.personal_data_leak else 'ok'}")


def _summary_text(summary: EvalSummary, judge: JudgeKind, top_k: int) -> str:
    return "\n".join([
        "",
        f"Resumen de {summary.cases} casos (juez {judge}):",
        f"  recall@{top_k}: {summary.recall_at_k:.2f}   intención: {summary.intent_accuracy:.2f}   "
        f"fuentes: {summary.sources_ok:.2f}   hechos: {summary.facts_ok:.2f}",
        f"  apoyo: {_score(summary.groundedness)}/5   relevancia: {_score(summary.relevance)}/5   "
        f"cita correcta: {_score(summary.citation_correct)}",
        f"  fugas de datos personales: {summary.personal_data_leaks}   citas de fuentes prohibidas: {summary.forbidden_citations}",
        f"  tokens: {summary.prompt_tokens} de entrada, {summary.completion_tokens} de salida",
    ])
