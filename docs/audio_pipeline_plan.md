# Audio Pipeline & LLM Integration Plan

This document captures the detailed design for the next iterations of the `/audio/analyze` pipeline as we integrate conversational LLM behaviour, structured feedback, and richer context management. It expands the earlier brainstorming so we can track scope, dependencies, and open questions.

## Goals

- Deliver a Spanish-language ATC training experience grounded in Costa Rican procedures, centred on Tobías Bolaños International Airport (MRPV) in San José.
- Enable student pilots at Costa Rican flight schools to practise complete flights end-to-end (clearance delivery, taxi, take-off, frequency transitions, en-route vectors, approach, landing, and taxi-in).
- Introduce controlled randomness (runway assignments, taxi routes, pattern direction, clearance outcomes, approach types) so repeated sessions remain realistic yet varied.
- Ensure the conversational agent behaves like a Costa Rica-based ATC controller, using accurate local airspace data and phraseology.
- Validate student radio calls against the correct frequency and intent (e.g., landing clearance should reach Tower).
- Generate deterministic, intent-specific controller responses using an LLM plus templated stencils.
- Produce structured feedback on readbacks, phraseology, and procedural correctness.
- Persist and reuse per-session context so the LLM understands prior exchanges (co-lation).
- Provide observability, testability, and operational safeguards for the end-to-end pipeline.

## High-Level Flow

1. **Audio Upload** – Client submits session ID, tuned frequency, and MP3/M4A audio.
2. **ASR** – Amazon Transcribe (or fallback) returns the transcript.
3. **Context Fetch** – Load session metadata, scenario state, and prior turns.
4. **Frequency / Intent Validation** – Decide whether the request matches the configured intent/frequency.
5. **Prompt Assembly** – Combine transcript, context, stencils, and rubric prompts.
6. **LLM Execution** – Call the provider to obtain structured response + slot fillings.
7. **Stencil Rendering** – Fill the response template with LLM output; fall back sensibly.
8. **Feedback Evaluation** – Run rubric checks, build student feedback payload.
9. **TTS** – Polly (Radio FX) renders the controller response; store in S3.
10. **Persistence & Telemetry** – Append turn history, log metrics, emit traces.

> **Training Setting**
> - **Idioma**: Español, con fraseología aeronáutica costarricense.
> - **Base primaria**: Aeropuerto Tobías Bolaños Internacional (MRPV – Pavas).
> - **Relación con MROC**: Pavas es un aeródromo secundario enclavado dentro del CTR de San José (COCO). Está a pocos kilómetros del Aeropuerto Internacional Juan Santamaría (MROC), por lo que las salidas y llegadas suelen coordinarse rápidamente con COCO Aproximación tras contactar Torre Pavas (y viceversa en la llegada).
> - **Cobertura de espacio aéreo**: Sectores controlados costarricenses (Torre, Superficie, COCO Aproximación/Control, radio, emergencia) con sus frecuencias reales.
> - **Datos necesarios**: Pistas, calles de rodaje, patrones de tráfico, puntos de notificación, restricciones de altitud y climatología local; estos datos deben alimentar prompts, reglas y estocasticidad.
> - **Escenarios activos**:
>   - `app/resources/scenarios/mrpv_vfr_departure.json` — flujo abreviado hasta la autorización de despegue (baseline).
>   - `app/resources/scenarios/mrpv_coco_approach.json` — práctica focalizada en COCO Aproximación.
>   - `app/resources/scenarios/mrpv_full_flight.json` — recorrido completo Superficie → Torre → COCO Aproximación/Radio → UNICOM → regreso y aterrizaje en Pavas.
> - **Experiencia estudiantil**: El sistema debe permitir simular un vuelo completo, incluyendo solicitudes de autorización de rodaje, despegue, transiciones de frecuencia, vectores radar, entradas a patrón, autorizaciones de aterrizaje y taxi a plataforma, siempre con retroalimentación sobre colación y fraseología.

### Demo Scenario (Primer Incremento)

