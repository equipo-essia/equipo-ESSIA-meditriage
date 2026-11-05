# Modelo de amenazas (STRIDE) · API Backend de MediTriage

- **Autor:** Alonso Plane (QA & Architecture Lead)
- **Fecha:** 05/11/2026 · **Versión:** 1.1
- **Componente analizado:** API Backend (`main.py`, FastAPI) y su despliegue en Kubernetes (`k8s/`, `Dockerfile`)
- **Relacionado:** ADR 0002 (monolito modular), ADR 0004 (datos, eventos y plataforma, con su anexo de seguridad), `docs/12-factor-checklist.md`

> **Cómo leer este documento.** La columna *Estado real* describe lo que el repositorio hace **hoy**, verificado contra el código, los manifiestos, los tests y el SBOM. Cada fila es "Implementada" o "Planificada".

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

**Leyenda de estado:** ✅ Implementada (la mitigación principal ya existe en el repositorio) · 📅 Planificada (la mitigación principal aún no existe). En las filas planificadas, "Ya existe" indica lo que sí hay hoy.
**Riesgo** = impacto × probabilidad en el contexto actual (Alto, Medio, Bajo).

### S · Spoofing (suplantación de identidad)

| ID | Amenaza | Riesgo | Mitigación | Estado real | Evidencia |
|---|---|---|---|---|---|
| S1 | Un atacante usa un token inventado (por ejemplo `Bearer x`) y es aceptado como usuario válido. | Alto | Validar JWT contra el proveedor de identidad: firma, expiración, `aud` y `iss`. | 📅 Planificada. Hoy la validación solo comprueba el formato `Bearer <algo>`. | `main.py` (`require_auth`), docstring del módulo |
| S2 | La autenticación se apaga por error con `AUTH_ENABLED=false` en producción. | Medio | Valor por defecto seguro y fallo de arranque si `APP_ENV=production` y la auth está apagada. | 📅 Planificada (fallo de arranque en producción). Ya existe: valor por defecto `true`; el ConfigMap no lo define. | `main.py` línea de `AUTH_ENABLED`; `k8s/configmap.yaml`; `test_auth_can_be_disabled_by_env` |

### T · Tampering (manipulación)

| ID | Amenaza | Riesgo | Mitigación | Estado real | Evidencia |
|---|---|---|---|---|---|
| T1 | Alguien con cualquier token cambia la categoría ESI de una evaluación, incluso varias veces. | Alto | RBAC (solo rol enfermera), estado terminal tras confirmar y auditoría de cada cambio. | 📅 Planificada (RBAC y estado terminal). Ya existe: rango 1 a 5 validado y cada cambio queda en el audit log. | `TriageUpdateIn`, `update_triage_evaluation` |
| T2 | Se altera o se pierde el registro de auditoría. | Alto | Tabla append-only en PostgreSQL, hash encadenado y réplica WORM en S3 (anexo del ADR 0004). | 📅 Planificada (PostgreSQL append-only, hash y WORM). Ya existe: solo `append` y ningún endpoint modifica entradas. Vive en memoria y se pierde al reiniciar el pod. | `_audit`; `test_audit_log_is_append_only` |
| T3 | Datos de entrada maliciosos o fuera de rango. | Medio | Validación de esquema con Pydantic, RUT con módulo 11 y errores uniformes. | ✅ Implementada. Rangos de signos vitales, `fullName` ≤ 200, `symptoms` ≤ 50 elementos y RUT con módulo 11. Mejora planificada: largo máximo por síntoma y formato de `patientId`. | `VitalSigns`, `PatientIn`, `TriageIn`; tests de validación |
| T4 | Con 2 o más réplicas el estado diverge: un PATCH puede caer en un pod que no tiene la evaluación. | Alto | Persistencia compartida (PostgreSQL). | 📅 Planificada (PostgreSQL). Limitación documentada: factor 6 de 12-Factor incumplido. | `STORE`; ADR 0004; `docs/12-factor-checklist.md` |
| T5 | Dependencias o imagen alteradas en la cadena de suministro. | Alto | Versiones fijadas, imagen por digest, SAST, SCA y escaneo de secretos en CI, y firma de artefactos. | ✅ Implementada. Versiones fijadas, imagen por digest, SBOM CycloneDX y SCA en CI. Planificado: subir `starlette` (ver sección 5) y firmar artefactos (S10). | `requirements.txt`, `k8s/deployment.yaml`, `.github/workflows/` |

