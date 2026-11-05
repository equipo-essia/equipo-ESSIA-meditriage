# language: es
Característica: H1 - Registro de paciente con validación de RUT y consentimiento informado
  Como Paciente o Personal de Admisión
  Quiero registrar la identificación y consentimiento del paciente
  Para habilitar la atención de urgencia bajo la normativa legal chilena

  Escenario: Registro exitoso con RUT válido y aceptación de consentimiento (Camino Feliz)
    Dado que el paciente ingresa un RUT válido "12.345.678-5"
    Y marca la casilla de consentimiento informado para tratamiento de datos de salud
    Cuando presiona el botón "Registrar paciente"
    Entonces el sistema confirma el registro con éxito
    Y habilita el paso siguiente de captura de síntomas.

  Escenario: Paciente indocumentado o extranjero sin RUT chileno (Caso Borde)
    Dado que el paciente no posee RUN chileno
    Cuando selecciona la opción "Ingreso sin RUT / Pasaporte provisional" e ingresa el identificador provisorio
    Y acepta el consentimiento informado de emergencia
    Entonces el sistema genera un identificador temporal único
    Y permite continuar el flujo de triage.

  Escenario: Rechazo de registro por formato de RUT inválido (Caso de Error)
    Dado que el usuario ingresa un RUT con dígito verificador erróneo "12.345.678-9"
    Cuando intenta enviar el formulario de registro
    Entonces el sistema bloquea el avance
    Y muestra un mensaje de error: "RUT inválido. Verifique el dígito verificador".