- **Entrada del alumno**: “Pavas torre, Alfa noviembre india, listo en punto de espera.”
- **Frecuencia evaluada**: 118.300 MHz (Torre MRPV). La validación rechaza frecuencias distintas con mensaje guía.
- **Intento inferido**: `tower_takeoff_clearance`.
- **Respuesta esperada**: “Alfa noviembre india, autorizado a despegar pista uno cero.”
- **Extracción de indicativo**: Se admite deletreo NATO (Alfa, Noviembre, India) y regresa `ANI` para poblar la plantilla.
- **Plantilla**: Stencil determinista con pista predeterminada “uno cero”; futura versión podrá variar pista según condiciones del escenario.
- **Evolución planeada**: El LLM entregará JSON estructurado con slots (`callsign`, `callsign_spelled`, `runway`, `instruccion`, etc.) y la plantilla renderizará siempre la frase final; nunca se enviará texto libre del modelo a Polly.
- **Conversión fonética**: `callsign_spelled` se derivará del LLM (o de utilidades NATO) para pronunciar siempre el indicativo completo (“Alfa Noviembre India”), incluso si `callsign` abreviado es `ANI`.

## Core Modules

### Session Context Store

- **Purpose**: Single interface to read/write training session state.
- **Responsibilities**:
  - Persist `TrainingContext` + turn history (transcript, intent, feedback, timestamps).
  - Provide context windows tailored for LLM prompts (recent N turns, key facts).
  - Cache hot sessions (Redis/in-memory) while keeping Postgres authoritative.
- **Implementation notes**:
  - Add `TrainingContext` import to `app/models/__init__.py` so metadata registers.
  - Consider `training_turns` table with JSON payload for extensibility.
  - Provide async repository helpers (`get_context(session_id)`, `append_turn(...)`).
  - Current baseline: `POST /training_context/` (`app/controllers/training_context.py`) creates a `TrainingContext` row with a generated `training_session_id`, the authenticated user, and the initial context payload supplied at session start. Any turn repository should build on this record by linking via `training_session_id`.
  - Session bootstrap now randomises per-flight parameters (squawk 05xx, viento, QNH, taxi-route) when absent and stores them in context so readback validation has consistent values.

### Frequency Intent Validator

- **Purpose**: Confirm the user’s request aligns with the expected frequency/intent.
- **Inputs**: Transcript text, selected frequency, session context (current phase, scenario), rubric rules.
- **Outputs**: `FrequencyValidationResult` with `is_valid`, `intent`, `reason`.
- **Details**:
  - Actualmente se valida comparando la frecuencia ingresada con la fase activa y sus reglas declarativas; los mensajes de error se construyen en el controlador de audio.
  - Start with deterministic rules keyed by training scenario (e.g., runway operations).
  - When rules are inconclusive, optionally escalate to the LLM en modo de clasificación.
  - Surface actionable `reason` strings for the UI and logs (e.g., “Runway taxi requests must be on Ground 121.7”).
  - Log every decision for auditing and to refine rules.

### Intent Response Generator

- **Purpose**: Produce the controller’s spoken response via an LLM + stencils.
- **Responsibilities**:
  - Build `LlmRequest` (prompt, instructions, context snippets, frequency/intent metadata).
  - Invoke the LLM using the transport client (streaming or JSON mode).
  - Parse the provider output (JSON/tool call), validate required fields, and fill stencils.
  - Support local mock mode for tests (fixture returns deterministic payload).
  - `extract_intent_slots` llena campos clave (indicativo, pista activa) combinando transcriptos con el perfil del aeropuerto antes de renderizar la plantilla.
  - Implementación actual: Amazon Bedrock (`bedrock-runtime`) con modelo `settings.bedrock.model_id`; se pasa un prompt controlado y se espera una frase única (fallback al stencil cuando la llamada falla).
  - Valida que la respuesta inicie con el indicativo esperado; si no, se recurre a la plantilla determinista para garantizar la colación correcta.
  - Verify generated instructions remain consistent with real Costa Rican procedures (frequencies, altitudes, pistas activas) before sending to TTS.
