# Modelo de amenazas (STRIDE) · API Backend de MediTriage

- **Autor:** Alonso Plane (QA & Architecture Lead)
- **Fecha:** 05/11/2026 · **Versión:** 1.0
- **Componente analizado:** API Backend (`main.py`, FastAPI) y su despliegue en Kubernetes (`k8s/`, `Dockerfile`)
- **Relacionado:** ADR 0002 (monolito modular), ADR 0004 (datos, eventos y plataforma, con su anexo de seguridad), `docs/12-factor-checklist.md`

> **Cómo leer este documento.** La columna *Estado real* describe lo que el repositorio hace **hoy**, verificado contra el código, los manifiestos y los tests. No describe lo planificado en los ADR. Lo planificado aparece como "Pendiente" y se explica en la mitigación.

## 1. Alcance y supuestos

**Dentro del alcance:** los endpoints de la API, su autenticación, el manejo de datos clínicos en memoria, el contenedor y el Deployment/Ingress/HPA que lo ejecutan.

**Fuera del alcance (se cubren en otros documentos):** SPA, worker de IA, broker, bases de datos, red del proveedor cloud. Hoy esos componentes no existen o están solo planificados (ver ADR 0004).

**Supuestos sobre el estado actual del MVP:**
- El estado vive **en la memoria de cada pod** (`STORE` en `main.py`); no hay PostgreSQL todavía.
- La autenticación Bearer es un **stub**: acepta cualquier token no vacío.
- El Ingress de `k8s/ingress.yaml` expone `meditriage.local` por HTTP, sin sección `tls`.

## 2. Diagrama de flujo y fronteras de confianza

```mermaid
flowchart LR
  subgraph Externo["Zona no confiable"]
    U["Usuarios: enfermera, médico, auditor"]
  end
  subgraph Cluster["Clúster Kubernetes · namespace meditriage"]
    I["Ingress nginx"]
    S["Service ClusterIP"]
    subgraph Pod["Pod API · 2 a 5 réplicas"]
      A["FastAPI · main.py"]
      M[("STORE en memoria<br/>pacientes, evaluaciones, audit")]
    end
  end
  F["Planificado: PostgreSQL RDS, SNS/SQS"]
  U -- "HTTP, sin TLS hoy" --> I --> S --> A --> M
  A -. "aún no implementado" .-> F
```

**Fronteras de confianza:** (1) Internet/usuario → Ingress; (2) Ingress → pod; (3) pod → almacenamiento (hoy memoria, mañana RDS/SQS).

## 3. Superficie de ataque

| Endpoint | Auth | Datos que maneja |
|---|---|---|
| `GET /health` | No (a propósito: probes de K8s) | Ninguno |
| `GET /` | No | Nombre del servicio, versión y `APP_ENV` |
| `GET /docs`, `/redoc`, `/openapi.json` | No (valores por defecto de FastAPI) | Contrato completo de la API |
| `POST /patients` | Bearer (stub) | **RUT, nombre completo**, consentimiento, signos vitales |
| `POST /triage-evaluations` | Bearer (stub) | Síntomas, signos vitales, categoría ESI |
| `PATCH /triage-evaluations/{id}` | Bearer (stub) | Confirmación o categoría ESI manual |
| `GET /triage-board` | Bearer (stub) | Todas las evaluaciones |
| `GET /audit-logs` | Bearer (stub) | Todas las decisiones y sus justificaciones |

**Activos a proteger:** datos personales y de salud (Leyes 19.628 y 21.719), integridad de la categoría ESI (decisión clínica), integridad y disponibilidad del registro de auditoría, disponibilidad del servicio (SLA 99,5 %).

## 4. Análisis STRIDE

**Leyenda de estado:** ✅ Implementado · 🟡 Parcial · ❌ Pendiente · ⚪ Riesgo aceptado para el MVP.
**Riesgo** = impacto × probabilidad en el contexto actual (Alto, Medio, Bajo).

### S · Spoofing (suplantación de identidad)

| ID | Amenaza | Riesgo | Mitigación | Estado real | Evidencia |
|---|---|---|---|---|---|
| S1 | Un atacante usa un token inventado (por ejemplo `Bearer x`) y es aceptado como usuario válido. | Alto | Validar JWT contra el proveedor de identidad: firma, expiración, `aud` y `iss`. | ❌ Pendiente. La validación solo comprueba que el header tenga formato `Bearer <algo>`. | `main.py` (`require_auth`), docstring del módulo |
| S2 | La autenticación se apaga por error con `AUTH_ENABLED=false` en producción. | Medio | Valor por defecto seguro y fallo de arranque si `APP_ENV=production` y la auth está apagada. | 🟡 Parcial. El valor por defecto es `true` y el ConfigMap no lo define. Falta el fallo de arranque. | `main.py` línea de `AUTH_ENABLED`; `k8s/configmap.yaml`; `test_auth_can_be_disabled_by_env` |

### T · Tampering (manipulación)

