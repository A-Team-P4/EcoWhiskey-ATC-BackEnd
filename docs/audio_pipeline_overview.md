# `/audio/analyze` Execution Map

This overview ties the FastAPI endpoint to the modules that implement each stage of the audio analysis pipeline. The code is organised so the folder mirrors the order in which a request travels from upload to the generated controller audio URL.

| Order | Stage | Purpose | Primary module(s) |
| --- | --- | --- | --- |
| 1 | Ingestion | Validate the upload, resolve the MIME type, and load the audio bytes. | `app/pipelines/audio/ingestion.py` |
| 2 | Transcription | Send the bytes to the ASR provider and obtain a transcript. | `app/pipelines/audio/transcription.py` |
| 3 | Session Context | Gather stored scenario data, phase info, and turn history. | `app/pipelines/audio/context.py` |
| 4 | Frequency Guardrails | Check the tuned frequency against the expected bucket. | `app/controllers/audio.py` (`_validate_frequency` block) |
| 5 | Prompt Assembly | Build system/user prompts tailored to the controller role. | `app/pipelines/audio/prompts.py` |
| 6 | LLM Invocation | Call Bedrock/Anthropic and validate the structured response. | `app/pipelines/audio/llm.py` |
| 7 | Persistence & Telemetry | Append student/controller turns, manage transitions, and log. | `app/controllers/audio.py` (`save_turn`, persistence section) |
| 8 | Readback Synthesis | Generate Radio TTS audio and store it for the client. | `app/pipelines/audio/synthesis.py` |

## Quick Navigation

- `app/controllers/audio.py` is the orchestration layer. It wires the FastAPI request to the pipeline helpers and handles HTTP-specific concerns (forms, errors, responses).
- `app/pipelines/audio/__init__.py` re-exports the helper functions per stage, so you can jump straight to `context`, `prompts`, or `llm` without sifting through unrelated logic.
- `app/pipelines/audio/flow.py` contains a lightweight `AudioAnalysisPipeline.describe()` helper, which lists the stages in order if you need a programmatic description.

These changes keep the behaviour identical while making it easier for new contributors to follow the request flow end-to-end.
