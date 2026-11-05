# language: es
Característica: H4 - Tablero dinámico de priorización para personal médico
  Como Médico Jefe de Turno o Enfermera de Urgencias
  Quiero visualizar la lista de espera ordenada dinámicamente según nivel ESI
  Para gestionar eficientemente los boxes de atención y tiempos de espera

  Escenario: Ordenamiento dinámico en tiempo real ante nuevo paciente de alta urgencia (Camino Feliz)
    Dado que el tablero muestra 4 pacientes en nivel ESI 3 y ESI 4
    Cuando ingresa un nuevo paciente evaluado como "ESI 1 (Reanimación)"
    Entonces el tablero se actualiza de forma inmediata posicionándolo en el primer lugar de atención
    Y emite una alerta audiovisual en la sala de urgencias.

  Escenario: Coexistencia de múltiples pacientes con el mismo nivel de gravedad (Caso Borde)
    Dado que existen dos pacientes con el mismo nivel "ESI 2"
    Cuando se visualiza la lista en el tablero
    Entonces el sistema desempata y prioriza al paciente con mayor tiempo acumulado en sala de espera.

  Escenario: Falla temporal de conexión en el visor del tablero (Caso de Error)
    Dado que el navegador del tablero pierde la conexión con el servidor
    Cuando intenta refrescar el estado de los pacientes
    Entonces el sistema muestra un banner de advertencia "Sin conexión en tiempo real: mostrando últimos datos en caché"
    Y reintenta la reconexión automática periódicamente.