| ID | Amenaza | Riesgo | Mitigación | Estado real | Evidencia |
|---|---|---|---|---|---|
| T1 | Alguien con cualquier token cambia la categoría ESI de una evaluación, incluso varias veces. | Alto | RBAC (solo rol enfermera), estado terminal tras confirmar y auditoría de cada cambio. | 🟡 Parcial. Rango 1 a 5 validado y cada cambio queda en el audit log. No hay RBAC ni estado terminal. | `TriageUpdateIn`, `update_triage_evaluation` |
| T2 | Se altera o se pierde el registro de auditoría. | Alto | Tabla append-only en PostgreSQL, hash encadenado y réplica WORM en S3 (anexo del ADR 0004). | 🟡 Parcial. En el código solo se hace `append` y no hay endpoint que modifique entradas. Vive en memoria: se pierde al reiniciar el pod y no hay hash. | `_audit`; `test_audit_log_is_append_only` |
| T3 | Datos de entrada maliciosos o fuera de rango. | Medio | Validación de esquema con Pydantic, RUT con módulo 11 y errores uniformes. | 🟡 Parcial. Rangos de signos vitales, `fullName` ≤ 200 y `symptoms` ≤ 50 elementos. Falta largo máximo por síntoma y formato de `patientId`. | `VitalSigns`, `PatientIn`, `TriageIn`; tests de validación |
| T4 | Con 2 o más réplicas el estado diverge: un PATCH puede caer en un pod que no tiene la evaluación. | Alto | Persistencia compartida (PostgreSQL). | ❌ Pendiente. Limitación conocida y documentada (factor 6 de 12-Factor incumplido). | `STORE`; ADR 0004; `docs/12-factor-checklist.md` |
| T5 | Dependencias o imagen alteradas en la cadena de suministro. | Alto | Versiones fijadas, imagen por digest, SAST, SCA y escaneo de secretos en CI, y firma de artefactos. | 🟡 Parcial. Versiones fijadas e imagen por digest. SAST, SCA y secretos están en implementación (S09). Firma pendiente (S10). | `requirements.txt`, `k8s/deployment.yaml`, `.github/workflows/` |

### R · Repudiation (repudio)

| ID | Amenaza | Riesgo | Mitigación | Estado real | Evidencia |
|---|---|---|---|---|---|
| R1 | Un usuario niega haber confirmado o cambiado una categoría, porque el registro no dice quién fue. | Alto | Guardar `actor_id`, rol, IP y `request_id` en cada entrada del audit log. | ❌ Pendiente. Cada entrada guarda solo `evaluationId`, `esiCategory`, `justification` y `timestamp`. | `_audit` |
| R2 | No se pueden correlacionar una petición y sus logs. | Medio | Incluir `trace_id` en los logs y centralizarlos. | 🟡 Parcial. Todo error devuelve `trace_id`, pero no se escribe en los logs. Salen a stdout sin retención. | `problem_response`; `LOG_LEVEL` |
| R3 | No se puede demostrar qué versión del motor tomó una decisión. | Bajo | Justificación con la versión del motor, confirmación humana obligatoria y marca de tiempo UTC. | ✅ Implementado. | `classify_esi` ("motor rules-v0"); `test_audit_log_records_each_decision` |

### I · Information disclosure (filtración de información)

| ID | Amenaza | Riesgo | Mitigación | Estado real | Evidencia |
|---|---|---|---|---|---|
| I1 | RUT y nombre quedan en claro en memoria y en las respuestas. No hay cifrado en reposo. | Alto | Cifrado en reposo con KMS, `rut_hash` con HMAC y minimización de campos. | ❌ Pendiente. Depende de la integración con RDS. | `register_patient`; ADR 0004 (anexo) |
| I2 | El RUT aparece en los logs. | Medio | Enmascarar el RUT y no registrar nombre ni síntomas. | ✅ Implementado. Solo se imprime el último carácter. | `mask_rut`; `test_rut_is_masked_in_logs` |
| I3 | Intercepción del tráfico: el Ingress sirve HTTP sin cifrar. | Alto | TLS en el Ingress (certificado gestionado) y HSTS. | ❌ Pendiente. `ingress.yaml` no tiene sección `tls`. | `k8s/ingress.yaml` |
| I4 | Cualquiera lee el contrato completo (`/docs`, `/openapi.json`) y la versión y entorno (`/`). | Medio | Desactivar la documentación interactiva cuando `APP_ENV=production`. | ❌ Pendiente. La app se crea con los valores por defecto de FastAPI. | `app = FastAPI(...)` |
| I5 | Acceso horizontal: cualquier token lista todas las evaluaciones y todo el audit log, sin límite por rol ni por centro. | Alto | RBAC por rol y por centro de atención. | ❌ Pendiente (misma raíz que S1 y E1). | `triage_board`, `audit_logs` |
| I6 | Los errores revelan detalles internos (trazas, rutas). | Medio | Respuestas RFC 7807 sin stack trace y con `trace_id`. | ✅ Implementado. Los errores de validación solo informan campo y motivo. | `_validation_handler`; tests con `_assert_problem` |

### D · Denial of service (denegación de servicio)