### R · Repudiation (repudio)

| ID | Amenaza | Riesgo | Mitigación | Estado real | Evidencia |
|---|---|---|---|---|---|
| R1 | Un usuario niega haber confirmado o cambiado una categoría, porque el registro no dice quién fue. | Alto | Guardar `actor_id`, rol, IP y `request_id` en cada entrada del audit log. | 📅 Planificada. Hoy cada entrada guarda solo `evaluationId`, `esiCategory`, `justification` y `timestamp`. | `_audit` |
| R2 | No se pueden correlacionar una petición y sus logs. | Medio | Incluir `trace_id` en los logs y centralizarlos. | 📅 Planificada (`trace_id` en logs y centralización). Ya existe: `trace_id` en cada respuesta de error; no se escribe en los logs. | `problem_response`; `LOG_LEVEL` |
| R3 | No se puede demostrar qué versión del motor tomó una decisión. | Bajo | Justificación con la versión del motor, confirmación humana obligatoria y marca de tiempo UTC. | ✅ Implementada. | `classify_esi` ("motor rules-v0"); `test_audit_log_records_each_decision` |

### I · Information disclosure (filtración de información)

| ID | Amenaza | Riesgo | Mitigación | Estado real | Evidencia |
|---|---|---|---|---|---|
| I1 | RUT y nombre quedan en claro en memoria y en las respuestas. No hay cifrado en reposo. | Alto | Cifrado en reposo con KMS, `rut_hash` con HMAC y minimización de campos. | 📅 Planificada. Depende de la integración con RDS. | `register_patient`; ADR 0004 (anexo) |
| I2 | El RUT aparece en los logs. | Medio | Enmascarar el RUT y no registrar nombre ni síntomas. | ✅ Implementada. Solo se imprime el último carácter del RUT. | `mask_rut`; `test_rut_is_masked_in_logs` |
| I3 | Intercepción del tráfico: el Ingress sirve HTTP sin cifrar. | Alto | TLS en el Ingress (certificado gestionado) y HSTS. | 📅 Planificada. `ingress.yaml` no tiene sección `tls`. | `k8s/ingress.yaml` |
| I4 | Cualquiera lee el contrato completo (`/docs`, `/openapi.json`) y la versión y entorno (`/`). | Medio | Desactivar la documentación interactiva cuando `APP_ENV=production`. | 📅 Planificada. La app se crea con los valores por defecto de FastAPI y `GET /` responde sin autenticación. | `app = FastAPI(...)` |
| I5 | Acceso horizontal: cualquier token lista todas las evaluaciones y todo el audit log, sin límite por rol ni por centro. | Alto | RBAC por rol y por centro de atención. | 📅 Planificada (misma raíz que S1 y E1). | `triage_board`, `audit_logs` |
| I6 | Los errores revelan detalles internos (trazas, rutas). | Medio | Respuestas RFC 7807 sin stack trace y con `trace_id`. | ✅ Implementada. Los errores de validación solo informan campo y motivo. | `_validation_handler`; tests con `_assert_problem` |

### D · Denial of service (denegación de servicio)

| ID | Amenaza | Riesgo | Mitigación | Estado real | Evidencia |
|---|---|---|---|---|---|
| D1 | Ráfaga de peticiones que satura CPU o tumba pods. | Alto | Escalado automático, límites de recursos, probes y rate limiting en el Ingress. | 📅 Planificada (rate limiting en el Ingress). Ya existe: HPA de 2 a 5 réplicas al 50 % de CPU, `requests` y `limits`, probes y `maxUnavailable: 0`. | `k8s/hpa.yaml`, `k8s/deployment.yaml` |
| D2 | Agotamiento de memoria: `STORE` y las claves de idempotencia crecen sin límite y el pod llega al límite de 256 Mi. | Medio | Persistir en BD, expirar claves de idempotencia (TTL) y limitar el tamaño de cada string. | 📅 Planificada. | `STORE`, `_idem_save`; `limits.memory` |
| D3 | Un único `LOCK` serializa las escrituras y degrada la latencia bajo carga. | Bajo | Reemplazar con transacciones de base de datos. | 📅 Planificada (riesgo aceptado en el MVP: mantiene la consistencia mientras el estado está en memoria). | `LOCK` en `main.py` |

