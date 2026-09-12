"""CLI:

  python -m orchestrator_agent run --hospital 9001 --as-of-date 2026-08-30 --run-id run-0001
    Runs the full urgency -> capacity -> coordinator -> rationale pipeline
    and prints the agent's final narrative.

  python -m orchestrator_agent ask "why is PW-9001-000007 ranked here?"
    Asks a single question in Q&A mode (read-only tools only) and prints
    the answer.

  python -m orchestrator_agent chat
    Starts an interactive Q&A session -- ask follow-up questions without
    repeating context; type "exit"/"quit" or Ctrl-D to stop.
"""

from __future__ import annotations

import argparse
import sys

from .config import Settings, load_settings
from .run import ConversationHistory, ask_question, run_pipeline


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the triage orchestrator + rationale agent."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="Run the full pipeline for one hospital-day.")
    run_parser.add_argument("--hospital", required=True, help="4-character HIPE hospital code")
    run_parser.add_argument("--as-of-date", required=True, help="ISO date, e.g. 2026-08-30")
    run_parser.add_argument("--run-id", required=True, help="Shared run_id for this pipeline run")

    ask_parser = subparsers.add_parser("ask", help="Ask the agent a single question (Q&A mode).")
    ask_parser.add_argument("question", help="e.g. 'why is PW-9001-000007 ranked here?'")

    subparsers.add_parser("chat", help="Start an interactive Q&A session with the agent.")

    return parser.parse_args(argv)


def _run_chat_loop(settings: Settings) -> int:
    print("Triage orchestrator -- ask a question, or type 'exit'/'quit' to stop.")
    history: ConversationHistory | None = None
    while True:
        try:
            question = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return 0
        if not question:
            continue
        if question.lower() in {"exit", "quit"}:
            return 0
        answer, history = ask_question(question, settings=settings, history=history)
        print(answer)
        print()


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    settings = load_settings()
    if not settings.openai_api_key:
        print(
            "OPENAI_API_KEY is not set -- required to run the orchestrator agent.",
            file=sys.stderr,
        )
        return 1

    if args.command == "run":
        narrative = run_pipeline(args.hospital, args.as_of_date, args.run_id, settings=settings)
        print(narrative)
        return 0

    if args.command == "ask":
        answer, _ = ask_question(args.question, settings=settings)
        print(answer)
        return 0

    return _run_chat_loop(settings)


if __name__ == "__main__":
    raise SystemExit(main())
