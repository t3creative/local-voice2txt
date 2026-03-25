# Voice2Text — Codebase Audit & External Landscape Review

**Date:** March 23, 2026  
**Scope:** `v2t.py`, `v2t_mobile_server.py`, `v2t_mobile_server_https.py`, `start_v2t.bat`, supporting docs.  
**Purpose:** Identify gaps, inefficiencies, and high-impact improvements; situate the project against recent speech-to-text (STT) tooling and research.

---

## Executive summary

This repository is a **practical, privacy-preserving Windows dictation stack**: local **whisper.cpp** (CUDA) + PyAudio capture + **pynput** injection + optional **Flask** mobile bridge. The core design is sound for a personal tool; the main weaknesses are **operational rigidity** (hardcoded paths, no dependency manifest), **duplication and drift** between desktop and mobile servers, a few **correctness bugs**, and **no first-class streaming or VAD**—patterns that are increasingly standard in 2024–2025 STT ecosystems.

The external landscape has moved toward **faster distilled/large-turbo Whisper variants**, **strong English-only streaming models (e.g. Parakeet-class)**, **tighter VAD integration**, and **better developer packaging**. None of these replace your architecture overnight, but several are **drop-in upgrades** (models, CLI flags, preprocessing) or **incremental** (config file, shared transcription module).

---

## 1. What the codebase does well

| Area | Notes |
|------|--------|
| **Local-first privacy** | Audio stays on-machine; no cloud STT dependency in the main path. |
| **UX for dictation** | Toggle F10, min duration guard, tray indicator, background transcription via thread pool, terminal-aware injection (clipboard vs typing). |
| **Safety-minded injection** | Password-field heuristics, optional blocked apps, chunking, clipboard restore—reasonable for a power-user tool. |
| **Resilience** | Idle watchdog, optional audio reconnect, max recording length, subprocess timeout on whisper. |
| **Mobile bridge** | Flask + CORS + FFmpeg + base64 pipeline is a valid pattern for phone-side capture. |

---

## 2. Critical issues (bugs / correctness)

### 2.1 `ThreadPoolExecutor.shutdown()` — invalid keyword on Python 3.12

```python
self.transcription_pool.shutdown(wait=True, timeout=10)
```

The **`timeout` parameter for `Executor.shutdown()` was added in Python 3.13**. On **Python 3.12** (as in this environment), this call raises **`TypeError: shutdown() got an unexpected keyword argument 'timeout'`** during `cleanup()`, so shutdown may not run cleanly.

**Fix direction:** Use `shutdown(wait=True)` only, or gate `timeout=` on `sys.version_info >= (3, 13)`, or implement a join-with-timeout pattern on the executor’s threads.

### 2.2 Mobile API: `processing_time` is not elapsed time

In `v2t_mobile_server.py`, the JSON response uses `time.time()` at response time, not duration of processing—so the field is misleading for benchmarking or UI.

### 2.3 Mobile UI: touch + click can double-fire

The record button uses both `onclick` and `ontouchstart` calling `toggleRecording()`. On many mobile browsers this can **start and immediately stop** recording. Prefer a single handler pattern (e.g. `pointerdown` / debounce) or only `touchstart` on touch devices.

### 2.4 Mobile blob MIME type vs actual codec

The client builds `new Blob(audioChunks, { type: 'audio/wav' })` while `MediaRecorder` typically emits **WebM/Opus** (or browser-dependent). The server’s ` _detect_audio_format()` often still infers format from bytes—**works when signatures match**, but the MIME label is misleading and can confuse debugging.

### 2.5 HTTPS cert SANs hardcode LAN IPs

`v2t_mobile_server_https.py` embeds specific IPs (`192.168.68.66`, etc.) in the certificate SAN list. That **does not generalize** to other machines and can encourage committing environment-specific certs. Prefer dynamic SAN generation, DNS-only `localhost`, or documented manual steps.

---

## 3. Major gaps and inefficiencies

### 3.1 Configuration and portability

- **Hardcoded paths** to `whisper-cli.exe`, `ggml-base.en.bin`, and (mobile) FFmpeg under Chocolatey.
- **No `requirements.txt` / `pyproject.toml`**—install story is implicit from README and easy to get wrong.
- **Launcher** (`start_v2t.bat`) hardcodes `G:\voice2text`.

