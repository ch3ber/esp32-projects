import network, machine, uasyncio
from microdot import Microdot, Response

# ====== Potenciómetro B10K ======
POT_ADC_PIN = 34  # ADC1_CH6 (recomendado 32..39)
VREF = 3.3  # referencia práctica
ALPHA = 0.25  # filtro (suavizado)
READ_MS = 50  # periodo de muestreo

adc_p = machine.ADC(machine.Pin(POT_ADC_PIN))
try:
    adc_p.atten(machine.ADC.ATTN_11DB)  # rango aprox 0-3.3V
except:
    pass


def _adc_volts(adc):
    raw = adc.read_u16()  # 0..65535 en ESP32 (MicroPython)
    if raw > 4095:
        raw >>= 4  # normaliza a ~12 bits
    volts = (raw / 4095.0) * VREF
    return raw, volts


# ====== Estado ======
pot_raw = 0
pot_volts = 0.0


async def _measure_task():
    global pot_raw, pot_volts

    while True:
        raw, v = _adc_volts(adc_p)

        # filtro exponencial simple (suaviza ruido)
        pot_raw = int(ALPHA * raw + (1 - ALPHA) * pot_raw)
        pot_volts = ALPHA * v + (1 - ALPHA) * pot_volts

        await uasyncio.sleep_ms(READ_MS)


# ====== Web (Microdot) ======
app = Microdot()
Response.default_content_type = "text/html; charset=utf-8"


@app.route("/")
async def index(req):
    return Response(body=open("/www/index.html", "rb").read())


@app.route("/metrics")
async def metrics(req):
    # JSON simple para el frontend
    body = ('{"raw": %d, "volts": %.3f}' % (pot_raw, pot_volts)).encode()
    return Response(body=body, headers={"Content-Type": "application/json"})


async def main():
    uasyncio.create_task(_measure_task())

    # En AP mode normalmente es 192.168.4.1
    ip = network.WLAN(network.AP_IF).ifconfig()[0]
    print("Servidor en  http://%s/" % ip)

    await app.start_server(host="0.0.0.0", port=80)


uasyncio.run(main())
