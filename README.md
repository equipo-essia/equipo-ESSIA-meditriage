## Cómo verificar una imagen firmada (S10)

Las imágenes que publica el CI se firman con Cosign (keyless, OIDC de GitHub Actions)
y llevan una attestation de provenance SLSA. Se pueden verificar sin llaves ni acceso
al repositorio. Requisito: [Cosign](https://github.com/sigstore/cosign) instalado.

1. Verificar la firma (reemplazar `<DIGEST>`):
   ```bash
   cosign verify \
     --certificate-identity "https://github.com/equipo-essia/equipo-ESSIA-meditriage/.github/workflows/ci.yml@refs/heads/main" \
     --certificate-oidc-issuer "https://token.actions.githubusercontent.com" \
     ghcr.io/equipo-essia/meditriage@<DIGEST>
   ```
2. Verificar la attestation de provenance:
   ```bash
   cosign verify-attestation --type slsaprovenance \
     --certificate-identity "https://github.com/equipo-essia/equipo-ESSIA-meditriage/.github/workflows/ci.yml@refs/heads/main" \
     --certificate-oidc-issuer "https://token.actions.githubusercontent.com" \
     ghcr.io/equipo-essia/meditriage@<DIGEST>
   ```

Si ambos comandos terminan sin error, la imagen fue construida y firmada por el workflow
`ci.yml` de este repositorio en la rama `main`. Si fallan, no debe desplegarse: Kyverno
también la rechaza en el clúster.

Limitación: la provenance la genera el propio workflow, por lo que el nivel SLSA es 2
con salvedad y no 3 (ver [ADR 0006](docs/adr/0006-supply-chain.md)).