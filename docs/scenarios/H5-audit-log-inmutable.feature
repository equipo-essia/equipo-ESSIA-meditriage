# language: es
Característica: H5 - Audit log inmutable y enmascaramiento de PII
  Como Auditor Clínico y Oficial de Seguridad
  Quiero que cada recomendación de la IA quede registrada de forma inmutable con PII enmascarada
  Para garantizar la trazabilidad por 5 años y cumplir las Leyes 19.628 y 21.719

  Escenario: Registro exitoso de evento de IA con anonimización de identidad (Camino Feliz)
    Dado que el motor de IA emite una recomendación de nivel ESI para el paciente con RUT "12.345.678-5"
    Cuando se genera el log de auditoría
    Entonces el registro almacena los signos vitales, la categoría ESI, la justificación y marca de tiempo
    Y enmascara la PII registrando el RUT como "12.345.***-*".

  Escenario: Consulta de registros históricos de auditoría de hace 5 años (Caso Borde)
    Dado que un auditor solicita la trazabilidad de una decisión de triage realizada hace 5 años
    Cuando consulta el log inmutable por el identificador del caso
    Entonces el sistema retorna el registro íntegro con su firma criptográfica sin alteraciones.

  Escenario: Intento no autorizado de modificación o borrado de log (Caso de Error)
    Dado un usuario o proceso que intenta alterar o eliminar un registro de log de triage
    Cuando envía la solicitud a la base de datos de auditoría
    Entonces la base de datos rechaza la operación por política de inmutabilidad (append-only)
    Y genera una alerta de seguridad por intento de violación de auditoría.