### E · Elevation of privilege (elevación de privilegios)

| ID | Amenaza | Riesgo | Mitigación | Estado real | Evidencia |
|---|---|---|---|---|---|
| E1 | Un usuario autenticado ejecuta funciones de otro rol (por ejemplo, un paciente confirma triage o lee la auditoría). | Alto | Roles y permisos por endpoint (paciente, enfermera, médico, auditor). | 📅 Planificada. No existe el concepto de rol. | `require_auth` |
| E2 | Compromiso de la app y escape hacia el nodo. | Alto | Contenedor mínimo, no-root y con capacidades eliminadas. | ✅ Implementada. Distroless sin shell, UID 65532, `readOnlyRootFilesystem`, `allowPrivilegeEscalation: false`, `drop ALL` y `seccompProfile: RuntimeDefault`. | `Dockerfile`, `k8s/deployment.yaml` |
| E3 | El token de la ServiceAccount por defecto está montado en el pod aunque la API no usa la API de Kubernetes. | Medio | `automountServiceAccountToken: false` y una ServiceAccount dedicada. | 📅 Planificada. | `k8s/deployment.yaml` |
| E4 | Movimiento lateral: sin reglas de red, un pod comprometido llega a cualquier otro. | Medio | `NetworkPolicy` con denegación por defecto y excepciones mínimas. | 📅 Planificada. No hay `NetworkPolicy` en `k8s/`. | `k8s/` |

## 5. Hallazgos reales del SCA (starlette 0.36.3)

`fastapi==0.110.0` fija `starlette==0.36.3` (ver `sbom.json`). Los advisories públicos que afectan a esa versión incluyen los siguientes. El reporte del job de SCA es la fuente de verdad: confirmar los identificadores contra él.

| Advisory | Tipo | Corregido en | ¿Alcanzable hoy en MediTriage? |
|---|---|---|---|
| CVE-2024-47874 | DoS por `multipart/form-data` | starlette 0.40.0 | No: ningún endpoint declara `Form` ni `File` |
| CVE-2025-54121 | DoS al procesar archivos grandes en formularios multipart | starlette 0.47.2 | No: mismo motivo |
| CVE-2026-48818 (PYSEC-2026-2281) | **SSRF** y robo de credenciales NTLM por rutas UNC en `StaticFiles` | starlette 1.1.0 | No: no se usa `StaticFiles` y el contenedor corre en Linux (el fallo es solo de Windows) |
| CVE-2026-54283 | DoS por límites ignorados en `application/x-www-form-urlencoded` | consultar el advisory | No: el código no llama a `request.form()` |

**Lectura:** el riesgo real hoy es **bajo**, porque la API solo recibe JSON y no usa las funciones afectadas. Aun así, el riesgo vuelve a ser **alto** apenas alguien agregue un formulario o archivos estáticos, y los escáneres reportarán la versión de todos modos. Mitigación: subir `fastapi` a una versión que permita un `starlette` corregido y volver a correr los tests (tarea de Cristóbal). Mientras tanto, la justificación "no alcanzable" es la base de una excepción VEX con plazo. Esta amenaza se registra en T5.

## 6. Resumen

| Estado | Cantidad | IDs |
|---|---|---|
| ✅ Implementada | 6 | T3, T5, R3, I2, I6, E2 |
| 📅 Planificada | 17 | S1, S2, T1, T2, T4, R1, R2, I1, I3, I4, I5, D1, D2, D3, E1, E3, E4 |

