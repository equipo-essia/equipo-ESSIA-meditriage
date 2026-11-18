# Game day — Ejercicio de mesa (2026-11-18)

**Tipo:** ejercicio de mesa (tabletop) sobre el estado real del repositorio.
**No se afirma** que se haya ejecutado en un clúster ni que se hayan medido series temporales. La ejecución en staging queda como acción pendiente.
**Participantes previstos por rol:** Cristóbal Araos (técnico), Martín Garrido (negocio), Martín Durán (seguridad), Alonso Plane (QA).

## 1. Hipótesis

> «Si un pod de la API muere en mitad de una evaluación, el servicio sigue disponible y la decisión clínica no se pierde.»

## 2. Escenarios y resultado del ejercicio

| # | Fallo simulado | Qué se revisó en el repo | Resultado | Evidencia |
|---|---|---|---|---|
| 1 | Muere una de las 2 réplicas | `k8s/deployment.yaml`: `replicas: 2`, `maxUnavailable: 0`, probes | **Sobrevive** el endpoint; queda 1 réplica | `k8s/deployment.yaml` |
| 2 | La réplica muere justo después de `POST /triage-evaluations` | `STORE` en `main.py`, `_audit` | **FALLO de la hipótesis**: la evaluación y el audit log se pierden | `main.py`, `docs/operacion/post-mortem.md` |
| 3 | Un paciente registrado en la réplica A se evalúa en la B | `STORE` por proceso, HPA 2-5 | **FALLO**: `unknown-patient` aunque el paciente exista | `main.py`, `k8s/hpa.yaml`, `docs/threat-model.md` (T4) |
| 4 | Se promueve una imagen sin firmar | Kyverno `validationFailureAction: Enforce`, Cosign en `ci.yml` | **Bloqueada** por la policy | `k8s/policies/require-signature.yaml`, ADR 0006 |
| 5 | Se dispare el HPA por CPU | `k8s/hpa.yaml`, prueba con busybox documentada | Configuración correcta; **medición en clúster pendiente** | `k8s/README.md` |
| 6 | Se intenta leer un secreto desde el repo | `git` ignore, secretos en GitHub Actions | No hay secreto en el repo; rotación documentada | `docs/operacion/runbook.md` §5 |

## 3. Hallazgo principal

La disponibilidad **técnica** del endpoint se sostiene con 2 réplicas y probes, pero la disponibilidad **funcional** no: el estado no es compartido. Dos de los seis escenarios invalidan la hipótesis. Es el mayor riesgo técnico y se documenta como incidente en [`post-mortem.md`](post-mortem.md).

## 4. Qué sí quedó demostrado con evidencia en repo

- Rollout sin caída de réplicas (`maxUnavailable: 0`).
- Imagen sin firma rechazada en modo `Enforce` (capturas `docs/img/s10-05-policy-enforce.png` y `s10-06-rechazo-sin-firma.png`).
- Reglas de Falco validadas y con ruta de alertas descrita (`docs/falco-alertas.md`, `docs/img/s10-07-falco-alertas.png`).
- HPA probado con carga sintética según `k8s/README.md` (`docs/img/hpa-scale-up.png`).

## 5. Acciones derivadas

| Acción | Responsable | Estado |
|---|---|---|
| Persistir `STORE` en PostgreSQL y audit log append-only | Cristóbal Araos | Planificada (ADR 0004) |
| Ejecutar este escenario 2 y 3 en staging con métricas | Martín Durán | Pendiente |
| Instrumentar SLOs del `slos.md` | Martín Durán | Pendiente |
| Repetir el game day con el fix aplicado y actualizar este documento | Alonso Plane | Pendiente |

## 6. Cómo repetirlo en staging

1. Avisar al canal `#equipo-ESSIA-meditriage`, abrir ventana de 30 min.
2. Ejecutar los seis escenarios con `kubectl` siguiendo el `runbook.md`.
3. Capturar `kubectl get pods -w`, `kubectl get hpa -w`, logs y PolicyReport.
4. Registrar hora de detección, hora de mitigación y desviación del SLO.
5. Actualizar este archivo con los datos reales y enlazar las evidencias.