- **Próxima iteración importante**:
  - Pedir al LLM que devuelva JSON estricto (`intent`, `slots`, `feedback`) en lugar de texto libre.
  - Validar el JSON (schema, tipos, campos obligatorios) y poblar la plantilla con los slots resultantes (`callsign`, `callsign_spelled`, `runway_human`, `instructions`).
  - Rechazar/registrar cualquier payload inválido y caer al stencil determinista para mantener fraseología consistente.
  - Permitir overrides puntuales (p.ej. vector radar) definiendo campos opcionales por intent.
- **Stencil storage**:
  - Keep canonical stencils in `app/resources/stencils/<intent>.json` or a DB table for runtime edits.
  - Include metadata like required slots, default text, language, voice hints.
  - Encode regional phraseology (e.g., “COCO Aproximación”, “mantenga patrón izquierdo pista 10”) so generated responses sound authentic to Costa Rican ATC.

#### Contrato estructurado LLM → Plantilla

- **Motivación**: evitar respuestas libres («ANI…») y garantizar fraseología estandarizada. El LLM funciona como extractor enriquecido; la plantilla siempre produce la frase final.
- **Formato esperado** (JSON estricto, sin texto adicional):

  ```json
  {
    "intent": "tower_takeoff_clearance",
    "confidence": 0.82,
    "slots": {
      "callsign": "ANI",
      "callsign_spelled": "Alfa Noviembre India",
      "runway": "10",
      "runway_human": "uno cero",
      "instruction_code": "takeoff_clearance"
    },
    "notes": {
      "observations": ["Alumno omitió viento"],
      "missing_information": []
    }
  }
  ```

- **Validación**:
  - `intent` debe existir en el catálogo (`audio/intents_registry.json`).
  - `confidence` ∈ [0, 1].
  - `slots.callsign` coincide con `[A-Z0-9]{2,6}`.
  - `slots.callsign_spelled` utiliza alfabeto OTAN (`app/resources/reference/nato_alphabet.json`).
  - `runway` pertenece a `airport_profile.runways` y `runway_human` corresponde a su forma hablada.
  - `instruction_code` se valida contra el mapa `intent_instruction_catalog`.
- **Renderizado**: el LLM entrega `controllerText` y `feedback` listos para voz; no usamos un motor adicional de plantillas por ahora.

  ```python
  RenderedPhrase(
      text="Alfa Noviembre India, autorizado a despegar pista uno cero",
      slots=slots,
      template_id="tower_takeoff_clearance"
  )
  ```

- **Fallbacks**:
  1. JSON inválido → registrar error + usar plantilla con datos mínimos (p. ej. `callsign_spelled` derivado localmente).  
  2. Slots incompletos → intentar completar (`callsign_spelled` vía conversión), en caso contrario, fallback determinista.  
  3. Intent desconocido → `FrequencyValidationResult.intent` mantiene valor original para trazas, pero se responde con mensaje genérico (“Solicitud recibida, mantenga posición”) hasta revisar el intent.

- **Telemetría**: registrar `llm_contract_valid` (bool), `llm_slots_missing` (lista) y `llm_fallback_reason` para monitoreo.

### Student Feedback Evaluator

- **Purpose**: Grade the student’s transmission before sending the controller readback.
- **Responsibilities**:
  - Check call-sign echo, readback completeness, mandatory phraseology, safety violations.
  - Combine deterministic rubric rules with optional LLM critique mode.
  - Output structured feedback object (scores, comments, next steps) for the API response.
  - Feed analytics dashboards with rubric outcomes to track learner progress.
  - Validate Costa Rican phraseology standards and highlight deviations (colación incompleta, orden de palabras incorrecto, omisión de “COCO”, etc.).

### Prompt Orchestration

- **Purpose**: Central place to assemble prompts and instructions.
- **Responsibilities**:
  - Merge system message, scenario description, last N turns, frequency guardrails, stencil hints.
  - Version prompts and support A/B testing (hash prompt content for telemetry).
  - Accept tuning knobs (temperature, max tokens) via configuration.
  - Provide snapshot testing to catch accidental prompt regressions.

#### Prompt Builder Detallado

