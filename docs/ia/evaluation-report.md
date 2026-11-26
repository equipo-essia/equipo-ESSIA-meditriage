# Resultado de la evaluación del motor `rules-v0`

**Fecha de ejecución:** 2026-11-18T18:56:16Z
**Comando:** `python docs/ia/evaluate.py` (desde la raíz del repo)
**Salida cruda:** [`evaluation-report.json`](evaluation-report.json)
**Conjunto:** [`golden-set.json`](golden-set.json) v1.0

## Resumen

| Métrica | Valor |
|---|---|
| Casos totales | 44 |
| Casos correctos | 44 |
| Exactitud | 100 % |
| Casos de categoría | 42 |
| Casos de justificación | 2 |
| Fallos | 0 |

## Desglose por categoría esperada

| ESI | Casos correctos |
|---|---|
| 1 | 11 |
| 2 | 15 |
| 3 | 9 |
| 4 | 2 |
| 5 | 5 |

Los 42 casos de categoría cubren: cada regla de nivel, los límites exactos de los umbrales (por ejemplo SpO₂ 89/90/93/94, FC 100/101/130/131/150/151, PAS 79/80/90/180, temperatura 35/38/40), la prioridad de severidad y el comportamiento con signos vitales ausentes. Los 2 casos de justificación comprueban que el texto mencione la razón, la categoría y la confirmación de la enfermera.

## Qué significa y qué no significa

- Significa: el motor es **determinista y consistente** con las reglas documentadas y con los tests del repo.
- No significa: precisión clínica, validación por especialistas, fairness medido ni desempeño con datos reales. No hay modelo estadístico del cual estimar intervalos de confianza.
- No se reporta RAGAS porque no existe un componente de recuperación ni generación; ver el ADR 0007.

## Reproducción

```bash
python docs/ia/evaluate.py
pytest --cov=main --cov-report=term-missing --cov-fail-under=70
```

Si cambian los umbrales, este informe queda obsoleto: actualizar el golden set y volver a ejecutar ambos comandos.
