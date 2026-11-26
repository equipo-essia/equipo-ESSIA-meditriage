# Demo portable con Docker (opcional). El Dockerfile del proyecto es de producción;
# este incluye el panel y no es distroless para poder abrir el server con un comando.
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DEMO_NO_BROWSER=1

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py demo_server.py demo_panel.html ./

# La demo no escribe en disco; ejecutarla como usuario no root cierra el hallazgo
# dockerfile.security.missing-user.missing-user del SAST.
RUN useradd --create-home --uid 10001 demo
USER demo

EXPOSE 8000
CMD ["python", "demo_server.py", "--host", "0.0.0.0", "--port", "8000"]
