# ruleid: fastapi-endpoint-missing-auth
@app.get("/clientes")
def listar():
    ...

# ok: fastapi-endpoint-missing-auth
@app.get("/clientes")
def listar_ok(user=Depends(require_auth)):
    ...

# ok: fastapi-endpoint-missing-auth
@app.post("/clientes", dependencies=[Depends(require_auth)])
async def crear():
    ...
