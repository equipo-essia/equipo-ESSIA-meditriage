# ADR 0005: Estrategia de Despliegue con GitOps

**Estado:** Aceptado
**Fecha:** 29 de octubre de 2026

## Contexto

El equipo de MediTriage necesita definir un mecanismo de despliegue continuo (CD) estandarizado, seguro y auditable para los clústeres de Kubernetes (K8s). Actualmente, la integración continua (CI) construye y publica las imágenes en GitHub Container Registry (GHCR), pero carecemos de una estrategia automatizada para sincronizar el estado del clúster con las nuevas versiones.

Se debe decidir si el CI empujará los cambios directamente al clúster (Push) o si el clúster observará los repositorios para trazar los cambios (Pull). Además, es necesario separar los ciclos de vida del código fuente de la aplicación de las configuraciones de infraestructura, establecer reglas de promoción entre entornos (`dev` y `prod`), y lidiar con limitaciones del entorno local de desarrollo, como la falta de asignación de IP para los recursos Ingress.

## Decisión

Se ha decidido adoptar una arquitectura basada en **GitOps con un enfoque Pull**, implementada a través de **Argo CD**, bajo los siguientes lineamientos:

1. **Estrategia Pull (Argo CD) vs. Push (CI directo):** Se utilizará un modelo Pull. Argo CD se ejecutará dentro del clúster de Kubernetes, monitoreando continuamente el repositorio de manifiestos y aplicando los cambios.
2. **Argo CD vs. Flux:** Se seleccionó Argo CD sobre Flux debido a su interfaz gráfica (UI) robusta, que facilita la visibilidad del estado de sincronización y salud de los recursos para todo el equipo de desarrollo, además de su excelente soporte para arquitecturas multi-entorno.
3. **Repositorio GitOps separado:** Los manifiestos de Kubernetes (Helm/Kustomize) vivirán en un repositorio exclusivo, separado del código fuente de la aplicación.
4. **Políticas de entorno:**
* **Entorno `dev`:** Los despliegues serán automáticos. Cuando el CI publique una nueva imagen, se actualizará el repositorio GitOps y Argo CD sincronizará el clúster inmediatamente.
* **Entorno `prod`:** Requerirá intervención manual. Los cambios hacia producción se realizarán mediante un Pull Request (PR) que exigirá la aprobación de al menos 2 revisores antes de ser integrado y desplegado.


5. **Manejo del Ingress Local:** Dado que en el clúster local el recurso Ingress no recibe una dirección IP pública, Argo CD se configuró con `ignoreDifferences` para el Ingress. Esto evita que la aplicación quede en un estado de degradación progresiva o sincronización infinita esperando una IP que el proveedor local no entregará.

## Consecuencias

### Positivas

* **Seguridad mejorada:** El clúster extrae (pull) los cambios. No es necesario exponer credenciales de administración del clúster (Kubeconfig) al entorno de GitHub Actions.
* **Trazabilidad y Auditoría:** Git se convierte en la única fuente de verdad. Cualquier cambio en la infraestructura queda registrado en el historial de commits.
* **Desacoplamiento:** Separar el repositorio de la aplicación del repositorio GitOps evita que la ejecución del pipeline de CI (por cambios en el código) colisione con el pipeline de CD (cambios en infraestructura).

### Negativas / Riesgos (Trade-offs)

* **Gestión del `GITOPS_TOKEN`:** La automatización entre el repositorio de la aplicación y el repositorio GitOps depende de un Personal Access Token (PAT). Este token está atado a una cuenta de usuario específica y tiene un vencimiento fijo de 90 días, lo que introducirá una carga operativa recurrente (rotación manual del token) para evitar fallos en el pipeline.

## Alternativas Descartadas

* **Push-based CI (Ej: `kubectl apply` desde GitHub Actions):** Descartado porque requiere abrir el firewall del clúster hacia los runners de GitHub y exponer credenciales críticas de infraestructura en el servicio de CI, rompiendo el principio de menor privilegio. Además, no detecta *drift* (cambios manuales en el clúster que difieran de Git).
* **Flux CD:** Descartado. Aunque es una herramienta GitOps nativa muy capaz, carece de una interfaz de usuario integrada de serie tan completa como la de Argo CD, lo cual disminuye la observabilidad inmediata para los miembros del equipo que no tienen un perfil puramente DevOps.
