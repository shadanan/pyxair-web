from sanic import Sanic

from sanic import response
from sanic.websocket import WebSocketProtocol
import json
import logging
import pyxair


app = Sanic(name="XAir API Proxy")
xair = pyxair.XAir(pyxair.auto_detect())


def make_response(message: pyxair.OscMessage):
    return response.json(
        {
            "data": {
                "id": message.address,
                "type": "osc",
                "attributes": {"arguments": message.arguments},
            }
        }
    )


@app.get("/osc/<address:path>")
async def osc_get(req, address):
    address = "/" + address
    message: pyxair.OscMessage = await xair.get(address)
    return response.json(
        message._asdict(),
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "*",
        },
    )


@app.patch("/osc/<address:path>")
async def osc_patch(req, address):
    await xair.put(req.json["address"], req.json["arguments"])
    return response.json(
        req.json,
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "*",
        },
    )


@app.options("/osc/<address:path>")
async def osc_options(req, address):
    address = "/" + address
    return response.json(
        {"address": address},
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "*",
        },
    )


@app.websocket("/feed")
async def feed(req, ws):
    with xair.subscribe() as queue:
        while True:
            message: pyxair.OscMessage = await queue.get()
            await ws.send(json.dumps(message._asdict()))


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    app.add_task(xair.monitor())
    app.run(host="0.0.0.0", port=8000, protocol=WebSocketProtocol, auto_reload=True)
