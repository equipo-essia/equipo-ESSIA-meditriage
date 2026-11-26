# Runbook operativo — MediTriage API

**Alcance:** clúster Kubernetes con namespace `meditriage`, imagen `ghcr.io/equipo-essia/meditriage` fijada por digest.
**Regla:** si el procedimiento no está aquí, no se improvisa en producción: se escala al DevSecOps de turno.

## 0. Comprobación inicial (todos los incidentes)

```bash
kubectl get pods -n meditriage -o wide
kubectl get hpa -n meditriage
kubectl get events -n meditriage --sort-by=.lastTimestamp | tail -20
curl -fsS http://<ingress>/health
```

## 1. El pod no pasa `readinessProbe`

1. `kubectl describe pod -n meditriage <pod>` → revisar eventos y `Readiness probe failed`.
2. `kubectl logs -n meditriage <pod> --tail=200`.
3. Causas habituales: `APP_ENV`/`LOG_LEVEL` mal inyectados desde el ConfigMap, puerto 8000 cambiado, proceso caído por estado en memoria corrupto.
4. Si el error es de configuración: corregir `k8s/configmap.yaml` en un PR, no con `kubectl edit`.
5. Si el pod está mal: `kubectl delete pod -n meditriage <pod>` y esperar al ReplicaSet.

## 2. Errores 5xx o latencia alta

1. Confirmar con `kubectl top pod -n meditriage` si CPU está en el límite de 500m.
2. Revisar `kubectl get hpa -n meditriage`: si `TARGETS` supera 50 % y `REPLICAS` no sube, revisar el HPA.
3. Generar carga sintética controlada siguiendo `k8s/README.md` y observar el escalado.
4. **Ojo:** con varias réplicas el estado no es compartido (`docs/operacion/post-mortem.md`); un 404 de `unknown-patient` puede ser un problema de réplica, no de datos.
5. Rollback si el fallo empezó tras un despliegue: revertir el PR de GitOps que cambió el digest.

## 3. Kyverno rechaza el pod (imagen sin firma)

1. `kubectl get policyreport -A` y `kubectl describe clusterpolicy require-image-signature`.
2. Verificar la firma en local con los comandos del `README.md` (`cosign verify` y `cosign verify-attestation`).
3. Causas habituales: la imagen se construyó en una rama distinta de `main`, o el digest promovido no corresponde al job `sign-and-attest`.
4. No se relaja la política en Enforce; se corrige el digest o se firma desde `main`.
5. Las excepciones temporales de la policy tienen fecha límite 2026-12-09 (ADR 0006).

## 4. Alerta de Falco

1. Seguir `docs/falco-alertas.md`: identificar regla, prioridad, namespace, pod y imagen.
2. Aislar o recrear el pod según la regla; si hay acceso a secretos, rotar credenciales.
3. Registrar el ticket con línea de tiempo y evidencia.
4. Validar las reglas con `falco --validate -f falco/rules-custom.yaml` tras cualquier cambio.

## 5. Rotación de secretos

| Secreto | Dónde vive | Quién lo rota | Cadencia |
|---|---|---|---|
| `GITHUB_TOKEN` | GitHub Actions, efímero por run | GitHub automáticamente | Cada run |
| `GITOPS_TOKEN` | GitHub → Settings → Secrets and variables → Actions | Martín Durán | Cada 90 días (`docs/12-factor-checklist.md`) |
| `DATABASE_URL` | Secret de K8s `meditriage-secrets` (hoy placeholder `CHANGEME`) | Martín Durán | Al implementar PostgreSQL y ante cualquier sospecha |

**Ningún secreto se versiona en el repo.** Para actualizar el Secret de Kubernetes sin guardar el valor en un archivo:

```bash
kubectl create secret generic meditriage-secrets -n meditriage \
  --from-literal=DATABASE_URL='<valor-nuevo>' \
  --dry-run=client -o yaml | kubectl apply -f -
```

Tras rotar `GITOPS_TOKEN`, verificar que el job `promote-to-gitops` sigue funcionando en el siguiente push a `main`.

## 6. Recuperación ante desastre (DR)

Objetivo: RTO 30 min, RPO 15 min **una vez persistida la base de datos**; hoy el RPO real no se cumple.

```bash
kubectl apply -k k8s/
kubectl rollout status deployment/meditriage-api -n meditriage
cosign verify --certificate-identity <identidad> --certificate-oidc-issuer <issuer> <imagen>@<digest>
```

La imagen se reconstruye desde el digest firmado en GHCR; no se recompila código en el clúster.

## 7. Despliegue y rollback

- Despliegue: el job `promote-to-gitops` abre un PR en el repo GitOps con el digest nuevo; Argo CD sincroniza.
- Rollback: revertir ese PR (o reapuntar al digest anterior) y esperar `kubectl rollout status`.
- Prohibido: `kubectl set image` directo en producción o editar manifiestos a mano.
