# ADR 0001: Selección de la Iniciativa MediTriage para la Clasificación y Triaje Médico Inteligente

* **Fecha:** 19 de agosto de 2026
* **Autores:** Cristobal Araos, Martin Duran, Martin Garrido, Alonso Plane 
* **Estado:** Aceptado

## Título

ADR 0001: Elección de MediTriage como Solución de Triaje Asistido para Servicios de Urgencia

## Contexto

La red de centros de atención primaria necesita reducir tiempos de espera en urgencias. Se busca una plataforma que priorice pacientes en la sala de espera usando IA sobre síntomas reportados, historia clínica y signos vitales, respetando la normativa chilena de datos sensibles (Ley 19.628 y Ley 21.719).

## Decisión

Se decide adoptar la iniciativa **MediTriage** como la solución arquitectónica para el sistema de triaje médico asistido.

### Justificación de la Elección de MediTriage

1. **Alineación con la Escala ESI 1–5:**
   MediTriage incorpora reglas clínicas y modelos de soporte a la decisión entrenados específicamente bajo el marco del *Emergency Severity Index* (ESI v4). Esto asegura que la severidad de los síntomas, los signos vitales y los recursos estimados requeridos por el paciente se mapeen exactamente a los niveles estandarizados (desde ESI 1: *Resucitación/Peligro inminente de vida*, hasta ESI 5: *No urgente/Sin recursos requeridos*).

2. **Garantía de Latencia < 3 Segundos:**
   La arquitectura de MediTriage está diseñada sobre un patrón desacoplado y orientado a servicios de alta disponibilidad y baja latencia (empleando caching en memoria para constantes vitales, inferencia optimizada y pipelines asíncronos). Esto permite procesar la entrada de datos clínicos, evaluar las reglas de priorización e inferir el nivel ESI en un tiempo promedio estimado de < 1.5s, cumpliendo con creces el límite máximo permitido de 3s.

3. **Inferencia Explicable (Explicabilidad / Interpretabilidad):**
   A diferencia de modelos cerrados (*"black-box"*), MediTriage integra un motor de explicabilidad (basado en árboles de decisión explicables, reglas de inferencia clínica y modelos de atribución de características como SHAP/LIME). Cada resultado generado incluye un desglose sintético de las variables que ponderaron la decisión (ej. *"Asignado ESI 2 debido a Saturación O2 < 90% y alteración del estado mental"*), permitiendo al personal de enfermería entender, validar o corregir el resultado en segundos.

4. **Material de gran importancia para la ley 21.719:**
   Gran parte de este proyecto constará de trabajar con la nueva ley de protección de datos, una ley que implicará un importante cambio en los métodos de tratar los datos para nuestra carrera. Por esto, nos vemos con la necesidad de experimentar y conseguir experiencia con la aplicación de esta.

## Consecuencias

### Alternativas consideradas

| Alternativa | Por qué se descartó |
|---|---|
| Mantener el triaje manual sin apoyo de software | No ataca el problema: el objetivo es bajar la priorización de unos 25 min a menos de 3 min, y el proceso manual depende de la variabilidad de cada profesional. |
| Modelo de IA cerrado ("black-box") | No explica por qué asigna una categoría; la enfermera no podría validarla ni corregirla en segundos, y se complica la trazabilidad que exige la Ley 21.719. |

### Positivas
* **Estandarización y Precisión:** Reducción en la variabilidad del triaje al apegarse estrictamente al protocolo ESI (1-5).
* **Eficiencia Operativa:** Al garantizar tiempos de respuesta por debajo de los 3 segundos, no se genera fricción ni demoras adicionales en la ventanilla o box de admisión de urgencia.
* **Adopción Clínica y Transparencia:** La explicabilidad del sistema incrementa la confianza de médicos y enfermeros, facilitando la adopción del software y cumpliendo con requerimientos legales de trazabilidad en decisiones clínicas.
* **Arquitectura Escalable:** Permite la integración fluida con sistemas EHR/HIS existentes mediante APIs REST/gRPC ligeras.

### Negativas y Riesgos
* **Complejidad Técnica Incrementada:** Computar métricas de explicabilidad en tiempo real agrega overhead computacional, lo cual requiere una optimización rigurosa del pipeline para no violar el límite de latencia de 3s.
* **Mantenimiento y Calibración:** Requiere monitoreo continuo para evitar el *data drift* (desviación de patrones de admisión) y asegurar que las reglas y pesos del modelo se mantengan alineados con las guías clínicas vigentes.
