import logging
import pyxair

from sanic import Sanic
from sanic.exceptions import NotFound
from sanic.response import json
from sanic.websocket import WebSocketProtocol
from json import dumps

app = Sanic(name="XAir API Proxy")
xairs = pyxair.XAirScanner(connect=True)


def get_xair(name):
    xinfos = {xinfo for xinfo in xairs.list() if xinfo.name == name}
    if len(xinfos) == 0:
        raise NotFound(f"Requested XAir {name} not found")
    return xairs.get(xinfos.pop())


@app.get("/xair")
async def xair(req):
    return json({"xair": [x.name for x in xairs.list()]})


@app.get("/xair/<name:string>/osc/<address:path>")
async def osc_get(req, name, address):
    address = "/" + address
    xair = get_xair(name)
    message = await xair.get(address)
    return json({**message._asdict(), **{"xair": name}})


@app.patch("/xair/<name:string>/osc/<address:path>")
async def osc_patch(req, name, address):
    xair = get_xair(name)
    xair.put(req.json["address"], req.json["arguments"])
    return json({**req.json, **{"xair": name}})


@app.websocket("/xair/<name:string>/feed")
async def feed(req, ws, name):
    xair = get_xair(name)
    with xair.subscribe() as queue:
        while True:
            message = await queue.get()
            await ws.send(dumps({**message._asdict(), **{"xair": name}}))


if __name__ == "__main__":
    logger = logging.getLogger("pyxair")
    logger.setLevel(logging.INFO)
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    formatter = logging.Formatter(
        "%(asctime)s [%(name)s] [%(levelname)s] %(message)s", "[%Y-%m-%d %H:%M:%S %z]"
    )
    ch.setFormatter(formatter)
    logger.addHandler(ch)

    app.add_task(xairs.start())
    app.run(
        host="0.0.0.0",
        port=8000,
        protocol=WebSocketProtocol,
        debug=True,
        auto_reload=True,
    )
