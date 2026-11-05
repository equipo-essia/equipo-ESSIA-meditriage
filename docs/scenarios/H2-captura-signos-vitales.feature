# language: es
Característica: H2 - Captura de signos vitales
Como enfermera de triage
  Quiero registrar los signos vitales del paciente
  Para tener los datos base que permitan evaluar su nivel de riesgo (ESI)

  Escenario: Registro exitoso de signos vitales completos
    Dado que el paciente "Juan" está registrado y en la sala de triage
    Cuando la enfermera ingresa los siguientes signos vitales:
      | heartRate                  | 80  |
      | bloodPressureSystolic      | 120 |
      | oxygenSaturationPercentage | 98  |
    Entonces el sistema debe asociar estos datos al paciente
    Y el paciente debe quedar listo para la evaluación automática de ESI