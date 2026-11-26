# Post-mortem — Pérdida de estado al reiniciar el pod

**Fecha del hallazgo:** 2026-11-18 · **Origen:** game de mesa (`game-day.md`, escenarios 2 y 3)
**Severidad:** Alta (afecta integridad de la decisión clínica y del audit log)
**Autor:** Alonso Plane (QA & Architecture Lead) · **Estado:** mitigación parcial, fix pendiente

> Este post-mortem documenta un fallo **real del código actual**, detectado al contrastar los manifiestos con `main.py`. No es un incidente de producción: el MVP se ejecuta en local y no hay pacientes reales.

## 1. Resumen

El API mantiene pacientes, evaluaciones, registro de auditoría y claves de idempotencia en la variable global `STORE` de `main.py`. Cada pod tiene su propia copia. Al reiniciar un pod —o al recibir una petición en otra réplica— la información desaparece o no se encuentra.

## 2. Impacto

- `POST /triage-evaluations` puede responder `unknown-patient` para un paciente registrado minutos antes en otra réplica.
- El audit log se pierde al reiniciar, incompatible con el requisito de conservación a 5 años del `CHARTER.md`.
- La idempotencia deja de funcionar tras un reinicio: una reintención con la misma `Idempotency-Key` se procesa como nueva.
- La hipótesis de disponibilidad funcional del game day queda invalidada.

## 3. Línea de tiempo del ejercicio

| Hora relativa | Hecho |
|---|---|
| T0 | Se plantea la hipótesis: «si muere un pod, la decisión no se pierde». |
| T+5 min | Escenario 1: se revisa el Deployment; el endpoint sobrevive con 1 réplica. |
| T+12 min | Escenario 2: se sigue el flujo `POST /triage-evaluations` → `_audit` → `STORE`; se detecta que todo vive en memoria. |
| T+18 min | Escenario 3: se comprueba el HPA de 2 a 5 réplicas; el estado diverge entre pods. |
| T+25 min | Se decide documentar el hallazgo como incidente y no afirmar DR cumplido en la defensa. |

## 4. Causa raíz

`STORE: dict[str, Any] = {"patients": {}, "evaluations": {}, "audit": [], "idempotency": {}}` en `main.py`, protegido con `threading.Lock` pero **no compartido entre procesos**. Es el incumplimiento del factor 6 (Processes) del `docs/12-factor-checklist.md`, ya señalado en el modelo de amenazas como T4.

**Factores contribuyentes:**
- El MVP priorizó cerrar la demo sin base de datos.
- El HPA permite 2-5 réplicas, lo que hace visible la divergencia.
- No hay backend de métricas que hubiera detectado el `unknown-patient` en producción.

## 5. Qué funcionó bien

- `maxUnavailable: 0` y los probes evitan caída del endpoint durante el rollout.
- La firma y la policy de Kyverno bloquean una imagen no autorizada (escenario 4).
- La documentación previa (`threat-model.md`, `12-factor-checklist.md`) ya había marcado el riesgo; el game day lo confirmó.

## 6. Mitigación

**Inmediata (documental):** no afirmar en la defensa que el servicio es resistente a pérdida de estado; presentar este post-mortem como evidencia de honestidad técnica.

**Corto plazo (código):**
1. Mover `patients`, `evaluations` e `idempotency` a PostgreSQL (ADR 0004).
2. Hacer el audit log una tabla append-only con hash encadenado y réplica WORM a 5 años.
3. Mantener `LOCK` solo para coherencia local; la concurrencia entre réplicas se resuelve en BD.

**Largo plazo:** copias PITR, RPO 15 min y RTO 30 min ensayados; repetir el game day con el fix aplicado.

## 7. Lecciones

- Un SLO de disponibilidad HTTP no implica disponibilidad funcional: `/health` puede estar en verde mientras el paciente no existe en otra réplica.
- Los `readinessProbe` y el HPA resuelven disponibilidad, no consistencia.
- Mostrar el fallo con causa raíz y mitigación es mejor evidencia que afirmar resiliencia sin probarla.

## 8. Seguimiento

| Acción | Responsable | Estado |
|---|---|---|
| Persistencia en PostgreSQL | Cristóbal Araos | Planificada |
| Audit log append-only + WORM | Martín Durán | Planificada |
| Repetir escenarios 2 y 3 en staging | Alonso Plane | Pendiente |
| Instrumentar tasa de `unknown-patient` | Martín Durán | Pendiente |
