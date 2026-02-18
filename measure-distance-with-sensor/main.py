import network
import machine
import utime
import uasyncio
from microdot import Microdot, Response

# ====== HC-SR04 ======
TRIG_PIN = 5
ECHO_PIN = 18
SAMPLE_MS = 300
ECHO_TIMEOUT_US = 30000  # ~5m max
ALPHA = 0.3  # filtro exponencial

trig = machine.Pin(TRIG_PIN, machine.Pin.OUT)
echo = machine.Pin(ECHO_PIN, machine.Pin.IN)
trig.value(0)


def read_distance_cm():
    # Pulso de disparo: 10us en TRIG
    trig.value(0)
    utime.sleep_us(2)
    trig.value(1)
    utime.sleep_us(10)
    trig.value(0)

    pulse_us = machine.time_pulse_us(echo, 1, ECHO_TIMEOUT_US)
    if pulse_us < 0:
        return None

    # Distancia (cm) = tiempo_us * velocidad_sonido_cm/us / 2
    return (pulse_us * 0.0343) / 2.0


# ====== Estado ======
distance_cm = 0.0
distance_ok = False
last_error = "sin lectura"


async def measure_task():
    global distance_cm, distance_ok, last_error

    while True:
        try:
            d = read_distance_cm()
            if d is None:
                distance_ok = False
                last_error = "timeout"
            else:
                if distance_ok:
                    distance_cm = (ALPHA * d) + ((1.0 - ALPHA) * distance_cm)
                else:
                    distance_cm = d
                distance_ok = True
                last_error = ""
        except Exception as exc:
            distance_ok = False
            last_error = str(exc)

        await uasyncio.sleep_ms(SAMPLE_MS)


# ====== Web (Microdot) ======
app = Microdot()
Response.default_content_type = "text/html; charset=utf-8"


@app.route("/")
async def index(req):
    return Response(body=open("/www/index.html", "rb").read())


@app.route("/metrics")
async def metrics(req):
    body = (
        '{"distance_cm": %.2f, "ok": %s, "error": "%s", "sample_ms": %d}'
        % (
            distance_cm,
            "true" if distance_ok else "false",
            last_error.replace('"', "'"),
            SAMPLE_MS,
        )
    ).encode()
    return Response(body=body, headers={"Content-Type": "application/json"})


async def main():
    uasyncio.create_task(measure_task())

    ip = network.WLAN(network.AP_IF).ifconfig()[0]
    print("Servidor en http://%s/" % ip)
    print("HC-SR04 TRIG=%d ECHO=%d" % (TRIG_PIN, ECHO_PIN))

    await app.start_server(host="0.0.0.0", port=80)


uasyncio.run(main())
