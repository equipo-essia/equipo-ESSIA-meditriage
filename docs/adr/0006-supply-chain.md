# ADR 0006 — Firma, attestation y cadena de suministro

- **Estado:** Aceptado con salvedades
- **Fecha:** 2026-11-12
- **Decisores:** Martín Garrido, Cristóbal Araos, Martín Durán, Alonso Plane
- **Relacionado:** PR #<PR>, run #<RUN>, `docs/falco-alertas.md`

## 1. Contexto

S10 exige integrar DAST, escaneos de IaC y contenedor, firma de imágenes,
attestation SLSA, policy de admisión y reglas Falco. La imagen se publica en
GHCR por digest y el clúster debe rechazar imágenes no firmadas.

Amenazas principales: T5 (supply chain), T3 (inyección), T4 (auth),
T7 (misconfiguración).

## 2. Decisión

- Construir una sola imagen y publicarla por digest.
- Firmar con Cosign en modo keyless usando OIDC de GitHub Actions.
- Generar attestation `slsaprovenance` con predicate SLSA v0.2.
- Verificar firma y attestation dentro del pipeline.
- Aplicar `k8s/policies/require-signature.yaml` en modo Enforce.
- Ejecutar Falco con tres reglas propias y enrutar alertas según
  `docs/falco-alertas.md`.
- DAST con ZAP baseline; IaC con Checkov; imagen con Trivy.

## 3. Alternativas consideradas

- Claves GPG propias: más control, pero gestión y rotación manual.
- Docker Content Trust / Notary v2: menos integrado con GHCR y Cosign.
- Attestations nativas de GitHub: más simples, pero cambian el modelo de
  verificación.
- `slsa-github-generator`: más fuerte para L3, más complejo.
- No firmar: descartado.

## 4. Política de firma y verificación

- Identidad final: `https://github.com/equipo-essia/equipo-ESSIA-meditriage/.github/workflows/ci.yml@refs/heads/main`
- Emisor: `https://token.actions.githubusercontent.com`
- La policy acepta únicamente esa identidad y ese emisor.
- Durante las pruebas se acepta la identidad de la rama de integración;
  antes del cierre se fija a `main`.
- La policy rechaza imágenes sin firma y, si se decide, sin attestation
  `slsaprovenance`.

## 5. SLSA

La attestation es `slsaprovenance` v0.2. La provenance la genera el propio
workflow, con `metadata.completeness` en `false` para parámetros, entorno y
materiales. Por tanto:

- Es **SLSA Build L2 con salvedad**, no SLSA L3.
- No se debe afirmar que la provenance es generada por un builder
  independiente.
- Para L3 se necesitaría `slsa-github-generator` o un builder gestionado.

## 6. Falco

Las reglas y la ruta de alertas están en `docs/falco-alertas.md`.
Reglas mínimas:

1. Shell dentro del contenedor.
2. Escritura bajo `/etc`.
3. Conexión saliente inesperada.
4. (Opcional) Lectura de archivos sensibles.

## 7. Limitaciones y riesgos residuales

- La provenance la genera el propio workflow (`completeness=false`); no es
  SLSA 2 pleno ni L3.
- Los escaneos de imagen/DAST pueden reconstruir la imagen y no analizar
  exactamente los bytes del digest firmado. Mitigación: build once y escanear
  `IMAGE@DIGEST`; si no se corrige, queda como riesgo residual.
- Trivy usa `ignore-unfixed`; las excepciones VEX están en `.trivyignore`
  con expiración y revisión mensual.
- La firma se verifica en CI y en admisión; si la policy está en Audit,
  no bloquea.
- El SBOM de `security.yml` es de fuentes, no de la imagen, y no está
  firmado.
- ZAP baseline es pasivo y sin autenticación; el escaneo activo de la API
  autenticada queda pendiente.
- Keyless depende de Fulcio/Rekor público; si Sigstore falla, el release
  se bloquea.

## 8. Operación

- Verificar manualmente:
  `cosign verify --certificate-identity ... --certificate-oidc-issuer ... IMAGE@DIGEST`
- Verificar attestation:
  `cosign verify-attestation --type slsaprovenance ...`
- Revisar excepciones Trivy antes de su expiración.
- Ante una alerta Falco: seguir la ruta de `docs/falco-alertas.md`.

## 9. Evidencias

- Run del pipeline: <RUN_URL>
- `cosign verify`: <salida o enlace>
- `cosign verify-attestation`: <salida o enlace>
- Reporte ZAP: <artefacto>
- Policy: imagen firmada aceptada / imagen sin firma rechazada
- Falco: alertas de las 3 reglas

## 10. Referencias

- PR #<PR>
- `docs/falco-alertas.md`
- `k8s/policies/require-signature.yaml`
- `falco/rules-custom.yaml`
