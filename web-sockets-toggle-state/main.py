import network, uasyncio as asyncio
from machine import Pin
from microdot import Microdot
from microdot.websocket import with_websocket

# ---------- Wi-Fi ----------
SSID = "wifi_ssid_to_connect"
PASS = "pass123123"


def wifi_connect():
    wlan = network.WLAN(network.STA_IF)
    if not wlan.isconnected():
        wlan.active(True)
        wlan.connect(SSID, PASS)
        while not wlan.isconnected():
            pass
    print("IP ESP32:", wlan.ifconfig()[0])


wifi_connect()

# ---------- LED integrado ----------
LED_PIN = 2  # La mayoría de DevKit V1 usa GPIO2 para el LED onboard:contentReference[oaicite:2]{index=2}
led = Pin(LED_PIN, Pin.OUT)

# ---------- Estado compartido ----------
state = {"on": False}
clients = set()

# ---------- Servidor ----------
app = Microdot()


@app.route("/")
async def index(req):
    html = f"""
    <!doctype html>
    <html><head><meta charset='utf-8'>
    <title>LED integrado</title></head>
    <body>
      <h1>LED: <span id='status'>{'ON' if state['on'] else 'OFF'}</span></h1>
      <button id='btn'>Cambiar</button>
      <script>
        const ws = new WebSocket('ws://' + location.host + '/ws');
        ws.onmessage = ev => document.getElementById('status').textContent = ev.data;
        document.getElementById('btn').onclick = () => ws.send('toggle');
      </script>
    </body></html>"""
    return html, 200, {"Content-Type": "text/html"}


@app.route("/ws")
@with_websocket
async def ws(req, sock):
    clients.add(sock)
    await sock.send("ON" if state["on"] else "OFF")  # estado inicial
    try:
        while True:
            msg = await sock.receive()
            if msg == "toggle":
                state["on"] = not state["on"]
                led.value(state["on"])  # actualiza LED físico
                # difunde a todas las pestañas
                for c in list(clients):
                    try:
                        await c.send("ON" if state["on"] else "OFF")
                    except:
                        clients.discard(c)
    finally:
        clients.discard(sock)


# ---------- Lanzar ----------
asyncio.run(app.start_server(host="0.0.0.0", port=80))