**Impact:** High friction for reuse, CI, or a second PC.

### 3.2 Duplicated transcription logic

`_extract_transcription` / `extract_transcription` and whisper CLI invocation are **copy-pasted** between `v2t.py` and `v2t_mobile_server.py`. Any change to whisper output format or flags must be edited twice—**high risk of drift**.

### 3.3 Brittle stdout parsing

Transcription is recovered by **filtering lines** that look like logs. whisper.cpp output changes with version, verbosity, or locale—this is **more fragile** than using structured output when available (e.g. `--output-txt` / JSON-style outputs if supported by your build).

### 3.4 Model choice frozen at `base.en`

`ggml-base.en` is a **reasonable default** for speed, but for heavy dictation use, **larger or “turbo”-style** models (see §5) often materially improve **word error rate** on names, jargon, and short segments—often at acceptable cost on GPU.

### 3.5 No voice activity detection (VAD) or silence trimming

The recorder captures **everything** between toggles, including long silence. That wastes GPU cycles and increases odds of “empty” or hallucinated segments. **VAD** (e.g. WebRTC VAD, silero-vad, or whisper.cpp’s own VAD path where applicable) is a standard upgrade.

### 3.6 Batch-only inference (no streaming)

Architecture is **record → file → whisper**. True **streaming** (partial text while speaking) is not in scope today. For dictation, many users still prefer batch; for **live feedback**, the ecosystem has moved toward streaming-capable models and APIs (§5).

### 3.7 Security posture of the mobile server

- **`0.0.0.0` binding** + **no authentication** on `/api/transcribe` means anyone reachable on the network can POST audio—acceptable on a trusted LAN only.
- **No rate limiting**, **no request size cap** on base64 JSON—DoS or memory pressure risk on a laptop serving the LAN.

### 3.8 Repository hygiene

- `.gitignore` does not list **`voice2text.crt` / `voice2text.key`**—if those are ever regenerated or copied, they could be committed by mistake.
- `__pycache__` / `*.pyc` are not ignored (user has `v2t.cpython-312.pyc` tracked in status as untracked—should be ignored).

---

## 4. Smaller improvements (quality of life)

- **Hotkey conflicts:** F10 is used by some apps (menus). Document or allow rebinding via config.
- **`keyboard` + `pynput`:** Two global-input stacks; sometimes causes edge cases on Windows. Worth documenting if you ever see duplicate events or permission issues.
- **Health check:** `_check_audio_health()` opens a stream; `_perform_health_check` message timing uses a narrow window (`idle_warning_hours + 0.1`)—easy to miss the warning.
- **Internationalization:** `base.en` is English-only; expanding languages means non-`.en` models and possibly language/translate flags.

---

## 5. External landscape (2024–2026) — what changed while this tool stayed stable

This section summarizes **industry and OSS trends** relevant to your stack—not as a mandate to replace whisper.cpp, but to **prioritize** upgrades.

### 5.1 Whisper family: Large v3 **Turbo** (Oct 2024)

OpenAI released **Whisper **large-v3-turbo**—a smaller, faster variant of large-v3** aimed at **much faster inference** with modest quality tradeoffs. It is widely discussed as a **sweet spot** for GPU batch transcription when `base` is too light and `large` is too heavy.

