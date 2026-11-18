# ADR 0008 — Resiliencia y FinOps del MVP

- **Estado:** Aceptado con salvedades
- **Fecha:** 2026-11-18
- **Decisores:** Martín Garrido, Cristóbal Araos, Martín Durán, Alonso Plane
- **Relacionado:** `CHARTER.md`, `docs/arch/atributos-calidad.md`, `docs/operacion/slos.md`, `docs/operacion/runbook.md`, `docs/operacion/game-day.md`, `docs/operacion/post-mortem.md`, `docs/finops/costo.md`, ADR 0003, ADR 0004, ADR 0005

## 1. Contexto

El `CHARTER.md` fija un SLA de 99,5 % mensual y el NFR de latencia es p95 < 3 s. El MVP corre en Kubernetes con 2 réplicas, HPA hasta 5, probes HTTP e imagen por digest. La S18 pide SLOs, patrones aplicados, DR con game day, runbook ejecutable, costo mensual creíble, tagging y dos palancas medidas antes/después.

## 2. Decisión

### Resiliencia

- **SLOs:** disponibilidad 99,5 %/mes (error budget ≈ 3 h 39 min), latencia p95 < 3 s para la sugerencia y < 200 ms para `/health`, tasa de errores 5xx < 0,1 %. Definidos en `docs/operacion/slos.md`.
- **Patrones aplicados:** `readinessProbe` y `livenessProbe` sobre `/health` (`k8s/deployment.yaml`), `RollingUpdate` con `maxUnavailable: 0`, HPA por CPU al 50 % entre 2 y 5 réplicas (`k8s/hpa.yaml`), `requests`/`limits`, `runAsNonRoot`, filesystem de solo lectura y `capabilities drop ALL`.
- **DR:** RTO objetivo 30 min (recrear desde la imagen firmada en GHCR con `kubectl apply -k k8s/`), RPO objetivo 15 min una vez exista PostgreSQL. **Hoy no se cumple el RPO**: `STORE` vive en memoria y se pierde al reiniciar; ver el post-mortem.
- **Game day:** ejercicio de mesa documentado en `docs/operacion/game-day.md`, con hallazgos reales sobre el estado del repo. No se afirma una ejecución en clúster que no ocurrió.
- **Runbook:** pasos ejecutables para los incidentes probables en `docs/operacion/runbook.md`.

### FinOps

- Modelo de costo estimado para el diseño objetivo (AWS) en `docs/finops/costo.md`, con supuestos explícitos: no hay factura real porque el despliegue demostrado es local/GHCR.
- Tagging obligatorio en el diseño: `app=meditriage`, `env=dev|staging|prod`, `owner`, `cost-center`.
- Dos palancas: caché de capas de Docker/GHA en CI y techo de réplicas del HPA; ambas con método de medición antes/después.

## 3. Alternativas descartadas

| Alternativa | Por qué se descartó |
|---|---|
| Réplicas fijas sin HPA | Desperdicia cómputo en horas valle y no absorbe picos; el HPA ya está declarado y la prueba de carga con carga sintética está documentada en `k8s/README.md`. |
| Sin probes, solo reinicio del pod | Un pod sin `readinessProbe` recibe tráfico antes de estar listo; el rolling update con `maxUnavailable: 0` exige saber cuándo está listo. |
| Base de datos gestionada ya en el MVP | Aumenta costo y alcance; el modelo de datos aún está en memoria y el equipo priorizó cerrar la demo. Queda en el ADR 0004 como siguiente paso. |
| Escalar a 0 réplicas para ahorrar | En urgencias el frío de arranque es inaceptable frente al SLO de latencia; se prefirió piso de 2 réplicas. |
| AWS Free Tier «gratis» como modelo de costo | No es sostenible ni creíble para un productivo; se estimó el costo real con supuestos publicados y se marcó como estimación. |
| Multi-región / active-active para DR | Fuera de alcance y presupuesto para el MVP; se documenta como evolución. |

## 4. Estado real vs. objetivo

| Elemento | Hoy (evidencia en repo) | Objetivo |
|---|---|---|
| Disponibilidad | 2 réplicas, probes, rolling update (`k8s/deployment.yaml`) | 99,5 % medido con series temporales (pendiente de instrumentar) |
| Latencia p95 | No instrumentada; `rules-v0` es despreciable | Dashboard y alerta por SLO |
| Persistencia | `STORE` en memoria, se pierde al reiniciar | PostgreSQL con copias y PITR |
| DR | Reconstrucción desde imagen firmada | RTO 30 min, RPO 15 min ensayados |
| Costo | Estimación documentada, sin factura | Factura real, presupuesto por ambiente |

## 5. Riesgos

- No hay backend de métricas: los SLOs son objetivos, **no están siendo medidos**. No se afirma lo contrario.
- El estado en memoria es el mayor riesgo técnico: afecta disponibilidad, consistencia entre réplicas y auditoría a 5 años.
- Ingress expone HTTP (`meditriage.local` sin TLS), explicado en el modelo de amenazas.
- La estimación de costo depende de precios de AWS y del volumen real de triages; debe revisarse con datos de factura.

## 6. Consecuencias

- Se puede defender la resiliencia con los patrones implementados y con honestidad sobre lo que falta.
- Antes de producción: instrumentar métricas, persistir el estado, ejecutar el game day en staging y sustituir la estimación de costo por datos reales.
