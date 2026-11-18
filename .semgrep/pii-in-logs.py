# ruleid: pii-in-logs
log.info("cliente %s", user.rut)
# ruleid: pii-in-logs
log.warning(f"Alta de {user.fullName}")
# ok: pii-in-logs
log.info("cliente %s", mask_rut(user.rut))
# ok: pii-in-logs
log.info("operación completada")
