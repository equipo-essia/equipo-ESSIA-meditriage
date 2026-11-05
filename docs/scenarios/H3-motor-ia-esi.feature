# language: es
Característica: H3 - Sugerencia de categoría ESI y explicabilidad por motor IA
  Como Personal Clínico de Triage
  Quiero que la IA clasifique al paciente en la escala ESI (1-5) con su debida justificación
  Para agilizar la toma de decisiones clínicas con una latencia menor a 3 segundos

  Escenario: Clasificación ESI exitosa con justificación clínica en tiempo estándar (Camino Feliz)
    Dado que el sistema recibe los signos vitales y síntomas de un paciente con dolor torácico opresivo
    Cuando el motor de IA procesa la solicitud
    Entonces el sistema retorna la categoría "ESI 2" en un tiempo menor a 3 segundos
    Y muestra la justificación clínica: "Riesgo de síndrome coronario agudo por dolor torácico opresivo y diaforesis".

  Escenario: Paciente con parámetros en frontera entre dos niveles ESI (Caso Borde)
    Dado que un paciente presenta signos ambiguos entre nivel ESI 2 y ESI 3
    Cuando el motor de IA realiza la inferencia
    Entonces asigna el nivel más conservador y seguro "ESI 2"
    Y explicita en la justificación los factores de riesgo determinantes.

  Escenario: Caída o timeout del motor de IA con fallback a triage manual (Caso de Error)
    Dado que el servicio del motor de IA experimenta una latencia superior a 3 segundos o pérdida de conexión
    Cuando el formulario de triage es enviado
    Entonces el sistema activa automáticamente el modo "Fallback Manual"
    Y notifica a la enfermera para categorizar manualmente sin detener el flujo de atención.