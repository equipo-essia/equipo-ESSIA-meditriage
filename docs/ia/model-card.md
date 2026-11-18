# Model card — Motor de sugerencia ESI `rules-v0`

**Versión:** 1.0 · **Fecha:** 2026-11-18 · **Responsable:** Cristóbal Araos (Tech Lead)
**Estado:** heurística determinista de demostración; **no** es un modelo entrenado ni un dispositivo médico.

## 1. Identidad

| Campo | Valor |
|---|---|
| Nombre | `rules-v0` |
| Tipo | Reglas deterministas (no LLM, no ML) |
| Implementación | `main.py::classify_esi` |
| Salida | `(categoría ESI 1-5, justificación en texto)` |
| Versión del golden set | 1.0 (`docs/ia/golden-set.json`) |
| Última evaluación | 2026-11-18, 44/44 casos correctos (`evaluation-report.json`) |

## 2. Uso previsto

Generar una **sugerencia de apoyo** de categoría ESI a partir de síntomas y signos vitales, para que la enfermera de triage confirme o corrija. El `CHARTER.md` prohibe que la recomendación sustituya al criterio humano: toda respuesta incluye «requiere confirmación de la enfermera de triage».

**Fuera de uso previsto:** decidir el destino clínico del paciente sin revisión humana, usarse como criterio diagnóstico, usarse con datos de identidad, o usarse con datos reales de pacientes sin validación clínica previa.

## 3. Entradas y salidas

**Entradas:** lista de síntomas (texto libre) y diccionario de signos vitales (`heartRate`, `bloodPressureSystolic`, `temperatureCelsius`, `oxygenSaturationPercentage`). Validados por Pydantic en la API (`VitalSigns`, `TriageIn`).

**Salida:** categoría entera 1-5 y una justificación que enumera las razones que dispararon la categoría. Prioriza la severidad mayor (ESI 1 > 2 > 3).

**Datos excluidos deliberadamente:** RUT, nombre, contacto y cualquier identificador directo. La identidad se registra en `POST /patients` y se enmascara en logs con `mask_rut`.

## 4. Datos y entrenamiento

No hay dataset de entrenamiento, pesos ni llamadas a modelos externos. El comportamiento se define en las constantes `_CRITICAL_SYMPTOMS` y `_HIGH_RISK_SYMPTOMS` y en los umbrales de `classify_esi`. Por tanto no existe riesgo de fuga de datos de entrenamiento ni de dependencia de un proveedor de IA.

## 5. Evaluación

| Métrica | Resultado | Cómo se obtiene |
|---|---|---|
| Exactitud sobre golden set | 44/44 (100 %) | `python docs/ia/evaluate.py` |
| Casos de categoría | 42/42 | Reglas por nivel, límites exactos y prioridad de severidad |
| Casos de justificación | 2/2 | Presencia de fragmentos explicativos y mención de confirmación humana |
| Cobertura del repo | 99,16 % (104 tests) | `pytest --cov=main --cov-fail-under=70` |
| Latencia de inferencia | Despreciable (función pura) | Sin red ni E/S; no instrumentada como p95 |

**RAGAS no aplica:** no hay recuperación ni generación. Reportar RAGAS aquí sería engañoso; la evaluación se hace con golden set determinista. Ver `docs/adr/0007-ia-responsable.md`.

## 6. Guardrails

1. Minimización de PII: el motor nunca recibe identidad.
2. Rangos validados en la capa de entrada; síntomas limitados a 50 elementos.
3. Salida acotada a 1-5 y justificación reproducible.
4. Humano en el loop: `PATCH /triage-evaluations/{id}` confirma o corrige; cada cambio se audita.
5. Sin prompt injection: los síntomas son datos comparados con literales, no instrucciones para un modelo.

## 7. Limitaciones y sesgos conocidos

- **Sin validación clínica.** No se ha contrastado con criterio ESI real ni con especialistas.
- **Vocabulario cerrado.** Solo reconoce las palabras de las constantes; sinónimos no listados caen en categoría inferior.
- **Sin fairness medido.** No hay cohortes ni datos para evaluar sesgo por edad, sexo o comuna.
- **Estado no persistente.** Las evaluaciones y el audit log viven en memoria; ver `docs/operacion/post-mortem.md`.
- **Explicación limitada.** La justificación es la lista de reglas disparadas, no un razonamiento clínico.

## 8. Cumplimiento legal

Ley 19.628 (datos sensibles, consentimiento `consentGiven`, enmascaramiento de RUT) y Ley 21.719 (seguridad y minimización). Ver `CHARTER.md` y `docs/threat-model.md`.

## 9. Mantenimiento

Cambiar umbrales o vocabulario obliga a: actualizar `golden-set.json`, ejecutar `evaluate.py`, ejecutar `pytest` y reabrir el ADR 0007. Revisión prevista: antes de cualquier uso con datos reales.
