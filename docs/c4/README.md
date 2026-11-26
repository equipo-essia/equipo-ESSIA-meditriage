# Modelo C4 · MediTriage

| Nivel | Archivo | Qué muestra | Estado |
|---|---|---|---|
| L1 — Contexto | [`l1-context.puml`](l1-context.puml) · [`l1-context.png`](l1-context.png) | Usuarios, sistema y sistemas externos | **Diseño objetivo**: incluye SPA, RDS, SNS/SQS, worker de IA |
| L2 — Contenedores | [`l2-container.puml`](l2-container.puml) · [`l2-container.png`](l2-container.png) | API, read models, broker, base de datos | **Diseño objetivo**: RDS/SQS/Lambda/OpenSearch no están implementados en `main` |
| L3 — Componentes | [`l3-component.puml`](l3-component.puml) · [`l3-component.png`](l3-component.png) | Componentes reales del pod: middleware, auth, `rules-v0`, `STORE`, modelos | **Estado real en `main`** |

> Para la defensa: mostrar los tres niveles y decir explícitamente cuáles son diseño y cuál es código que corre. Lo implementado hoy es una API FastAPI en memoria con reglas deterministas; el resto está en los ADR 0002 y 0004 como roadmap. Generar PNG con `plantuml -tpng docs/c4/l3-component.puml` si se quiere la imagen versionada.

---

### Mapeo de Puertos y Protocolos

* **SPA Web ↔ API Backend:** Comunicación bidireccional externa vía **HTTPS (Puerto 443)** utilizando *payloads* en formato JSON, y **WebSockets** para actualizar el tablero en tiempo real. Garantiza el cifrado en tránsito desde el dispositivo del usuario hasta los servidores.
* **API Backend ↔ Base de Datos (PostgreSQL / Amazon RDS):** Conexión interna vía **TCP/TLS (Puerto 5432)**. El cambio de estado y la fila de `outbox_event` se escriben en la misma transacción (Patrón Outbox).
* **API Backend ↔ Broker de Mensajería (Amazon SNS FIFO + SQS FIFO):** El relay del Patrón Outbox publica los eventos en SNS FIFO, que los reparte a una cola SQS FIFO por consumidor (Servicio de IA, Auditoría y proyectores de lectura). Se usa la **API de AWS sobre HTTPS (Puerto 443)**. Publicar desde el relay evita bloquear el hilo principal de la API y conserva el orden de los eventos por `encounter_id`.
* **Broker de Mensajería ↔ Servicio de IA (AWS Lambda):** El Servicio de IA recibe `triage.requested` desde su cola SQS y publica `triage.completed` o `triage.failed` por el mismo broker (AWS API / HTTPS). No hay una llamada directa entre la API y la IA: la comunicación es asíncrona. El requisito de latencia (< 3 s, p95) se mide de extremo a extremo, incluyendo el paso por el broker.
* **Broker de Mensajería ↔ Proyectores de Lectura ↔ Read Models:** Los proyectores (AWS Lambda) consumen los eventos y actualizan OpenSearch (dashboard de triage, HTTPS) y Redis/ElastiCache (sala de espera, TLS). La API consulta estos read models (CQRS).

### Flujo de Enmascaramiento de PII (Cumplimiento Ley 19.628)

1. **Captura en Texto Plano:** La SPA Web envía el RUT y el nombre del paciente a la API Backend mediante HTTPS.
2. **Punto de Intercepción (Backend):** La API Backend es el único componente que conoce la identidad real del paciente para poder guardar el registro de ingreso y el consentimiento informado en la Base de Datos.
3. **Proceso de Enmascaramiento:** Antes de insertar un evento en `outbox_event`, la API Backend ejecuta una función de enmascaramiento (hash con clave HMAC-SHA256 o tokenización) sobre el RUT, nombre y cualquier dato de contacto. El payload del evento se construye ya enmascarado.
4. **Derivación Segura:**
    * El **Servicio de IA** recibe exclusivamente los síntomas, signos vitales y un `encounter_id` (UUID anonimizado) mediante el evento `triage.requested`. La IA nunca lee el RUT.
    * La cola de **Auditoría** recibe el evento de la decisión de IA (`triage.completed`) asociado a `encounter_id` y `rut_hash`, garantizando que los logs inmutables a 5 años no contengan Información de Identificación Personal directa, previniendo fugas de datos de salud sensibles.
