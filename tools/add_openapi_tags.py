"""Agrega `tags` a las 5 operaciones de api/openapi.yaml (corrige los 5 warnings
operation-tags de Spectral). Idempotente. Uso: python tools/add_openapi_tags.py"""

import pathlib

F = pathlib.Path("api/openapi.yaml")
MAP = {
    "registerPatient": "Pacientes",
    "createTriageEvaluation": "Triage",
    "updateTriageEvaluation": "Triage",
    "getTriageBoard": "Triage",
    "getAuditLogs": "Auditoria",
}
lines = F.read_text(encoding="utf-8").splitlines(keepends=True)
out, n = [], 0
for i, ln in enumerate(lines):
    out.append(ln)
    s = ln.strip()
    if s.startswith("operationId:"):
        op = s.split(":", 1)[1].strip()
        nxt = lines[i + 1].strip() if i + 1 < len(lines) else ""
        if op in MAP and not nxt.startswith("tags:"):
            ind = ln[: len(ln) - len(ln.lstrip())]
            out += [f"{ind}tags:\n", f"{ind}  - {MAP[op]}\n"]
            n += 1
text = "".join(out)
if "\ntags:\n" not in text:
    top = (
        "tags:\n  - name: Pacientes\n    description: Registro y consentimiento\n"
        "  - name: Triage\n    description: Sugerencia ESI, confirmación y tablero\n"
        "  - name: Auditoria\n    description: Registro de decisiones\n\n"
    )
    text = text.replace("\npaths:\n", "\n" + top + "paths:\n", 1)
F.write_text(text, encoding="utf-8")
print(f"{n} operaciones actualizadas")
