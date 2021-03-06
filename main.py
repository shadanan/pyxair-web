#!/usr/bin/env python3
import asyncio
import logging
from json import dumps

import pyxair
from sanic import Sanic
from sanic.exceptions import NotFound
from sanic.response import json
from sanic.websocket import WebSocketProtocol

logger = logging.getLogger("pyxair.web")
app = Sanic(name="XAir API Proxy")


class XAirMonitor:
    def __init__(self):
        self._xinfos = {}
        self._scanner = pyxair.XAirScanner(connect=True, meters=[2, 3, 5])

    async def start(self):
        scanner_task = asyncio.create_task(self._scanner.start())
        with self._scanner.subscribe() as queue:
            try:
                while True:
                    self._xinfos = {xinfo.name: xinfo for xinfo in await queue.get()}
            except asyncio.CancelledError:
                await scanner_task

    def get(self, name):
        if name not in self._xinfos:
            raise NotFound(f"Requested XAir {name} not found")
        return self._scanner.get(self._xinfos[name])

    def list(self):
        return list(self._xinfos.keys())


xmon = XAirMonitor()


@app.get("/api/xairs")
async def xairs_get(req):
    return json({"xairs": xmon.list()})


@app.websocket("/ws/xairs")
async def xairs_ws(req, ws):
    try:
        logger.info("Subscribed: %s", req.socket)
        with xmon._scanner.subscribe() as queue:
            await ws.send(dumps({"xairs": xmon.list()}))
            while ws.open:
                xinfos = await queue.get()
                await ws.send(dumps({"xairs": [xinfo.name for xinfo in xinfos]}))
    finally:
        logger.info("Unsubscribed: %s", req.socket)


@app.get("/api/xairs/<name:string>/addresses/<address:path>")
async def osc_get(req, name, address):
    address = "/" + address
    xair = xmon.get(name)
    try:
        message = await xair.get(address)
    except asyncio.TimeoutError:
        raise NotFound(f"Requested address {address} on {name} not found")
    return json({**message._asdict(), **{"xair": name}})


@app.patch("/api/xairs/<name:string>/addresses/<address:path>")
async def osc_patch(req, name, address):
    xair = xmon.get(name)
    xair.put(req.json["address"], req.json["arguments"])
    return json({**req.json, **{"xair": name}})


@app.websocket("/ws/xairs/<name:string>/addresses")
async def osc_ws(req, ws, name):
    xair = xmon.get(name)
    try:
        logger.info("Subscribed %s: %s", name, req.socket)
        with xair.subscribe() as queue:
            while ws.open:
                message = await queue.get()
                await ws.send(dumps({**message._asdict(), **{"xair": name}}))
    finally:
        logger.info("Unsubscribed %s: %s", name, req.socket)


app.static("", "./static/index.html")
app.static("", "./static")


if __name__ == "__main__":
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    formatter = logging.Formatter(
        "%(asctime)s [%(name)s] [%(levelname)s] %(message)s", "[%Y-%m-%d %H:%M:%S %z]"
    )
    ch.setFormatter(formatter)

    pyxair_logger = logging.getLogger("pyxair")
    pyxair_logger.setLevel(logging.DEBUG)
    pyxair_logger.addHandler(ch)

    app.add_task(xmon.start())
    app.run(host="::", port=8000, protocol=WebSocketProtocol, auto_reload=True)
