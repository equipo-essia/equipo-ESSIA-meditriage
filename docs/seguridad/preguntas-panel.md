# Preguntas del panel — respuestas con evidencia

**Uso:** preparación del Q&A de 15 minutos. Cada respuesta nace de un archivo del repo; cuando algo no se hizo, se dice explícitamente. Reparto por rol según `CHARTER.md`.

## Perfil técnico

**¿Por qué event-driven vs sincrónico?**
El **diseño objetivo** es event-driven (ADR 0004): `triage.requested`, `triage.completed` sobre SNS/SQS FIFO para desacoplar API, motor de IA y auditoría, con patrón Outbox y consumidores idempotentes. El **MVP real** es sincrónico en un solo proceso (`main.py::create_triage_evaluation`), porque el broker y el worker no están implementados. No se afirma lo contrario. Evidencia: `docs/data/event-catalog.md`, `docs/c4/l2-container.puml`, `main.py`.

**¿Qué alternativas descartaron en el ADR 0004?**
Se descartaron: (1) inserción directa en base de datos sin broker, por acoplamiento entre API y motor; (2) llamada HTTP sincrónica API→IA, porque rompe el SLO p95 < 3 s al depender de un servicio externo; (3) REST polling desde el tablero, por costo y frescura; (4) Kafka autogestionado, por sobrecarga operativa frente a SNS/SQS gestionado. Tabla completa en el ADR 0004.

**¿Cómo evolucionaría esto a 100× tráfico?**
Hoy el cuello es `STORE` en memoria y el `LOCK` global: 100× tráfico no se resuelve añadiendo réplicas, porque el estado diverge. Secuencia: PostgreSQL con `SELECT ... FOR UPDATE SKIP LOCKED`, outbox + broker, read models para el tablero, caché de Redis, HPA y particionado de la tabla de auditoría. Evidencia del riesgo: `docs/operacion/post-mortem.md`, `docs/threat-model.md` (T4).

**Muéstrame un test que falle si borro esta función.**
`tests/test_unit.py::test_classify_esi_boundaries` falla si se altera cualquier umbral de `classify_esi` (por ejemplo SpO₂ 89→1, 90→2, 94→5). `test_rut_masking_keeps_only_last_char` falla si se elimina `mask_rut`. 104 tests, 99,16 % de cobertura.

**¿Dónde está el mayor riesgo técnico hoy?**
La persistencia en memoria (`STORE`), no la seguridad de la cadena de suministro. Está resuelto el rollout sin caída, la firma y la policy en `Enforce`; no está resuelto que un paciente registrado en una réplica exista en otra. Evidencia: `docs/operacion/post-mortem.md`, ADR 0008.

## Perfil de negocio

**¿Cómo mides que el producto ayuda al usuario?**
El objetivo del `docs/impact-map.md` y el `docs/backlog.md` es reducir el tiempo de priorización de 25 min a < 3 min. Hoy **no hay medición real**: no hay series temporales ni usuarios reales. La métrica candidata es `p95(desde registro hasta sugerencia confirmada)`; está definida en los SLOs como pendiente de instrumentar.

**¿Cuál es el costo por usuario / tenant / triage?**
≈ 0,034 USD por evaluación con 5 000 evaluaciones/mes y ≈ 169 USD/mes de costo fijo estimado (`docs/finops/costo.md`). No hay factura real: es un modelo con supuestos explícitos.

**¿Qué feature entrega más valor por unidad de esfuerzo?**
La sugerencia ESI con justificación (`rules-v0`): ya existe, es determinista, explicable y no cuesta inferencia. El fallback manual de la enfermera es el segundo lugar: cubre el fallo del motor sin infraestructura adicional.

**Si tuvieran 2 semanas más, ¿qué construirían?**
1) Persistencia en PostgreSQL con audit log append-only (desbloquea 2 réplicas reales y el RPO). 2) Instrumentación de los SLOs y dashboard. 3) Validación clínica del golden set con enfermeras. En ese orden, porque los dos primeros eliminan el riesgo técnico y el tercero es prerrequisito para uso real.

**¿Cuál es el break-even estimado?**
Con un supuesto hipotético de 0,10 USD por evaluación, ≈ 1 700 evaluaciones/mes cubren 169 USD/mes. Alternativa por suscripción: 4 sedes × 50 USD/mes. Es un supuesto de negocio, no un ingreso medido.

## Perfil de seguridad

**¿Cómo aplica la Ley 21.719 a este producto?**
Datos de salud son sensibles: consentimiento explícito (`consentGiven` en `POST /patients`), minimización (el motor no recibe RUT ni nombre), seguridad de tratamiento (TLS objetivo, imagen firmada, SAST/SCA/DAST, secretos fuera del repo) y trazabilidad (audit log con timestamp). Conviven con la Ley 19.628. Pendiente: cifrado en reposo real y retención verificable a 5 años; hoy el audit log vive en memoria.

**Muéstrame un secret. ¿Dónde vive y quién lo rota?**
**No hay ningún secreto en el repo**: `GITOPS_TOKEN` vive en GitHub Actions (Settings → Secrets), `GITHUB_TOKEN` es efímero por run y el Secret `meditriage-secrets` de Kubernetes tiene hoy un placeholder `CHANGEME`. `GITOPS_TOKEN` lo rota Martín Durán cada 90 días; el procedimiento está en `docs/operacion/runbook.md` §5. Mostrar `git log -S'CHANGEME'` para demostrar que solo hay un valor de ejemplo.

**¿Qué hace tu sistema frente a un prompt injection?**
Hoy no hay LLM: `rules-v0` compara los síntomas como datos contra literales, no como instrucciones. Por tanto no existe un canal de inyección de prompt. Si se incorporara un modelo, el ADR 0007 se reabre y harían falta: separación instrucción/dato, validación de salida acotada a 1-5, y pruebas adversariales en el golden set. No se afirma que esté probado un LLM que no existe.

**¿Cómo demuestran fairness a un regulador?**
**No puede demostrarse todavía**: no hay datos reales ni cohortes. Lo que sí hay es un golden set determinista de 44 casos y la prohibición de que la IA decida sola. La respuesta honesta es «no hay evidencia de fairness; está en el roadmap y es bloqueante para uso real».

**Enséñame el último post-mortem del equipo.**
`docs/operacion/post-mortem.md`: pérdida de `STORE` al reiniciar el pod. Incluye impacto, línea de tiempo, causa raíz (factor 6 de 12-Factor), mitigación y acciones con responsables. Fue detectado en el game day de mesa del 2026-11-18.

## Lo que no alcanzamos (decirlo antes de que lo pregunten)

- Sin métricas reales: los SLOs son objetivos, no mediciones.
- Sin base de datos: el estado y el audit log se pierden al reiniciar.
- Sin LLM: no hay RAGAS, ni fairness, ni evaluación clínica.
- Sin factura cloud: FinOps es una estimación con supuestos.
- Sin TLS en el Ingress (`meditriage.local`); documentado en `docs/threat-model.md`.
- Sin ruta de alertas de Falco desplegada: está diseñada en `docs/falco-alertas.md`.
- Sin game day en clúster: se hizo un ejercicio de mesa; la ejecución en staging queda pendiente.

**Principio:** responder con datos y distinguir «lo que hicimos» de «lo que no alcanzamos» vale más que una afirmación sin evidencia.
