# Ruta de alertas de Falco — MediTriage

## 1. Objetivo

Definir qué hace el equipo cuando Falco detecta una de las reglas propias
de `falco/rules-custom.yaml`.

## 2. Componentes

Falco DaemonSet -> Falcosidekick -> Alertmanager/Slack/email -> guardia
-> ticket de incidente.

- **Falco:** captura syscalls con eBPF/modern probe.
- **Falcosidekick:** recibe eventos y los envía al canal configurado.
- **Alertmanager/Slack/email:** notificación primaria.
- **Guardia:** DevSecOps de turno.
- **Ticket:** issue de seguridad o incidente interno.

## 3. Reglas y enrutamiento

Las prioridades son las declaradas en `falco/rules-custom.yaml` (no se han inventado
ni suavizado valores):

| Regla (`falco/rules-custom.yaml`) | Prioridad | Qué detecta | Canal | Acción inicial |
|---|---|---|---|---|
| Shell interactivo en pod de MediTriage | CRITICAL | `sh`, `bash`, `ash`, `dash`, `zsh` con TTY dentro de un pod | #meditriage-security + email | Aislar pod, revisar proceso, recolectar logs |
| Escritura en `/etc` o `/app` en pod de MediTriage | ERROR | Escritura en rutas protegidas del contenedor | #meditriage-security | Comparar con imagen, revisar drift, recrear pod |
| Conexión saliente inesperada desde pod de MediTriage | ERROR | Conexión a una red no incluida en los rangos privados permitidos | #meditriage-security | Ver destino, revisar DNS, bloquear si es malicioso |
| Lectura de archivo sensible | No implementada | Regla opcional, aún no existe en `falco/rules-custom.yaml` | — | Si se implementa: rotar credenciales y revisar alcance |

## 4. Formato de la alerta

Cada alerta debe incluir:

- Fecha y hora.
- Regla y prioridad.
- Namespace, pod, contenedor e imagen.
- Nodo.
- Salida de Falco.
- labels de Kubernetes.
- Enlace al run/log.

## 5. Escalamiento

1. Guardia revisa la alerta en menos de 15 minutos.
2. Si es un pod de producción, se aísla o se recrea.
3. Si hay acceso a secretos, se rotan credenciales.
4. Se abre ticket con timeline y evidencia.
5. Se actualiza el ADR o las reglas si fue un falso positivo.

## 6. Supresión y tuning

- Allowlist de procesos legítimos.
- Excepciones por namespace y por tiempo limitado.
- Revisión mensual de falsos positivos.
- Toda excepción debe tener justificación, dueño y fecha de expiración.

## 7. Verificación

- Ejecutar `falco --validate` sobre las reglas.
- Provocar cada regla en un pod de prueba.
- Guardar captura/log de las 3 alertas.
- Enlazar la evidencia en el PR.

## 8. Limitaciones

Falco en Docker Desktop puede no funcionar por los drivers de kernel.
Plan B: validar las reglas con `falco --validate`, ejecutarlas en una VM
Linux o Codespaces, y documentarlo en el ADR.