**Lectura:** los controles de **contenedor, validación de entrada, manejo de errores y cadena de suministro** están activos. El mayor riesgo está en **identidad y autorización** (S1, E1, I5, T1, R1): al ser un stub, un solo cambio, JWT real con roles, cierra cinco amenazas de riesgo alto.

## 7. Plan de mitigación priorizado

| Prioridad | Acción | Amenazas que cierra | Cuándo |
|---|---|---|---|
| 1 | Validar JWT y agregar RBAC por endpoint | S1, E1, I5, T1 | Antes de manejar datos reales |
| 2 | Registrar `actor_id`, rol y `request_id` en el audit log | R1, R2 | Junto con la prioridad 1 |
| 3 | TLS en el Ingress | I3 | Antes de exponer fuera del equipo |
| 4 | Persistir en PostgreSQL con cifrado y audit append-only con hash | T2, T4, I1, D2 | Siguiente hito de datos |
| 5 | Deshabilitar `/docs` en producción, no exponer versión ni entorno en `GET /` y agregar rate limiting en el Ingress | I4, D1 | Cambio pequeño |
| 5b | Subir `fastapi` y `starlette` a versiones sin los advisories de la sección 5 | T5 | Antes del cierre de S09 |
| 6 | `automountServiceAccountToken: false` y `NetworkPolicy` | E3, E4 | Cambio pequeño de manifiestos |

## 8. Relación con los controles del pipeline (S09)

| Control | Amenazas que reduce | Estado |
|---|---|---|
| SBOM CycloneDX | T5 (visibilidad de dependencias) | ✅ Generado como artefacto del run del PR #51 y validado (ver 8.1) |
| SCA | T5 (dependencias vulnerables) | ✅ Activo: reportó los advisories de la sección 5 |
| SAST (Semgrep, reglas propias) | T3 (patrones inseguros en el código) | Por confirmar con Martín Durán y Cristóbal |
| Escaneo de secretos (gitleaks) | Credenciales en el repositorio | Por confirmar con Martín Durán |
| Protección de rama y checks requeridos | T5 (cambios sin revisión ni controles) | Por confirmar con Martín Durán |

### 8.1 Validación del `sbom.json`

| Comprobación | Resultado |
|---|---|
| Formato y versión | CycloneDX 1.6, `serialNumber` UUID válido, marca de tiempo 05/11/2026 |
| Componentes | 13, todos con `type`, `name`, `version` y `purl` coherentes entre sí |
| Referencias | `bom-ref` únicos y grafo de dependencias sin referencias rotas |
| Contra `requirements.txt` | `fastapi 0.110.0`, `uvicorn 0.28.0` y `pydantic 2.6.4` coinciden exactamente |
| Dependencias de desarrollo | No hay (`pytest`, `ruff` y similares no aparecen) |
| Licencias | 12 de 13 componentes las declaran |

**Observaciones para mejorar:**
- Incluye `pip` y `setuptools`: el SBOM se generó desde el entorno de CI, no desde la imagen. Esos paquetes no están en el contenedor (las dependencias se instalan con `--target=/deps`), así que podrían generar falsos positivos en el SCA.
- Faltan los componentes raíz (`metadata.component`): el SBOM no identifica a la propia aplicación MediTriage ni su versión.
- Las dependencias transitivas (`anyio`, `h11`, `click`, entre otras) no están fijadas en `requirements.txt`. El SBOM refleja lo que resolvió el CI, y el build de Docker puede resolver otras versiones.
- No incluye hashes, lo cual es normal en este modo de generación.
- La validación fue estructural. La validación contra el esquema oficial JSON de CycloneDX debe correrse con `cyclonedx-cli validate`.

## 9. Mantenimiento de este documento

- Al cerrar una amenaza, cambiar su estado y enlazar el PR que la resolvió.
- Si cambia la arquitectura (por ejemplo, se agrega PostgreSQL), revisar T2, T4, I1 y D2. Si se actualizan las dependencias, regenerar el SBOM y revisar T5 y la sección 5.
- Revisar el modelo completo antes de cada hito de entrega.
