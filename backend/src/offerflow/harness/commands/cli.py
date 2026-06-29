"""L8: Command — CLI entry point for deterministic operations."""

from __future__ import annotations

import asyncio
import sys


def main():
    """CLI entry point: `offerflow diagnose <file>`."""
    if len(sys.argv) < 2:
        print("Usage: offerflow diagnose <transcript-file>")
        sys.exit(1)

    command = sys.argv[1]

    if command == "diagnose":
        if len(sys.argv) < 3:
            print("Usage: offerflow diagnose <transcript-file>")
            sys.exit(1)

        filepath = sys.argv[2]
        try:
            with open(filepath, encoding="utf-8") as f:
                transcript = f.read()
        except FileNotFoundError:
            print(f"Error: file not found: {filepath}")
            sys.exit(1)

        asyncio.run(_run_diagnosis(transcript))
    else:
        print(f"Unknown command: {command}")
        print("Available commands: diagnose")
        sys.exit(1)


async def _run_diagnosis(transcript: str):
    from offerflow.harness.skills import DiagnoseTranscriptSkill

    print("Starting diagnosis...")
    skill = DiagnoseTranscriptSkill()

    async def on_progress(event: str, data: dict):
        if event == "splitting":
            print(f"  → {data.get('message', '')}")
        elif event == "split_complete":
            print(f"  → {data.get('rounds', 0)} interview rounds identified")
        elif event == "diagnosing":
            print(f"  → [{data.get('round', 0)}/{data.get('total', 0)}] {data.get('message', '')}")
        elif event == "generating_report":
            print(f"  → {data.get('message', '')}")
        elif event == "complete":
            print(f"  → {data.get('message', '')}")

    skill.on_progress(on_progress)
    result = await skill.execute(transcript=transcript)

    if result.status.value == "completed":
        report = result.data.get("report", {})
        md = report.get("markdown", "")
        output_path = "diagnosis_report.md"
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(md)
        print(f"\nReport saved to {output_path}")
    else:
        print(f"\nDiagnosis failed: {result.error}")
        sys.exit(1)
