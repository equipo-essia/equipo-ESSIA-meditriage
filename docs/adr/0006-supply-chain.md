# ADR 0006 — Firma, attestation y cadena de suministro

- **Estado:** Aceptado con salvedades
- **Fecha:** 2026-11-12
- **Decisores:** Martín Garrido, Cristóbal Araos, Martín Durán, Alonso Plane
- **Relacionado:** PR #60, `docs/falco-alertas.md`, ADR 0004 y ADR 0005

## 1. Contexto

La S10 exige integrar DAST, escaneos de IaC y de contenedor, firma de imágenes,
attestation SLSA, una policy de admisión y reglas Falco. La imagen se publica en
GHCR por digest y el clúster debe rechazar imágenes no firmadas.

Amenazas principales: T5 (supply chain), T3 (inyección), T4 (autenticación) y
T7 (misconfiguración), según `docs/threat-model.md`.

## 2. Decisión

- Construir una sola imagen y publicarla por digest.
- Firmar con Cosign en modo keyless, usando el OIDC de GitHub Actions (job
  `sign-and-attest` de `ci.yml`, que solo corre en push a `main`).
- Fijar Cosign a la versión `v2.6.5` y el instalador por SHA.
- Generar una attestation `slsaprovenance` (predicate SLSA v0.2).
- Verificar firma y attestation dentro del pipeline.
- Aplicar `k8s/policies/require-signature.yaml` (Kyverno) en modo Enforce.
- Ejecutar Falco con tres reglas propias (`falco/rules-custom.yaml`).
- DAST con ZAP baseline, IaC con Checkov y contenedor con Trivy (`scans.yml`, que
  `ci.yml` ejecuta antes de construir la imagen).

## 3. Alternativas consideradas

- Claves propias (GPG o Cosign con llave): más control, pero hay que custodiarlas
  y rotarlas manualmente.
- Docker Content Trust / Notary v2: menos integrado con GHCR y Cosign.
- Attestations nativas de GitHub: más simples, pero cambian el modelo de
  verificación.
- `slsa-github-generator`: más fuerte para SLSA L3, pero más complejo.
- No firmar: descartado.

## 4. Política de firma y verificación

- Identidad definitiva:
  `https://github.com/equipo-essia/equipo-ESSIA-meditriage/.github/workflows/ci.yml@refs/heads/main`
- Emisor: `https://token.actions.githubusercontent.com`
- **Excepción temporal:** el digest desplegado
  (`ghcr.io/equipo-essia/meditriage@sha256:6f90a5ba7122abc570d69790cf7dc71f92928874b93db70f65fd8d8cb9b84b21`)
  se firmó desde la rama `feature/sign-and-attest`, por lo que la policy acepta
  también esa identidad. Se retira cuando el Deployment apunte a un digest firmado
  desde `main`.
- La policy incluye además la referencia `ghcr.io/guffy0921/meditriage*`, usada solo
  para demostrar el rechazo de una imagen sin firma. Debe retirarse al cerrar la
  prueba.
- La policy rechaza los pods del namespace `meditriage` cuya imagen no tenga una
  firma válida de una de esas identidades.

## 5. SLSA

La attestation es `slsaprovenance` (SLSA v0.2). La provenance la genera el propio
workflow y su predicate no declara la completitud de parámetros, entorno ni
materiales (por defecto, `false` en SLSA v0.2). Por tanto:

- Es **SLSA Build L2 con salvedad**, no L3.
- No se debe afirmar que la provenance fue generada por un builder independiente.
- Para L3 haría falta `slsa-github-generator` o un builder gestionado.

## 6. Falco

Reglas propias (`falco/rules-custom.yaml`):

1. Shell interactivo en un pod de MediTriage (prioridad Critical).
2. Escritura en `/etc` o `/app` (Error).
3. Conexión saliente inesperada (Error).

Se verificó que las tres reglas generan alertas al provocarlas desde un contenedor
de depuración (`kubectl debug`); la evidencia son los logs del pod de Falco. La ruta
de alertas (Falcosidekick, Alertmanager, Slack o email) está descrita en
`docs/falco-alertas.md` como diseño y no está desplegada.

## 7. Limitaciones y riesgos residuales

- La provenance la genera el propio workflow; no es SLSA L3.
- Los escaneos de imagen y DAST construyen su propia imagen y pueden no analizar
  exactamente los bytes del digest firmado. Queda como riesgo residual.
- Trivy usa `ignore-unfixed`. Hay 21 excepciones VEX en `.trivyignore` (CVE HIGH del
  sistema de la imagen base distroless), cada una con justificación y vencimiento el
  2026-12-09. Al vencer, el job vuelve a fallar hasta renovar la excepción o
  actualizar la imagen base.
- Si la policy estuviera en modo Audit, no bloquearía.
- El SBOM de `security.yml` es de las fuentes, no de la imagen, y no está firmado.
- ZAP baseline es pasivo y sin autenticación; el escaneo activo de la API
  autenticada queda pendiente.
- La excepción temporal de la rama `feature/sign-and-attest` y la referencia
  `guffy0921` siguen en la policy hasta que exista un digest firmado desde `main`.
- Keyless depende de Fulcio y Rekor públicos: si Sigstore falla, el release se
  bloquea.
- La ruta de alertas de Falco no está desplegada.
- El job `sign-and-attest` aparece omitido en los PRs, porque solo corre en push a
  `main`. La firma se comprobó sobre el digest de la rama de pruebas.

## 8. Operación

- Verificar una imagen: sección "Cómo verificar una imagen firmada (S10)" del
  `README.md`.
- Revisar las excepciones de `.trivyignore` antes del 2026-12-09.
- Ante una alerta de Falco, seguir `docs/falco-alertas.md`.

## 9. Evidencias

- Run del pipeline: <RUN_URL>
- Checks del PR #60: `docs/img/s10-checks-verdes.png`
- `cosign verify` (verificación externa):
  ```
  <pegar salida>
  ```
- `cosign verify-attestation` (verificación externa):
  ```
  <pegar salida>
  ```
- Imagen firmada aceptada: `docs/img/s10-04-pods-imagen-firmada.png`
- Policy en Enforce: `docs/img/s10-05-policy-enforce.png`
- Imagen sin firma rechazada: `docs/img/s10-06-rechazo-sin-firma.png`
- Alertas de Falco: `docs/img/s10-07-falco-alertas.png`
- Reporte ZAP: artefacto `zap-baseline-report` del run
- Pods de Kyverno y Falco: `docs/img/s10-01-kyverno-pods.png`,
  `docs/img/s10-02-falco-pods.png`

## 10. Referencias

- PR #60
- `k8s/policies/require-signature.yaml`
- `falco/rules-custom.yaml`
- `docs/falco-alertas.md`
