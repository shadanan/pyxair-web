from sanic import Sanic

from sanic.response import json
from sanic.websocket import WebSocketProtocol
from json import dumps
import logging
import pyxair


app = Sanic(name="XAir API Proxy")
xinfo = pyxair.auto_detect()
xairs = {xinfo.name: pyxair.XAir(xinfo)}


CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "*",
}


@app.get("/xair/<xair:string>/osc/<address:path>")
async def osc_get(req, xair, address):
    address = "/" + address
    message = await xairs[xair].get(address)
    return json({**message._asdict(), **{"xair": xair}}, headers=CORS_HEADERS)


@app.patch("/xair/<xair:string>/osc/<address:path>")
async def osc_patch(req, xair, address):
    xairs[xair].put(req.json["address"], req.json["arguments"])
    return json({**req.json, **{"xair": xair}}, headers=CORS_HEADERS)


@app.options("/xair/<xair:string>/osc/<address:path>")
async def osc_options(req, xair, address):
    address = "/" + address
    return json({"xair": xair, "address": address}, headers=CORS_HEADERS)


@app.websocket("/xair/<xair:string>/feed")
async def feed(req, ws, xair):
    with xairs[xair].subscribe() as queue:
        while True:
            message = await queue.get()
            await ws.send(dumps({**message._asdict(), **{"xair": xair}}))


if __name__ == "__main__":
    logging.basicConfig(
        format="[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s",
        level=logging.INFO,
    )
    for xair in xairs.values():
        app.add_task(xair.monitor())
    app.run(host="0.0.0.0", port=8000, protocol=WebSocketProtocol, auto_reload=True)
