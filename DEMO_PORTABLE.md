# Demo portable de MediTriage (cualquier PC)

Este folder contiene **la API real** (`main.py`) y un panel visual de dos pasos:
**Datos del paciente → Demo en vivo**. No necesita Kubernetes, AWS, Postgres,
Docker ni acceso a internet después de la primera instalación.

> Esta entrega también incluye `demo/` con la interfaz paso a paso y el mapa de
> evidencia en `ENTREGA.md`. Este archivo describe la **alternativa portable de un
> clic**: misma API `main.py`, panel de dos pasos y sin depender de la ruta de nadie.

## Requisito único

| Opción | Qué necesita la otra PC |
|---|---|
| **Recomendada** | Python **3.10+** y un navegador |
| Sin internet | Python 3.10+ y la carpeta `wheels/` (ver más abajo) |
| Opcional | Docker |

Para comprobar Python:

```powershell
python --version     # Windows
python3 --version    # macOS / Linux
```

## Opción A — Un clic (Windows)

1. Copia **toda esta carpeta** a la otra PC (incluye `main.py`, `demo_*.py`,
   `start_demo.*`, `requirements.txt`).
2. Doble clic en **`start_demo.bat`**.
3. Se abre solo `http://localhost:8000/demo`.
4. Completa los datos del paciente y pulsa **«▶ Cargar datos y ejecutar demo»**.
5. Para detener: `Ctrl+C` en la ventana negra, o cierra esa ventana.

La primera vez tarda ~30 s porque crea `.venv-demo/` e instala `fastapi`,
`uvicorn` y `pydantic`. Las veces siguientes arranca en 1–2 s.

## Opción A — macOS / Linux

```bash
cd carpeta-demo
chmod +x start_demo.sh
./start_demo.sh
```

Se abre `http://localhost:8000/demo`. Si no se abre solo, cópialo tú.

## Opción B — Sin internet

En **una PC con internet**, dentro de esta carpeta:

```powershell
python start_demo.py --download-wheels
```

Eso crea `wheels/` con los paquetes. Copia **toda la carpeta** (con `wheels/`)
a la PC sin conexión. El lanzador detecta `wheels/` e instala con
`pip --no-index --find-links=wheels`. No contacta a PyPI.

> Importante: la PC de destino debe tener la **misma versión mayor de Python**
> (por ejemplo 3.11) para que los wheels sean compatibles.

## Opción C — Docker (si la PC lo tiene)

```powershell
docker build -f demo.Dockerfile -t meditriage-demo .
docker run --rm -p 8000:8000 meditriage-demo
```

Abre `http://localhost:8000/demo`. El contenedor no intenta abrir navegador.

## Opciones del lanzador

```powershell
start_demo.bat --port 8080          # si quieres otro puerto
start_demo.bat --no-browser         # no abre el navegador
start_demo.bat --download-wheels    # preparar modo offline
```

También funcionan variables de entorno: `DEMO_HOST`, `DEMO_PORT`, `DEMO_NO_BROWSER=1`.

**Si el puerto 8000 está ocupado**, el servidor busca automáticamente el siguiente
libre y lo imprime en pantalla, por ejemplo:

```
Aviso : el puerto 8000 estaba ocupado; se usa 8001.
Panel : http://localhost:8001/demo
```

El encabezado del panel muestra siempre el host/puerto real.

## Solución de problemas

| Síntoma | Causa / solución |
|---|---|
| «no se encontró Python 3.10» | Instala Python desde python.org. En Windows marca **Add Python to PATH**. |
| En Ubuntu: `ensurepip is not available` | `sudo apt install python3-venv` y vuelve a correr. |
| `ERROR: no se pudieron instalar las dependencias` | Sin internet: usa `--download-wheels` en otra PC y copia `wheels/`. |
| `No se encontró main.py` | Copia **todos** los archivos; el lanzador usa rutas relativas a la carpeta. |
| Pantalla en blanco | Abre la URL exacta que imprimió la terminal, con `/demo` al final. |
| El contador de auditoría no es 2 | Pulsa **«↺ Limpiar pantalla»** o recarga: cada ejecución limpia el `STORE` en memoria. |
| Acentos raros en la consola | Es solo la terminal de Windows; el panel y las respuestas JSON están en UTF-8 correcto. |

## Qué decir en la defensa si se usa en otra PC

> «Esto no es un video ni un mock: es la misma API FastAPI del repo corriendo en
> local, con su `main.py` sin modificar. El despliegue real en Kubernetes está
> evidenciado en `k8s/README.md` y en `docs/img/`.»

## Archivos de esta carpeta

| Archivo | Función |
|---|---|
| `main.py` | API real (sin cambios) |
| `demo_server.py` | API + panel en un puerto, `/demo/reset`, puerto libre automático |
| `demo_panel.html` | Interfaz: datos del paciente y demo en vivo |
| `start_demo.py` | Bootstrap portable (venv + dependencias + arranque) |
| `start_demo.bat` / `start_demo.sh` | Doble clic / script por sistema operativo |
| `demo_s18.py` | Demo alternativa de terminal (solo stdlib) |
| `demo.Dockerfile` | Opción contenedor |
| `requirements.txt` | Únicas 3 dependencias, ya versionadas en el repo |
