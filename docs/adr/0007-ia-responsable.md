# ADR 0007 — Motor de triage: reglas explicables en lugar de LLM

- **Estado:** Aceptado con salvedades
- **Fecha:** 2026-11-18
- **Decisores:** Martín Garrido, Cristóbal Araos, Martín Durán, Alonso Plane
- **Relacionado:** `CHARTER.md`, `docs/arch/atributos-calidad.md`, `docs/threat-model.md`, ADR 0002, ADR 0004, `docs/ia/model-card.md`, `docs/ia/golden-set.json`

## 1. Contexto

El `CHARTER.md` exige que la sugerencia ESI sea **explicable**, no una caja negra, y que la decisión final la tome siempre personal de salud. El NFR de latencia es p95 < 3 s y los datos son sensibles (Leyes 19.628 y 21.719). La S18 evalúa IA responsable con 12 puntos: feature, evaluación, guardrails, model card y marco legal.

Hoy el repositorio no tiene un modelo de lenguaje ni un worker de IA: la sugerencia la calcula `main.py::classify_esi` con reglas deterministas (`rules-v0`). El diseño asíncrono con un servicio de IA aparece en el ADR 0004 y en el C4 L2, pero **no está implementado**. Este ADR documenta la decisión real del MVP y la diferencia con el diseño objetivo.

## 2. Decisión

Mantener `rules-v0` como motor de sugerencia del MVP:

- Función pura `classify_esi(symptoms, vitals) -> (categoría, justificación)` en `main.py`.
- Categoría 1-5 por umbrales de signos vitales y palabras clave de síntomas, con prioridad de la severidad mayor.
- La justificación nombra la razón concreta y termina siempre con «requiere confirmación de la enfermera de triage».
- La enfermera puede confirmar la sugerencia o fijar `manualEsiCategory`; ambas acciones se registran en el audit log.
- Al motor **no** le llegan RUT, nombre ni contacto: solo síntomas y signos vitales.

**Salvedad:** esto es una regla heurística de demostración, **no un criterio clínico validado ni un modelo de IA entrenado**. No se afirma precisión diagnóstica.

## 3. Alternativas descartadas

| Alternativa | Por qué se descartó |
|---|---|
| LLM externo (API de terceros) con prompt con los síntomas | Envía datos clínicos a un tercero sin acuerdo de tratamiento, añade latencia de red imprevisible frente al p95 < 3 s, introduce alucinaciones no reproducibles y no existe presupuesto para su uso en el MVP. |
| LLM local con RAG de guías ESI | Requiere infraestructura con GPU, un corpus con licencia verificada y un pipeline de ingestión; no hay tiempo ni evidencia de que las guías estén autorizadas para redistribución. |
| Modelo ML entrenado con datos históricos de urgencias | No existe dataset etiquetado, no hay consentimiento para usar historial clínico con ese fin y no hay forma de demostrar fairness sin cohortes reales. |
| Score numérico opaco (sin justificación) | Incumple la política de explicabilidad del `CHARTER.md` y la trazabilidad exigida en la defensa. |
| Motor asíncrono con SQS/Lambda (diseño del ADR 0004) | Es el estado objetivo, pero exponerlo en el MVP exigiría broker, base de datos y worker; hoy `main.py` resuelve la sugerencia en el mismo proceso. Se mantiene como roadmap, no como evidencia. |

## 4. Guardrails aplicados

1. **Minimización de datos:** el motor recibe síntomas y signos vitales; la identidad queda en `POST /patients` y se enmascara con `mask_rut` antes de escribir logs (`main.py`).
2. **Validación de entrada:** Pydantic limita rangos de vitales, máximo 50 síntomas y longitud de nombre (`main.py`, modelos `VitalSigns`, `TriageIn`).
3. **Salida acotada:** la categoría siempre está entre 1 y 5; la justificación es determinista y reproducible para la misma entrada.
4. **Humano en el loop:** `confirmedByNurse` o `manualEsiCategory` en `PATCH /triage-evaluations/{id}`; cada cambio genera una entrada de auditoría inmutable (`_audit`).
5. **Sin superficie de prompt injection:** no hay modelo que consuma texto del usuario como instrucción; los síntomas se tratan como datos y se comparan con literales. Si se incorporara un LLM, este ADR debe reabrirse.

## 5. Evaluación

- **Golden set:** 44 casos en `docs/ia/golden-set.json`, derivados de los tests existentes en `tests/test_unit.py`: reglas por nivel, límites exactos, prioridad de severidad y justificación.
- **Script reproducible:** `python docs/ia/evaluate.py` ejecuta el golden set contra `classify_esi` y escribe `docs/ia/evaluation-report.json`.
- **Resultado:** ver `docs/ia/evaluation-report.md`.
- **RAGAS no aplica:** RAGAS mide sistemas con recuperación y generación; aquí no hay LLM ni RAG. Se sustituye por exactitud determinista, cobertura de reglas y pruebas de límites. No se reporta una métrica que el sistema no puede tener.

## 6. Marco legal

- **Ley 19.628:** datos sensibles, consentimiento informado (`consentGiven` en `POST /patients`) y enmascaramiento de PII en logs (`mask_rut`).
- **Ley 21.719:** deber de seguridad y minimización; el motor no recibe datos de identidad.
- **CHARTER.md:** prohibición de caja negra, decisión final humana y auditoría con marca de tiempo.
- **Límite:** no hay todavía una evaluación de fairness por cohorte (edad, sexo, comuna), porque no hay datos reales. Se registra como brecha, no como logro.

## 7. Riesgos y limitaciones

- Las reglas no están validadas clínicamente; pueden sub-clasificar o sobre-clasificar. Mitigación: confirmación obligatoria de la enfermera y fallback manual.
- `symptoms` se compara por subcadena; sinónimos no listados no se detectan. Mitigación: golden set de límites y revisión periódica del vocabulario.
- El estado de las evaluaciones vive en memoria (ver ADR 0008 y el post-mortem); el audit log no es persistente hoy.
- No hay medición de sesgo ni de calidad clínica con datos reales.

## 8. Consecuencias

- Positivo: latencia despreciable, salida reproducible, cero costo de inferencia, explicación auditable y sin PII en el motor.
- Negativo: capacidad clínica limitada; si el producto fuera real, el siguiente paso es un modelo validado con dataset etiquetado, evaluación por cohortes y revisión de este ADR.