| ID | Amenaza | Riesgo | Mitigación | Estado real | Evidencia |
|---|---|---|---|---|---|
| D1 | Ráfaga de peticiones que satura CPU o tumba pods. | Alto | Escalado automático, límites de recursos, probes y rate limiting en el Ingress. | 🟡 Parcial. HPA de 2 a 5 réplicas al 50 % de CPU, `requests` y `limits`, probes y `maxUnavailable: 0`. Falta rate limiting. | `k8s/hpa.yaml`, `k8s/deployment.yaml` |
| D2 | Agotamiento de memoria: `STORE` y las claves de idempotencia crecen sin límite y el pod llega al límite de 256 Mi. | Medio | Persistir en BD, expirar claves de idempotencia (TTL) y limitar el tamaño de cada string. | ❌ Pendiente. | `STORE`, `_idem_save`; `limits.memory` |
| D3 | Un único `LOCK` serializa las escrituras y degrada la latencia bajo carga. | Bajo | Reemplazar con transacciones de base de datos. | ⚪ Aceptado para el MVP: mantiene la consistencia mientras el estado está en memoria. | `LOCK` en `main.py` |

### E · Elevation of privilege (elevación de privilegios)

| ID | Amenaza | Riesgo | Mitigación | Estado real | Evidencia |
|---|---|---|---|---|---|
| E1 | Un usuario autenticado ejecuta funciones de otro rol (por ejemplo, un paciente confirma triage o lee la auditoría). | Alto | Roles y permisos por endpoint (paciente, enfermera, médico, auditor). | ❌ Pendiente. No existe el concepto de rol. | `require_auth` |
| E2 | Compromiso de la app y escape hacia el nodo. | Alto | Contenedor mínimo, no-root y con capacidades eliminadas. | ✅ Implementado. Distroless sin shell, UID 65532, `readOnlyRootFilesystem`, `allowPrivilegeEscalation: false`, `drop ALL` y `seccompProfile: RuntimeDefault`. | `Dockerfile`, `k8s/deployment.yaml` |
| E3 | El token de la ServiceAccount por defecto está montado en el pod aunque la API no usa la API de Kubernetes. | Medio | `automountServiceAccountToken: false` y una ServiceAccount dedicada. | ❌ Pendiente. | `k8s/deployment.yaml` |
| E4 | Movimiento lateral: sin reglas de red, un pod comprometido llega a cualquier otro. | Medio | `NetworkPolicy` con denegación por defecto y excepciones mínimas. | ❌ Pendiente. No hay `NetworkPolicy` en `k8s/`. | `k8s/` |

## 5. Resumen

| Estado | Cantidad | IDs |
|---|---|---|
| ✅ Implementado | 4 | R3, I2, I6, E2 |
| 🟡 Parcial | 7 | S2, T1, T2, T3, T5, R2, D1 |
| ❌ Pendiente | 11 | S1, T4, R1, I1, I3, I4, I5, D2, E1, E3, E4 |
| ⚪ Aceptado | 1 | D3 |

**Lectura:** los controles de **contenedor, validación de entrada y manejo de errores** están sólidos. El mayor riesgo está en **identidad y autorización** (S1, E1, I5, T1, R1): al ser un stub, un solo cambio, JWT real con roles, cierra cinco amenazas de riesgo alto.

## 6. Plan de mitigación priorizado

| Prioridad | Acción | Amenazas que cierra | Cuándo |
|---|---|---|---|
| 1 | Validar JWT y agregar RBAC por endpoint | S1, E1, I5, T1 | Antes de manejar datos reales |
| 2 | Registrar `actor_id`, rol y `request_id` en el audit log | R1, R2 | Junto con la prioridad 1 |
| 3 | TLS en el Ingress | I3 | Antes de exponer fuera del equipo |
| 4 | Persistir en PostgreSQL con cifrado y audit append-only con hash | T2, T4, I1, D2 | Siguiente hito de datos |
| 5 | Deshabilitar `/docs` en producción y agregar rate limiting en el Ingress | I4, D1 | Cambio pequeño |
| 6 | `automountServiceAccountToken: false` y `NetworkPolicy` | E3, E4 | Cambio pequeño de manifiestos |

## 7. Relación con los controles del pipeline (S09)

| Control | Amenazas que reduce | Estado |
|---|---|---|
| SAST (Semgrep, reglas propias) | T3 (patrones inseguros en el código) | En implementación |
| SCA y SBOM CycloneDX | T5 (dependencias vulnerables) | En implementación |
| Escaneo de secretos (gitleaks) | Credenciales en el repositorio | En implementación |
| Protección de rama y checks requeridos | T5 (cambios sin revisión ni controles) | En implementación |

> Actualizar esta tabla y la columna *Estado real* de la sección 4 cuando cada control quede activo.

## 8. Mantenimiento de este documento

- Al cerrar una amenaza, cambiar su estado y enlazar el PR que la resolvió.
- Si cambia la arquitectura (por ejemplo, se agrega PostgreSQL), revisar T2, T4, I1 y D2.
- Revisar el modelo completo antes de cada hito de entrega.
