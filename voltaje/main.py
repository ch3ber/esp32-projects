import network, machine, uasyncio
from microdot import Microdot, Response

# ===================== Pines y hardware =====================
LED_PIN = 16  # LED controlado por botón y web
BUTTON_PIN = 15  # Pulsador a GND con pull-up interno

# Voltaje (entrada a través de divisor a máx 3.3V)
VOLT_ADC_PIN = 34  # ADC1_CH6 (recomendado: 32..39)
VOLT_DIVIDER_RATIO = 3.134  # Ajusta a TU divisor (ej. 100k/47k -> ~3.134)
VREF = 3.3  # Referencia práctica para ESP32

# Corriente con ACS712 (salida *escalada* al ADC con divisor)
ACS_ADC_PIN = 35  # ADC1_CH7
ACS_VOUT_DIVIDER_RATIO = 2.0  # 2.0 si usas divisor 1:1; 1.0 si sin divisor
ACS_MV_PER_A = 100.0  # Sensibilidad: 185 (5A), 100 (20A), 66 (30A)

# ===================== I/O y botón con IRQ ==================
led = machine.Pin(LED_PIN, machine.Pin.OUT)
button = machine.Pin(BUTTON_PIN, machine.Pin.IN, machine.Pin.PULL_UP)

try:
    import micropython

    def _toggle_led(_):
        led.value(not led.value())

    def _irq_handler(pin):
        micropython.schedule(_toggle_led, 0)

except ImportError:

    def _toggle_led(_):
        led.value(not led.value())

    def _irq_handler(pin):
        _toggle_led(None)


button.irq(trigger=machine.Pin.IRQ_FALLING, handler=_irq_handler)

# ===================== ADC helpers ==========================
adc_v = machine.ADC(machine.Pin(VOLT_ADC_PIN))
adc_i = machine.ADC(machine.Pin(ACS_ADC_PIN))
try:
    adc_v.atten(machine.ADC.ATTN_11DB)
    adc_i.atten(machine.ADC.ATTN_11DB)
except:
    pass  # algunos ports no requieren esta llamada


def _adc_volts(adc):
    raw = adc.read_u16()  # 0..65535 en ESP32
    if raw > 4095:
        raw >>= 4  # normaliza a ~12 bits
    return (raw / 4095.0) * VREF  # voltaje en pin ADC


# ===================== Estado de mediciones ==================
voltage_v = 0.0
current_a = 0.0
_acs_zero_vadc = None  # baseline (voltaje en pin ADC con 0 A)
_alpha = 0.3  # filtro simple exponencial para suavizar


# ===================== Tareas periódicas =====================
async def _calibrate_zero(samples=200, delay_ms=2):
    global _acs_zero_vadc
    s = 0.0
    for _ in range(samples):
        s += _adc_volts(adc_i)
        await uasyncio.sleep_ms(delay_ms)
    _acs_zero_vadc = s / samples


async def _measure_task():
    global voltage_v, current_a
    # calibración inicial del ACS712 (sin carga)
    if _acs_zero_vadc is None:
        await _calibrate_zero()

    while True:
        # Voltaje de entrada (escalado desde pin ADC por el divisor)
        try:
            v_pin = _adc_volts(adc_v)
            v_in = v_pin * VOLT_DIVIDER_RATIO
        except:
            v_in = voltage_v

        # Corriente (delta respecto a cero en pin ADC, revertir divisor y dividir entre sensibilidad)
        try:
            v_adc = _adc_volts(adc_i)
            dv_adc = v_adc - _acs_zero_vadc  # delta en el pin
            # la salida real del sensor = dv_adc * ACS_VOUT_DIVIDER_RATIO
            dv_sensor = dv_adc * ACS_VOUT_DIVIDER_RATIO
            i_now = dv_sensor / (ACS_MV_PER_A / 1000.0)  # A (mV/A -> V/A)
        except:
            i_now = current_a

        # Filtro simple para estabilizar
        voltage_v = _alpha * v_in + (1 - _alpha) * voltage_v
        current_a = _alpha * i_now + (1 - _alpha) * current_a

        await uasyncio.sleep_ms(200)


# ===================== Web (Microdot) =======================
app = Microdot()
Response.default_content_type = "text/html; charset=utf-8"


@app.route("/")
async def index(req):
    # Sirve /www/index.html (cópialo ahí)
    return Response(body=open("/www/index.html", "rb").read())


@app.route("/led")  # /led?state=on|off
async def led_ctrl(req):
    state = req.args.get("state", "off")
    led.value(1 if state == "on" else 0)
    return Response(status_code=204)


@app.route("/status")  # "on" | "off"
async def led_status(req):
    return Response(body="on" if led.value() else "off")


@app.route("/metrics")  # {"voltage": V, "current": A}
async def metrics(req):
    body = ('{"voltage": %.3f, "current": %.3f}' % (voltage_v, current_a)).encode()
    return Response(body=body, headers={"Content-Type": "application/json"})


@app.route("/calibrate", methods=["POST"])  # recalibra el cero del ACS712
async def calibrate(req):
    await _calibrate_zero()
    body = ('{"ok": true, "zero_vadc": %.4f}' % _acs_zero_vadc).encode()
    return Response(body=body, headers={"Content-Type": "application/json"})


async def main():
    uasyncio.create_task(_measure_task())
    ip = network.WLAN(network.AP_IF).ifconfig()[0]
    print("Servidor en  http://%s/" % ip)
    await app.start_server(host="0.0.0.0", port=80)


uasyncio.run(main())