- Useful overview: [Simon Willison — Whisper large-v3-turbo](https://simonwillison.net/2024/Oct/1/whisper-large-v3-turbo-model)
- Hugging Face model card: [openai/whisper-large-v3-turbo](https://huggingface.co/openai/whisper-large-v3-turbo)

**Relevance:** If you convert or obtain **GGUF** (or your build’s format) for whisper.cpp, upgrading the **model file** may be the **single highest ROI** change for accuracy.

### 5.2 Distilled / faster Whisper variants

**Distil-Whisper** and **faster-whisper** (CTranslate2) ecosystems emphasize **throughput** and **lower latency** than reference PyTorch Whisper. Your project bypasses Python inference, but the **same model checkpoints** often appear in **ggml** form for whisper.cpp—so the ecosystem trend is **more efficient models at the same quality tier**.

- [Hugging Face distil-whisper](https://github.com/huggingface/distil-whisper)

### 5.3 Parakeet-class ASR (streaming, English-focused)

**Parakeet** (NVIDIA / NeMo ecosystem) is frequently cited in 2024–2025 comparisons as **very fast** and **streaming-friendly** for English. Integration would **not** be a one-line change for whisper.cpp users—it implies **NeMo / ONNX / TensorRT** or similar runtimes—but it is the **main architectural alternative** if you ever want **sub-second partial results**.

**Relevance:** Compare against your goals: **local privacy**, **minimal deps**, **whisper.cpp**—you may stay on Whisper; Parakeet is for **streaming + throughput** priorities.

### 5.4 whisper.cpp: VAD and streaming still evolving

Upstream **whisper.cpp** continues active work on **VAD** and **streaming** (stdin streaming, VAD edge cases). Staying on a **recent release** and reading release notes beats staying on an arbitrary old binary.

- Releases: [ggml-org/whisper.cpp releases](https://github.com/ggml-org/whisper.cpp/releases)
- Example VAD-related fix discussion: [PR #3230 — VAD processing for skipped segments](https://github.com/ggml-org/whisper.cpp/pull/3230)

**Relevance:** **Rebuild whisper.cpp periodically** and consider enabling **VAD** in CLI if your build supports it—pairs well with your toggle-based capture.

### 5.5 OS-level STT (Windows)

Windows offers **UWP speech recognition** APIs (`Windows.Media.SpeechRecognition`) and **Live Captions** uses on-device processing for captions. These are **not drop-ins** for “inject text into arbitrary Win32 apps” the way you do now, but they matter for **product comparison**: some users get “good enough” dictation from **OS features** without maintaining whisper binaries.

- [Speech recognition (WinRT)](https://learn.microsoft.com/en-us/uwp/api/windows.media.speechrecognition)

---

## 6. Prioritized recommendations

| Priority | Item | Rationale |
|----------|------|-----------|
| **P0** | Fix `shutdown(..., timeout=...)` on Python 3.12 | Prevents broken teardown; verify cleanup path. |
| **P0** | Fix mobile `processing_time` | Correct metrics and UX. |
| **P1** | Add **`requirements.txt`** (pinned versions) + **config file** (paths, hotkey, model) | Portability and fewer edits to source. |
| **P1** | **Single shared module** for whisper invocation + output parsing | Removes duplication; easier upgrades. |
| **P1** | **`.gitignore`** certs/keys and `__pycache__` | Safer git hygiene. |
| **P2** | Evaluate **larger or turbo** Whisper weights in GGUF/GGML for your GPU | Largest accuracy win for dictation. |
| **P2** | Add **VAD** or silence trimming before whisper | Less wasted inference; fewer blank/hallucination outputs. |
| **P2** | Harden mobile server: **auth**, **max body size**, optional **127.0.0.1** bind | Safer default on untrusted networks. |
| **P3** | Mobile UI: single event path for record toggle | Fewer double-trigger bugs on touch. |
| **P3** | Optional **streaming** exploration (different model/runtime) | Only if you need live partial transcripts. |

---

## 7. Relationship to existing `ANALYSIS.md`

The repo already contains **`ANALYSIS.md`** with overlapping themes (hardcoded config, VAD, stdout parsing). This **AUDIT** adds: **verified code issues** (e.g. shutdown API, mobile timing), **security** notes for the Flask server, **repository hygiene**, and a **concise 2024–2026 STT landscape** lens for prioritization. Use **AUDIT** for roadmap and risk; use **ANALYSIS** for the longer internal brainstorming list.

---

## 8. Conclusion

The tool remains a **solid bespoke dictation system** aligned with privacy and universal injection. The highest-impact improvements are **small correctness fixes**, **config + dependency packaging**, **deduplicated whisper pipeline**, and **model / VAD upgrades** informed by current Whisper and whisper.cpp releases. Deeper architectural shifts (streaming Parakeet-class) only matter if your product goals move from “accurate paste after stop” toward “live captions while speaking.”

---

*Generated as part of a codebase review; adjust priorities to match your maintenance budget and threat model (LAN-only vs internet-exposed, etc.).*
