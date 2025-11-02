# Crear nuevos escenarios para EcoWhiskey ATC

Esta guía describe, paso a paso, cómo definir un escenario de entrenamiento completamente nuevo sin modificar el código fuente. El audio pipeline ahora depende del manifiesto JSON del escenario y del contexto guardado en la base de datos para hidratar la sesión y dirigir al LLM, de modo que basta con añadir archivos de configuración.

---

## 1. Estructura general

1. Cada escenario vive en `app/resources/scenarios/<escenario>.json`.
2. El `training_context` almacenado en Postgres determina qué escenario se usa cuando el alumno envía audio. El `context` de esa tabla puede fijar:
   - `scenario_id`: id del escenario que se debe cargar.
   - `phase_id` (opcional): fase inicial distinta a la predeterminada.
   - Overrides dinámicos (meteo, frecuencias, transponder, etc.).
3. `fetch_session_context` combina el escenario base, los overrides y el histórico de turnos para construir la “verdad” operativa por sesión. No es necesario reiniciar servicios tras añadir o modificar JSON, pero sí recargar el proceso si está empaquetado (p.ej., en producción con workers que cachean recursos al inicio).

---

## 2. Campos obligatorios del JSON

```jsonc
{
  "id": "mrpv_vfr_departure",          // identificador único (snake_case recomendado)
  "display_name": "MRPV VFR salida",   // etiqueta amigable (se usa en UI/logs)
  "airport": "MRPV",                   // ICAO o identificador del aeródromo
  "default_phase": "ground_departure", // fase con la que arrancará la sesión
  "frequencies": {                     // valores base por grupo (se usan para mapear 121.7→ground, etc.)
    "ground": "121.7",
    "tower": "118.3"
  },
  "shared": { ... },                   // información común disponible para todas las fases
  "phases": [ ... ]                    // lista ordenada de fases
}
```

### `shared`

Este bloque agrupa datos que pueden reutilizarse en cualquier fase. No existen claves obligatorias, pero los campos convencionales incluyen:

- `student`: datos de la aeronave/operador (callsign, ruta, almas, autonomía, etc.).
- `meteo`: condiciones, QNH, viento… se mezclarán con lo que venga de Postgres si existe.
- `objectives`: lista de objetivos pedagógicos.

Cualquier valor presente en `training_context.context` sobrescribirá lo definido en `shared`. Por ejemplo, si el alumno selecciona otro QNH en el panel, `fetch_session_context` añadirá esa lectura a cada fase automáticamente.

---

## 3. Definir fases

Cada fase representa un tramo de la conversación (llamada inicial, readback, autorización, etc.). Las fases se almacenan como objetos dentro del array `phases` y **deben** tener las siguientes claves mínimas:

```jsonc
{
  "id": "ground_departure_request", // identificador único dentro del escenario
  "name": "Solicitud de apertura de plan de vuelo",
  "frequency": "ground",            // coincide con las llaves de frequencies (ground, tower, approach…)
  "intent": "ground_taxi_clearance",// intent esperado por la fase
  "transitions": {                  // reglas (ver siguiente sección)
    "onSuccess": "ground_readback"
  },
  "llm": { ... },                   // instrucciones dirigidas al LLM
  "data": { ... }                   // payload operativo que el LLM puede usar
}
```

### 3.1. Transiciones

- `onSuccess`: indica a qué fase moverse cuando el LLM responde con `metadata.nextPhase = "<fase>"`.
- Puedes añadir otras claves (e.g. `onFailure`) para documentar rutas alternativas; el backend siempre delega en el LLM: si el modelo decide cambiar de fase, debe incluir `metadata.nextPhase` en la respuesta.

### 3.2. Bloque `llm`

Esta sección guía al modelo sobre qué validar, cómo responder y cuál es el objetivo de la fase. Los campos más útiles son:

| Campo                 | Uso principal                                                                                                   |
|-----------------------|------------------------------------------------------------------------------------------------------------------|
| `role`                | Reemplaza el prompt base. Define explícitamente quién es el modelo (“Eres Pavas Torre…”)                         |
| `studentChecklist`    | Lista (o texto) con los elementos que el alumno debe incluir. Aparece como checklist en el prompt.               |
| `controllerChecklist` | Pasos esperados en la respuesta del controlador.                                                                |
| `allowResponseRules`  | Criterios para decidir si `allowResponse` debe ser `true` o `false`.                                            |
| `feedbackGuidance`    | Consejos sobre cómo redactar el feedback.                                                                       |
| `notes`               | Observaciones adicionales (cambios de fase, recordatorios de fraseología, etc.).                                |