- `PromptContext` (pydantic):
  ```python
  class PromptContext(BaseModel):
      frequency_group: Literal["tower", "ground", "approach", "radar"]
      airport: str
      runway_conditions: str | None
      weather_snippet: str | None
      recent_turns: list[str]
      expected_slots: list[str]
  ```
- **System prompt** por `frequency_group` (ejemplos):
  - Torre (`tower`): enfatiza autorizaciones, pistas activas, mantiene fraseología de torre.
  - Superficie (`ground`): instrucciones de rodaje, uso de taxiways, espera en puntos holding.
  - Aproximación (`approach`/`radar`): vectores, niveles, transferencias a otras dependencias.
- **User prompt**: incluye transcript, resumen de contexto (`PromptContext`), lista de slots esperados y ejemplo de output (formato JSON). Se añade cláusula “responde únicamente en JSON válido”.
- **Versionado**: `prompt_hash = sha256(system + user + intent + model_id)` para trazabilidad; guardar en telemetría y en tabla de turnos.
- **Pruebas**: snapshoteo del prompt completo por frecuencia para detectar cambios accidentales antes de liberar.

### LLM Transport Client

- **Purpose**: Provider-agnostic wrapper for Bedrock/OpenAI/etc.
- **Responsibilities**:
  - Handle auth, retries with exponential backoff, timeouts, and rate limits.
  - Expose streaming + JSON response modes with consistent return type (`LlmResponse`).
- **Guardrails**:
  - Enforce token budgets; truncate long transcripts before sending.
  - Sanitize LLM output (untrusted JSON, profanity) before downstream use.
  - Emit rich telemetry (latency, model ID, prompt hash).

### Rule Engine & Rubric Checks

- **Purpose**: Modular set of validators used by both frequency validation and feedback.
- **Responsibilities**:
  - Provide reusable checks (e.g., `requires_phrase("ready for departure")`).
  - Support composable rule sets per scenario/intent.
  - Produce machine- and human-readable findings for report generation.
  - Capture Costa Rica-specific requirements (puntos de notificación, uso de QNH/QNE, indicaciones de COCO, patrones izquierdos/derechos obligatorios).
  - Plan futuro: reemplazar reglas textuales extensas (stopwords, regex complejas) por extracción basada en LLM + validaciones deterministas (ej. `runway` ∈ pistas permitidas), evitando crecimiento exponencial del código.

### Telemetry & Audit Logging

- **Purpose**: Observability across every turn.
- **Responsibilities**:
  - Record prompt hash, model version, latency, rubric scores, intent decisions.
  - Link telemetry to `training_session_id` for debrief dashboards.
  - Feed alerts when failure rates spike (e.g., ASR or LLM outages).
  - Ensure logs redact PII and comply with training privacy requirements.
- **Implementación de logs**:
  - `logs/app.log`: eventos generales de la aplicación (rotación 1 MB, 5 backups).
  - `logs/audio_pipeline.log`: flujo específico del pipeline (rotación 500 KB). Contenido esperado por request (en orden):
    1. Intent detectado + tokens.
    2. LLM request metadata (frecuencia, slots preliminares, prompt hash).
    3. Respuesta cruda truncada (`raw_json`).
    4. Resultado del parser (`structured_slots`).
    5. Plantilla aplicada / fallback con motivo.
  - Librerías ruidosas (`botocore`, `urllib3`, `sqlalchemy.engine`) forzadas a nivel WARNING.
  - Feature flag `AUDIO_PIPELINE_LOG_LEVEL=DEBUG` permite activar trazas de bajo nivel al diagnosticar incidentes.
- **Métricas clave** (Prometheus):
  - `audio_pipeline_llm_contract_failures_total{intent}`.
  - `audio_pipeline_fallback_total{reason}`.
  - `audio_pipeline_render_duration_seconds` (histograma).

### Scenario & Curriculum Manager

