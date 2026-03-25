"""
Shared whisper.cpp subprocess invocation and stdout parsing for voice2text.
Keeps desktop and mobile servers aligned when CLI output or flags change.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

_SKIP_SUBSTRINGS = (
    "whisper_",
    "system_info",
    "main:",
    "load time",
    "mel time",
    "sample time",
    "encode time",
    "decode time",
    "batchd time",
    "prompt time",
    "total time",
    "ggml_cuda_init",
)

_LINE_PREFIXES = ("main:", "system_info:", "whisper_")


def extract_transcription(whisper_output: str) -> str:
    """Extract user-facing text from whisper-cli stdout (strip logs / timing lines)."""
    lines = whisper_output.strip().split("\n")
    transcription_lines = []

    for line in lines:
        lower = line.lower()
        if any(skip in lower for skip in _SKIP_SUBSTRINGS):
            continue
        if line.strip() and not line.startswith("[") and not line.startswith("whisper_"):
            clean_line = line.strip()
            if clean_line and not any(clean_line.startswith(p) for p in _LINE_PREFIXES):
                transcription_lines.append(clean_line)

    transcription = " ".join(transcription_lines)
    transcription = transcription.replace("[BLANK_AUDIO]", "")
    while "  " in transcription:
        transcription = transcription.replace("  ", " ")
    return transcription.strip()


def run_whisper_cli(
    whisper_path: Path,
    model_path: Path,
    audio_path: Path,
    *,
    threads: int = 8,
    timeout: int = 30,
) -> subprocess.CompletedProcess:
    cmd = [
        str(whisper_path),
        "-m",
        str(model_path),
        "-f",
        str(audio_path),
        "-t",
        str(threads),
        "--no-timestamps",
    ]
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout,
        cwd=str(whisper_path.parent),
    )
