# MediTriage — Apoyo a la priorización clínica en urgencias

[![CI](https://github.com/equipo-essia/equipo-ESSIA-meditriage/actions/workflows/ci.yml/badge.svg)](https://github.com/equipo-essia/equipo-ESSIA-meditriage/actions/workflows/ci.yml)

**Proyecto final — Taller de Ingeniería de Software · Equipo ESSIA · S18**

MediTriage es una API que sugiere una categoría de triage ESI (1-5) a partir de
síntomas y signos vitales, con justificación legible y confirmación obligatoria
de la enfermera. El objetivo de negocio es reducir la priorización de **25 min a
menos de 3 min** ([`docs/backlog.md`](docs/backlog.md),
[`docs/impact-map.md`](docs/impact-map.md)). El repositorio contiene el MVP
ejecutable, el contrato abierto, los manifiestos Kubernetes, la cadena de
suministro firmada y la documentación de arquitectura, IA responsable,
operación y costos que se defiende en la S18.

> **Honestidad técnica:** lo que corre hoy es una API FastAPI **en memoria** con
> reglas deterministas (`rules-v0`). El worker de IA con SQS/Lambda, PostgreSQL,
> OpenSearch y la SPA son **diseño** documentado en ADRs y C4 L1/L2, no código
> de `main`. Los SLOs son objetivos, no métricas instrumentadas. Ver
> [Estado real](#9-estado-real-y-limitaciones).

---

## 1. Demo en 90 segundos (lo que se muestra en la defensa)

Requisitos: Python 3.11+ y `pip install -r requirements.txt`.

```powershell
# Terminal 1: levantar la API (Windows PowerShell)
$env:AUTH_ENABLED = "false"
uvicorn main:app --port 8000

# Terminal 2: flujo completo (registro, sugerencia ESI, confirmación, tablero, auditoría)
python demo/demo.py
```

En Linux o macOS: `AUTH_ENABLED=false uvicorn main:app --port 8000` y luego
`python demo/demo.py`.

Para correr la misma demo contra la API desplegada en Kubernetes, abre un túnel
(`kubectl port-forward -n meditriage deploy/meditriage-api 8080:8000`) y ejecuta
`$env:BASE_URL = "http://127.0.0.1:8080"; python demo/demo.py`. La interfaz
visual de demo está en [`demo/ui/`](demo/ui/); no es la SPA diseñada en el C4,
que sigue como diseño.

Salida esperada: `health ok`, paciente `201`, sugerencia `202` con ESI 2 y
justificación con la razón y la confirmación enfermera, `200` con
`status: confirmed`, tablero ordenado por ESI y **2** eventos de auditoría
(creación + confirmación). Usar `AUTH_ENABLED=false` solo en local; en clúster
el token Bearer es obligatorio.

Contrato completo: [`api/openapi.yaml`](api/openapi.yaml). Ejemplos de
petición/respuesta en [`api/examples/`](api/examples/).

---

## 2. Cómo ejecutar y verificar

```bash
# Instalar y probar
python -m venv .venv && .\.venv\Scripts\activate      # Windows
pip install -r requirements.txt
pytest --cov=main --cov-report=term-missing --cov-fail-under=70
ruff check .

# Evaluar el motor de IA (golden set, sin LLM)
python docs/ia/evaluate.py

# Contenedor y Kubernetes (requiere Docker y kubectl)
docker build -t meditriage:local .
kubectl apply -k k8s/
kubectl get all,ingress,hpa -n meditriage
```

Verificación de la imagen firmada publicada por CI (requiere
[Cosign](https://github.com/sigstore/cosign)):

```bash
cosign verify \
  --certificate-identity "https://github.com/equipo-essia/equipo-ESSIA-meditriage/.github/workflows/ci.yml@refs/heads/main" \
  --certificate-oidc-issuer "https://token.actions.githubusercontent.com" \
  ghcr.io/equipo-essia/meditriage@<DIGEST>

cosign verify-attestation --type slsaprovenance \
  --certificate-identity "https://github.com/equipo-essia/equipo-ESSIA-meditriage/.github/workflows/ci.yml@refs/heads/main" \
  --certificate-oidc-issuer "https://token.actions.githubusercontent.com" \
  ghcr.io/equipo-essia/meditriage@<DIGEST>
```

Si ambos comandos terminan sin error, la imagen fue construida y firmada por
`ci.yml` en `main`. Kyverno la rechaza en el clúster si no es así. La
provenance es SLSA Build L2 con salvedad, no L3 ([ADR 0006](docs/adr/0006-supply-chain.md)).

---

## 3. Arquitectura y decisiones

| Vista | Enlace | Estado |
|---|---|---|
| C4 L1 — contexto | [`docs/c4/l1-context.puml`](docs/c4/l1-context.puml) | Diseño objetivo (SPA, RDS, SNS/SQS, IA) |
| C4 L2 — contenedores | [`docs/c4/l2-container.puml`](docs/c4/l2-container.puml) | Diseño objetivo (no implementado en `main`) |
| C4 L3 — componentes | [`docs/c4/l3-component.puml`](docs/c4/l3-component.puml) | **Estado real**: middleware, auth stub, `rules-v0`, `STORE` |
| Índice C4 | [`docs/c4/README.md`](docs/c4/README.md) | Puertos, protocolos y cuáles son diseño |
| ADRs | [`docs/adr/README.md`](docs/adr/README.md) | 8 decisiones con alternativas y riesgos |

**Top 3 ADRs para la defensa:**
1. [ADR 0002 — Estilo arquitectónico](docs/adr/0002-estilo-arquitectonico.md): monolito modular frente a microservicios.
2. [ADR 0004 — Datos, eventos y plataforma](docs/adr/0004-datos-y-eventos.md): Outbox + SNS/SQS FIFO, PostgreSQL, Kubernetes; por qué el MVP es sincrónico.
3. [ADR 0007 — IA responsable](docs/adr/0007-ia-responsable.md): reglas explicables frente a LLM; guardrails y por qué RAGAS no aplica.

Complementos: [atributos de calidad](docs/arch/atributos-calidad.md),
[servicios gestionados](docs/arch/managed-services.md),
[catálogo de eventos](docs/data/event-catalog.md),
[modelo de amenazas STRIDE](docs/threat-model.md) y
[checklist 12-Factor](docs/12-factor-checklist.md).

---

## 4. DevSecOps (evidencia S10)

| Capa | Dónde está | Evidencia |
|---|---|---|
| SAST, SCA, Secret scanning, IaC | `.github/workflows/ci.yml`, `.github/workflows/scans.yml` | [badge CI](#meditriage--apoyo-a-la-priorización-clínica-en-urgencias) |
| DAST (ZAP baseline) | `.github/workflows/scans.yml` | Artefacto `zap-baseline-report`; `10049 IGNORE` en `.zap/rules.tsv` |
| Trivy + 21 excepciones VEX | `.trivyignore` | `exp:2026-12-09`; revisar antes de esa fecha |
| Firma Cosign + attestation SLSA | job `sign-and-attest` de `ci.yml` | [ADR 0006](docs/adr/0006-supply-chain.md), comandos de verificación arriba |
| Admisión Kyverno | [`k8s/policies/require-signature.yaml`](k8s/policies/require-signature.yaml) | `Enforce`; capturas en [`docs/img/`](docs/img/) |
| Falco | [`falco/rules-custom.yaml`](falco/rules-custom.yaml) | [alertas y prioridades](docs/falco-alertas.md) |
| GitOps | job `promote-to-gitops` de `ci.yml` | [ADR 0005](docs/adr/0005-gitops-strategy.md); canonización `ghcr.io/equipo-essia/meditriage` con alias temporal |

**Cadena de suministro:** una sola imagen por digest, firmada keyless con OIDC
de GitHub Actions, verificada en CI y admitida solo si la firma es válida. Las
excepciones temporales de la policy (rama `feature/sign-and-attest` y alias
`guffy0921`) tienen fecha límite **2026-12-09** y se retiran al promover un
digest firmado desde `main`.

---

## 5. IA responsable

- **Motor real:** `rules-v0` en [`main.py`](main.py), sin LLM y sin llamadas a
  terceros. Categoría 1-5 por umbrales y palabras clave; prioriza severidad;
  justificación determinista.
- **Guardrails:** el motor no recibe RUT ni nombre; Pydantic valida rangos y
  número de síntomas; la salida está acotada a 1-5; la enfermera confirma o
  corrige en `PATCH /triage-evaluations/{id}` y todo se audita.
- **Evaluación:** 44/44 casos correctos en el
  [`golden-set.json`](docs/ia/golden-set.json) v1.0, reproducibles con
  `python docs/ia/evaluate.py` ([reporte](docs/ia/evaluation-report.md)).
- [Model card](docs/ia/model-card.md) · [ADR 0007](docs/adr/0007-ia-responsable.md)
- **RAGAS no aplica:** no hay recuperación ni generación. Reportar esa métrica
  sería engañoso; se sustituye por exactitud determinista, límites y cobertura
  de reglas.
- **Leyes 19.628 y 21.719:** consentimiento `consentGiven`, minimización,
  enmascaramiento de RUT en logs (`mask_rut`) y trazabilidad. Pendiente:
  cifrado en reposo y retención real a 5 años.

---

## 6. Operación, resiliencia y FinOps

| Documento | Qué contiene |
|---|---|
| [SLOs](docs/operacion/slos.md) | 99,5 % disponibilidad, p95 < 3 s, 5xx < 0,1 %,error budget 3 h 39 min. **Objetivos sin instrumentar.** |
| [Runbook](docs/operacion/runbook.md) | 7 procedimientos: probes, 5xx, Kyverno, Falco, rotación de secretos, DR y rollback. |
| [Game day](docs/operacion/game-day.md) | Ejercicio de mesa con 6 escenarios; 2 invalidan la hipótesis de disponibilidad funcional. |
| [Post-mortem](docs/operacion/post-mortem.md) | Pérdida de `STORE` al reiniciar: impacto, causa raíz, mitigación y responsables. |
| [Costo](docs/finops/costo.md) | ≈ 169 USD/mes y ≈ 0,034 USD/triage **estimados**; tagging y dos palancas con método de medición. |

Patrones implementados: 2 réplicas, probes HTTP, `RollingUpdate` con
`maxUnavailable: 0`, HPA 2-5 por CPU, requests/limits, non-root, filesystem de
solo lectura, imagen por digest y política de firma en `Enforce`.
Detalle en [`k8s/README.md`](k8s/README.md) y [ADR 0008](docs/adr/0008-resiliencia-finops.md).

---

## 7. Calidad

- **104 tests**, **99,16 % de cobertura** de `main.py` (`pytest --cov=main`).
- `ruff check .` sin errores.
- Contrato OpenAPI 3.1 con errores RFC 7807 y `trace_id`.
- Idempotencia por `Idempotency-Key` en los tres endpoints de escritura.
- Reporte histórico de Spectral: 5 warnings de `operation-tags` (0 errores) en
  [`docs/api/spectral-report.txt`](docs/api/spectral-report.txt); corrección
  pendiente.
- [Preguntas del panel con evidencia](docs/seguridad/preguntas-panel.md) para Q&A.

---

## 8. Estructura del repositorio

```text
api/            contrato OpenAPI y ejemplos
docs/adr/       8 ADRs + índice
docs/c4/        C4 L1/L2/L3 + mapa de puertos
docs/ia/        golden set, evaluador, model card e informes
docs/operacion/ SLOs, runbook, game day y post-mortem
docs/finops/    modelo de costo y tagging
docs/seguridad/ preguntas del panel y modelo de amenazas
docs/img/       capturas de evidencia S10
falco/          reglas personalizadas
k8s/            Deployment, Service, Ingress, HPA, política Kyverno
tests/          tests unitarios y de integración
.github/workflows/  ci.yml y scans.yml (reutilizable)
main.py         API FastAPI + rules-v0
```

---

## 9. Estado real y limitaciones

**Implementado en `main`:** API FastAPI, `rules-v0`, idempotencia, audit log
en memoria, endpoints del contrato, contenedor distroless, manifiestos K8s,
HPA, SAST/SCA/DAST/IaC, firma Cosign, Kyverno en `Enforce`, Falco y GitOps.

**Diseñado pero no implementado:** PostgreSQL y PITR, broker SNS/SQS y worker
de IA, read models/OpenSearch, SPA WebSockets, métricas/dashboards de SLO, TLS
en el Ingress, ruta de alertas de Falco, game day en clúster, factura cloud y
validación clínica/fairness.

El riesgo técnico principal es el estado en memoria: con 2-5 réplicas un
paciente registrado en una no existe en otra y el audit log se pierde al
reiniciar. Está documentado y asumido en el
[post-mortem](docs/operacion/post-mortem.md). Antes de producción: persistir el
estado, instrumentar SLOs, ejecutar el game day en staging y sustituir la
estimación de costo por datos reales.