- **Purpose**: Track learner objectives and gate available intents.
- **Responsibilities**:
  - Define scenario metadata (phase, allowed intents, expected frequencies).
  - Unlock new intents as the student progresses; present to validator + prompt builder.
  - Store expected controller responses for offline evaluation and rubric comparisons.
  - Manage randomness knobs (pista activa, rodajes alternativos, autorizaciones condicionales, patrones izquierdos/derechos, aproximaciones cortas/largas) to keep training varied yet plausible para MRPV y el espacio aéreo circundante.

### Evaluation Playground

- **Purpose**: Offline harness for regression testing and prompt iteration.
- **Responsibilities**:
  - Replay captured transcripts through the pipeline with canned responses.
  - Compare outputs against gold stencils; produce diff reports.
  - Allow prompt engineers to tweak instructions safely before production rollout.

### Fallback & Resilience Utilities

- **Purpose**: Keep training sessions running during partial outages.
- **Responsibilities**:
  - Detect ASR/LLM/TTS failures; switch to cached or rule-based responses.
  - Queue work for later reprocessing when providers recover.
  - Expose degraded-mode indicators via API so the UI can warn students.

### Configuration & Feature Flags

- **Purpose**: Manage environment-specific behaviour and rapid toggles.
- **Responsibilities**:
  - Extend `app.config.settings` with LLM provider keys, model IDs, mock modes.
  - Integrate remote flag service (e.g., LaunchDarkly) or env-driven toggles.
  - Allow quick rollback to previous stencil/prompt versions.

## Data & Storage Considerations

- Ensure `TrainingContext` is registered with SQLAlchemy metadata and covered by migrations.
- Add `training_turns` table with references to `training_session_id`, storing:
  - Student transcript, selected frequency, inferred intent.
  - Controller response text, stencil ID, audio S3 key.
  - Feedback scores, rubric findings, timestamps.
- Consider TTL caches or Redis for hot session context; persist back to Postgres on completion.
- Curate airport and airspace datasets (MRPV layouts, frecuencias COCO, puntos de notificación, procedimientos IFR/VFR) in YAML/JSON so prompts, randomness engines, and validators consume authoritative information.
- Mantener perfiles de aeropuertos (`app/resources/airports/*.json`) con pistas activas por defecto y frecuencias primarias para alimentar extracción de slots y validaciones.
- Version stencils and prompts; store revision IDs alongside turn records for replay fidelity.
- Centralise shared reference data (e.g., NATO alfabeto, frecuencias por estación) under `app/resources/**` to keep service logic free of literals.
- Asegurar la ingestión segura de credenciales (incluyendo `BEDROCK_API_KEY` codificada en base64) y registrar si el cliente Bedrock usa API key o credenciales IAM para diagnósticos.

## Testing Strategy

- **Unit**: 
  - Rule engine, prompt builder, stencil renderer, JSON parser.
- **Integration**:
  - Mocked ASR/LLM/TTS to cover `/audio/analyze` happy path (`tests/test_audio.py` foundation).
  - Snapshot tests for `LlmRequest` payload and parsed responses.
- **Contract / Schema**:
  - Fixtures con respuestas LLM válidas/erróneas (`tests/data/llm_responses/*.json`).
  - Pruebas que aseguren errores claros cuando faltan slots (`pytest.raises(ValidationError)`).
- **End-to-end controlado**:
  - Simular turnos completos (solicitud de taxi → despegue → transferencia) con mocks deterministas.
  - Guardar `RenderedPhrase.text` y verificar que la fraseología coincide con el catálogo.
- **Regresión de plantillas**:
  - Snapshot por plantilla (`tests/snapshots/templates/*.txt`) para detectar cambios accidentales en fraseología.
- **Offline Regression**:
  - Evaluation playground runs nightly suites on recorded sessions.
- **Manual QA**:
  - Notebooks to visualize rubric scores and iterate on prompts/stencils.

## Observability & Ops