Todos los campos son opcionales, pero mientras más detalle se incluya, más consistente será la retroalimentación generada.

### 3.3. Bloque `data`

Esta sección entrega datos operativos que el LLM puede citar en sus respuestas o validar en los readbacks. No hay una estructura rígida; algunos ejemplos comunes:

- `controller_callsign`, `runway`, `runway_human`
- `wind_direction`, `wind_speed`, `qnh`, `squawk`
- `taxi_route`, `advisory`, `climb_instruction`, `report_altitude_ft`, etc.
- `expected_items`: lista de elementos que el alumno debe mencionar (p. e. para readbacks).

El backend incluye este bloque completo en el prompt (`phase` ⇒ JSON), por lo que el LLM tiene acceso al detalle exacto.

---

## 4. Asociar el escenario a una sesión

1. Crea (o actualiza) la fila en `training_context` usando el endpoint `POST /training_context/` desde la consola de pruebas o cualquier cliente autorizado. Ejemplo:

```json
{
  "context": {
    "scenario_id": "mrpv_vfr_departure",
    "meteo": {
      "qnh": "3005",
      "wind": "080/12"
    },
    "transponder": "0522",
    "route": "MRPV-MRPV",
    "objectives": ["phraseology_focus"]
  }
}
```

2. Guarda el `trainingSessionId` que devuelve la API; ese identificador se usará en el `session_id` del endpoint `/audio/analyze`.
3. Opcional: actualiza otros campos del contexto durante la sesión (p. ej. cambiar a la fase siguiente manualmente) usando el mismo endpoint o el `PATCH` equivalente si está expuesto en tu build.

---

## 5. Flujo recomendado para crear un escenario nuevo

1. **Diseña las fases en papel**: define qué bloques de conversación existen, requisitos del alumno y respuestas del controlador.
2. **Crea el manifiesto** en `app/resources/scenarios/<id>.json` siguiendo el formato anterior. Usa `mrpv_vfr_departure.json` como referencia.
3. **Incluye todo lo configurable** en JSON: destinos, pistas, rutas de taxi, checklists, reglas de feedback. La meta es no tocar código para un nuevo aeropuerto o maniobra.
4. **Actualiza (o añade) documentación de entrenamiento** para los instructores si es necesario.
5. **Carga un `training_context`** apuntando al nuevo escenario y validando metadatos (frecuencias, meteo, etc.).
6. **Prueba end-to-end** con `test_console.py`:
   - Selecciona/crea el `training_session_id`.
   - Asegúrate de que la primera respuesta del controlador corresponda a la fase inicial.
   - Verifica que `metadata.nextPhase` aparezca cuando la fase se complete y que el backend cambie de fase automáticamente.
7. **Itera sobre el JSON** si detectas ajustes en el feedback o en los datos operativos. No necesitas reiniciar la aplicación si se está ejecutando en modo de desarrollo.

---

## 6. Buenas prácticas

- **Reutiliza estructuras**: si varios escenarios comparten fases (p. ej., readback de taxi), copia el bloque y solo ajusta `data` / checklists necesarios.
- **Incluye nombres humanos** en `runway_human` (ej. “uno cero”) para que el LLM pueda usar fraseología natural sin deducirla.
- **Mantén `metadata` predecible**: decide una convención clara (ej. `nextPhase`, `missingItems`, `notes`). El controlador registra la respuesta completa (`llm_raw`) para auditoría, así que es sencillo depurar.
- **Versiona tus escenarios**: describe cambios relevantes en el repositorio (commit message o changelog interno) para saber cuándo y por qué se actualizaron checklists.
- **Aprovecha overrides**: si un escenario necesita variar QNH/viento en tiempo real, basta con actualizar `training_context.context.meteo` sin tocar el JSON de base.
- **Valida en audio**: aunque el JSON se vea correcto, prueba con grabaciones reales o sintetizadas; la entonación puede afectar la transcripción y, por tanto, la respuesta del LLM.

Con esta estructura, crear una nueva misión (p. ej., un aterrizaje en otro aeropuerto o un escenario IFR) consiste únicamente en definir las fases y su guía pedagógica dentro de un nuevo archivo JSON y apuntar la sesión a ese escenario. No es necesario modificar controladores, pipelines ni prompts base.

