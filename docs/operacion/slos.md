# SLOs y error budget — MediTriage API

**Versión:** 1.0 · **Fecha:** 2026-11-18 · **Responsable:** Martín Durán (DevSecOps & Compliance Lead)
**Estado:** objetivos definidos; **no instrumentados todavía**. No se afirma que estén siendo medidos.

## 1. Objetivos

| SLO | Objetivo | Ventana | Cómo se mediría | Estado actual |
|---|---|---|---|---|
| Disponibilidad del API | 99,5 % de éxito en `/health` | 30 días deslizantes | Series temporales del Ingress (`sum(rate(http_requests_total{code!~"5.."}[5m])) / sum(rate(http_requests_total[5m]))`) | Objetivo del `CHARTER.md`; sin backend de métricas |
| Latencia de sugerencia | p95 < 3 s en `POST /triage-evaluations` | 30 días | Histograma de duración por endpoint | NFR de `docs/arch/atributos-calidad.md`; sin instrumentar |
| Latencia de probe | p95 < 200 ms en `GET /health` | 30 días | Histograma del mismo endpoint | Sin instrumentar; la función es trivial |
| Tasa de errores | 5xx < 0,1 % | 30 días | Conteo de respuestas 5xx | Sin instrumentar |
| Integridad de despliegue | 100 % de pods con imagen firmada | Continuo | Kyverno `require-image-signature` en `Enforce` | ✅ Implementado (`k8s/policies/require-signature.yaml`) |

**Error budget de disponibilidad:** 0,5 % de 30 días ≈ **3 h 39 min/mes**. Si se agota, se congelan cambios no críticos y se prioriza estabilidad.

## 2. Patrones que sostienen los SLOs

- `readinessProbe` y `livenessProbe` HTTP sobre `/health` (`k8s/deployment.yaml`).
- `RollingUpdate` con `maxSurge: 1` y `maxUnavailable: 0`: nunca baja a 1 réplica durante el despliegue.
- HPA por CPU al 50 %, de 2 a 5 réplicas (`k8s/hpa.yaml`); prueba de carga documentada en `k8s/README.md`.
- `requests: 100m/128Mi`, `limits: 500m/256Mi` para evitar vecinos ruidosos.
- Imagen fijada por digest y verificada por Kyverno antes de admitir el pod.
- Contenedor distroless, non-root (UID 65532), `readOnlyRootFilesystem`, sin capabilities.

## 3. Riesgo que hoy limita el SLO de disponibilidad

`STORE` en `main.py` es memoria de proceso. Con 2-5 réplicas:

- un paciente registrado en una réplica no existe en otra;
- al reiniciar un pod se pierden evaluaciones, audit log y claves de idempotencia.

Detalle y mitigación en [`post-mortem.md`](post-mortem.md). Por eso la disponibilidad *técnica* del endpoint no equivale a disponibilidad *funcional* del servicio.

## 4. Siguiente paso

Instrumentar Prometheus + Grafana con los cuatro SLOs, exportar el dashboard en el repo y sustituir «objetivo» por «medido». Hasta entonces, en la defensa se presentan como **objetivos con evidencia de los patrones implementados**, no como resultados observados.

## 5. Evidencias en el repo

- `CHARTER.md` (SLA 99,5 %)
- `docs/arch/atributos-calidad.md` (p95 < 3 s)
- `k8s/deployment.yaml`, `k8s/hpa.yaml`, `k8s/README.md`
- `k8s/policies/require-signature.yaml`