- Add structured logging (`training_session_id`, `intent`, `model_id`, `prompt_hash`).
- Surface metrics (success rates, latency, rubric failure counts) via Prometheus.
- Implement tracing (OpenTelemetry) to follow ASR → LLM → TTS spans.
- Provide admin tooling to replay problematic turns and inspect raw prompts/responses.
- Registrar en logs cada fase clave (detección de intento, slots, payload al LLM, respuesta cruda y fallback) para acelerar diagnósticos.
- Persistir registros humanos en `logs/app.log` (rotación por tamaño con respaldos) para facilitar revisiones y debriefs sin depender de stdout.
- Registrar solo la señal relevante del pipeline en `logs/audio_pipeline.log` y enviar librerías ruidosas (botocore, urllib3, SQLAlchemy) a nivel WARNING para que los archivos sean legibles.
- El objetivo final es que el LLM produzca un payload estructurado, no frases libres; la plantilla garantizará fraseología consistente y será la única fuente para Polly.

## Security & Compliance

- Redact sensitive data (student identifiers) in logs and telemetry exports.
- Store all transcripts and LLM responses under compliance-controlled buckets.
- Audit access to session context, especially when storing historic transcripts.
- Support data deletion requests by purging session history across DB/S3/cache.
- Verify third-party LLM providers can ingest Spanish aviation data under Costa Rican privacy agreements before production rollout.
- Al persistir respuestas LLM (JSON), asegurar cifrado en reposo y control de acceso fino (solo equipo ML / QA). Registrar versión del contrato JSON y del modelo para auditorías.
- Desacoplar claves (IAM o API key) por entorno y rotarlas periódicamente; documentar procedimiento de revocación inmediata.

## Implementation Roadmap (Status)

- ☐ Wire `TrainingContext` into metadata; diseñar `training_turns` y repositorios dedicados.
- ✅ Implementar Frequency Intent Validator con reglas + fallback LLM (incluye bloqueo por frecuencia incorrecta).
- ✅ Construir repositorio de plantillas, orquestador de prompts y validar via snapshots.
- ☐ Añadir toggles/mock al cliente LLM y servicios externos para modo offline.
- ☐ Expandir `IntentResponseGenerator` y `StudentFeedbackEvaluator`; integrarlo con el controlador.
- ☐ Añadir telemetría operativa, feature flags y lógica de fallback más rica (métricas Prometheus).
- ☐ Levantar evaluation playground + suites de regresión.
- 🟡 Iterar en rúbricas/plantillas con datos reales (en progreso inicial con escenario MRPV).
- ✅ Migrar a contrato LLM→JSON estructurado + validación centralizada de plantillas.
- ✅ Diferenciar prompts por `frequency_group` para soportar torre/superficie.
- ✅ Implementar `response_contract`, `prompt_builder` y ajustar `call_conversation_llm` para que Polly reciba solo frases renderizadas por el LLM.
- ☐ Añadir pruebas de contrato/snapshots automáticas y telemetría (`llm_contract_valid`, `llm_fallback_reason`).

### Next Steps

**Completado recientemente**
- Validar frecuencia/intención y bloquear respuestas en canal incorrecto.
- Ampliar reglas de intentos ground/tower y cargar escenario determinista desde JSON.
- Enriquecer el contrato de slots y normalización con viento, QNH, squawk, taxi_route, etc.
- Renderizar plantillas multi-frase usando secuencias `instruction_codes`.

**Pendiente inmediato**
1. **Instrumentación y observabilidad**  
   - Exponer métricas (`audio_pipeline_frequency_mismatch_total`, `llm_contract_valid_total`, `template_fallback_total`, `render_duration_seconds`).  
   - Añadir logs estructurados con `prompt_hash`, `scenario_id`, `instruction_codes` para diagnósticos.

2. **Persistencia detallada de turnos**  
   - Crear tabla `training_turns` y actualizar `append_turn` para reflejar cada intercambio con slots, fallback y audio generado.  
   - Guardar el estado del escenario (p.ej. fase ground → tower) para que próximos turnos conozcan la fase activa.

3. **Tests y fixtures de regresión**  
   - Añadir pruebas unitarias/snapshot que reproduzcan el guion completo (“Apertura y rodaje…” + “Punto de espera y salida…”).  
   - Crear fixtures LLM mock (`tests/data/llm/`) y conectar el evaluation playground cuando exista.

