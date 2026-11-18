# FinOps — Modelo de costo de MediTriage

**Versión:** 1.0 · **Fecha:** 2026-11-18 · **Responsable:** Martín Garrido (Product Owner)
**Estado:** **estimación del diseño objetivo en AWS**, no una factura. El despliegue demostrado en el repo es local/GHCR sobre Docker Desktop; no hay factura de cloud que citar. Los supuestos están explicados para que el panel pueda recalcularlos.

## 1. Supuestos

- Región us-east-1, precios on-demand de referencia, 730 h/mes.
- Volumen de referencia: **5 000 evaluaciones/mes** (~165/día).
- Arquitectura objetivo del ADR 0003/0004: EKS, ALB, un nodo `t3.small`, RDS `db.t3.micro`, S3 + CloudWatch, ECR, SNS/SQS, NAT Gateway.
- Sin descuentos por compromiso, ni Free Tier.

## 2. Costo mensual estimado

| Ítem | Supuesto unitario | USD/mes |
|---|---|---|
| EKS control plane | 0,10 USD/h | 73,00 |
| Nodo de cómputo (1 × t3.small) | 0,0208 USD/h | 15,18 |
| ALB + LCU | 0,0225 USD/h + tráfico | 21,00 |
| RDS db.t3.micro + 20 GB | 0,017 USD/h + almacenamiento | 14,40 |
| NAT Gateway | 0,045 USD/h + datos | 33,00 |
| S3 + CloudWatch Logs | Retención 30 días | 8,00 |
| ECR (imágenes por digest) | ~10 GB | 2,00 |
| SNS + SQS | Volumen bajo | 2,00 |
| **Total estimado** | | **≈ 169 USD/mes** |

## 3. Costo por unidad y break-even

| Métrica | Fórmula | Valor |
|---|---|---|
| Costo por evaluación | 169 / 5 000 | **≈ 0,034 USD/triage** |
| A 10 000 evaluaciones/mes | 169 / 10 000 | ≈ 0,017 USD/triage |
| Punto de equilibrio hipotético | 169 / 0,10 USD por evaluación cobrados al hospital | **≈ 1 700 evaluaciones/mes** |
| Alternativa por sede | 4 sedes × 50 USD/mes = 200 USD | cubre 169 USD con margen estrecho |

El precio de 0,10 USD/evaluación es **un supuesto de negocio, no un precio medido**. Se presenta para mostrar la estructura de costos, no como modelo de ingresos validado.

## 4. Tagging

Todo recurso del diseño objetivo lleva estas etiquetas (declaradas aquí como política; no hay recursos cloud reales versionados en el repo):

| Tag | Valor | Uso |
|---|---|---|
| `app` | `meditriage` | Agrupación de costo del producto |
| `env` | `dev`, `staging`, `prod` | Separar entornos en la factura |
| `owner` | `martin.duran` / `cristobal.araos` | Responsable de cada recurso |
| `cost-center` | `urgencias` | Imputación al área de negocio |
| `data-classification` | `sensible` | Recordatorio de Ley 21.719 |

## 5. Palancas aplicadas y cómo medirlas

| Palanca | Antes | Después | Medición antes/después |
|---|---|---|---|
| **Techo del HPA** | Réplicas sin límite superior en el dimensionamiento inicial | `maxReplicas: 5` con `requests.cpu: 100m` (`k8s/hpa.yaml`) | Techo de CPU solicitado: 2 réplicas = 200m → 5 réplicas = 500m (2,5×). Coste máximo estimado de cómputo: ~1,52 USD/mes (2 réplicas) → ~3,80 USD/mes (5 réplicas), con 0,0104 USD por vCPU-h. Se verifica con `kubectl get hpa -w` y la factura del nodo. |
| **Caché de capas en CI** | Cada job `build-and-push`, `container-scan` y `dast` reconstruía la imagen desde cero | `cache-from`/`cache-to` de GitHub Actions con `scope=scans` en los tres jobs | Comparar la duración del step «Build» en un run sin caché contra el siguiente con caché, en la pestaña Actions. **Pendiente de pegar los segundos reales**: no se inventan tiempos. |

**Honestidad:** la primera palanca es una configuración verificable en el repo con una estimación numérica derivada de ella. La segunda está aplicada en el código, pero el ahorro en segundos queda pendiente de medir en un run real. No se presenta como medición completada.

## 6. Riesgos

- El modelo asume un solo nodo; con el HPA al máximo puede hacer falta otro nodo (~+15 USD/mes).
- NAT Gateway es una partida desproporcionada para el volumen; mover los servicios a endpoints de interfaz la reduciría.
- Sin tagging real en AWS, la factura no se puede repartir por ambiente: es acción pendiente del despliegue productivo.
- El costo por triage cae con volumen porque casi todo el gasto es fijo: el break-even depende del volumen real.

## 7. Evidencias en el repo

- `k8s/hpa.yaml`, `k8s/deployment.yaml` (requests/limits y techo de réplicas)
- `.github/workflows/ci.yml`, `.github/workflows/scans.yml` (caché de GHA)
- `docs/adr/0003-cloud-style.md`, `docs/adr/0004-datos-y-eventos.md`, `docs/adr/0008-resiliencia-finops.md`
- `docs/arch/managed-services.md` (selección de servicios)