4. **Modo mock y toggles**  
   - Incorporar flags de settings para forzar Bedrock/Transcribe simulados y documentar el procedimiento en README/Runbook.

5. **Student Feedback & Rubrics**  
   - Definir rubric rules (call-sign echo, readback completo, fraseología correcta, uso de QNH/QNE) y exponer un puntaje + comentarios accionables.  
   - Integrar la evaluación antes de sintetizar Polly, de modo que el payload API entregue `controller_response` y `feedback` diferenciados.  
   - Añadir métricas (`audio_pipeline_feedback_score`) y logs con los hallazgos principales para analytics.

6. **Estrategia de contexto prolongado**  
   - Persistir resúmenes o turnos clave para que la detección de intentos use historial (no solo el transcript actual).  
   - Diseñar transición automática de fase (ground → tower → departure) basada en intentos detectados y estado del escenario.

7. **QA de fraseología costarricense**  
   - Programar sesiones de revisión con instructores locales para vetar cada plantilla y conjunto de slots.  
   - Registrar observaciones y acciones en un backlog compartido; actualizar prompts/plantillas con el feedback.  
   - Establecer checklist de lanzamiento que incluya validación bilingüe ASR+LLM+TTS sobre los flujos de rodaje y despegue.

## Open Questions

- Which LLM provider(s) will we launch with? (Bedrock vs. OpenAI vs. self-hosted).
- How large should the context window be, and do we chunk or summarize older turns?
- Do we require human review for rubric failures above a severity threshold?
- Where do scenario definitions live (YAML, DB, CMS), and who owns updates?
- What is the SLA for degraded mode before we abort a session?
- How do we incorporate GIS-aware data (VRPs, fixes, terrain cautions) so vectors and patterns remain geographically accurate?
- What bilingual QA process ensures ASR + LLM outputs adhere to Costa Rican Spanish phraseology before wider rollout?
- How do we seed and log randomness so instructors can replay or audit a specific “random” session during debrief?
- Which UX patterns do we use when the pipeline low-confidence marks a student call (graceful fallback messaging vs. retry prompts)?
- What is the extensibility plan for onboarding additional Costa Rican airports (data schema, intent catalog, rule packs) without major refactors?
- ¿Cómo versionamos prompts/plantillas/LLM-config para auditar cambios en fraseología y mantener reproducibilidad en sesiones pasadas?
- ¿Cuál es la secuencia exacta para el “happy path” (apertura de plan → rodaje → punto de espera → autorización → despegue) y cómo garantizamos que el contexto persistido permita al LLM interpretar la fase correcta?

Keeping this document updated alongside implementation will ensure the team has a single source of truth for the evolving audio + LLM pipeline.
- **LLM → JSON → Plantilla (Diseño futuro inmediato)**:
  - **Prompt dinámico**: construir un mensaje de sistema basado en `frequency_group` (torre, superficie, aproximación). Ejemplo: torre de MRPV vs. COCO Aproximación. Evitar mensajes genéricos (“siempre torre”) para soportar múltiples fases.
  - **Formato de salida**: exigir `application/json` con estructura establecida:
    ```json
    {
      "intent": "tower_takeoff_clearance",
      "confidence": 0.82,
      "slots": {
        "callsign": "ANI",
        "callsign_spelled": "Alfa Noviembre India",
        "runway": "10",
        "runway_human": "uno cero",
        "instruction": "Autorizado a despegar pista uno cero"
      },
      "notes": {
        "frequency_group": "tower",
        "observations": ["Alumno omitió viento"]
      }
    }
    ```
  - **Validación**: usar `pydantic`/schema para validar y normalizar; si falla, registrar el payload, reportar telemetría y usar fallback determinista.
  - **Plantillas**: cada intent tiene un template (YAML/JSON) con placeholders y metadatos (ej. requiere `callsign_spelled`). Rellenar siempre desde `slots` validados; el texto devuelto por el LLM no se enviará a Polly directamente.
  - **Expansión**: permitir que la plantilla reciba también `instruction_code` (ej. `line_up_and_wait`, `vector_heading`) para mapear a fraseología canónica.
