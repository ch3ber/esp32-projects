import network, machine, uasyncio
from microdot import Microdot, Response

# physical LED controlled by a push-button
LED_PIN = 16                   # LED conectado al pin 16
BUTTON_PIN = 15                # Pulsador en el pin 15

led = machine.Pin(LED_PIN, machine.Pin.OUT)

# Configura el pulsador con resistencia de pull-up interna.  El pulsador debe
# conectar el pin a GND cuando se presione.
button = machine.Pin(BUTTON_PIN, machine.Pin.IN, machine.Pin.PULL_UP)

try:
    import micropython

    # Utilizamos micropython.schedule para que la parte pesada se ejecute fuera
    # de la interrupción, evitando problemas de tiempo en la ISR.

    def _toggle_led(_):
        led.value(not led.value())

    def _irq_handler(pin):  # noqa: ARG001 – firma impuesta por IRQ
        micropython.schedule(_toggle_led, 0)

except ImportError:
    # Cuando el módulo micropython no existe (p. ej. en CPython durante pruebas),
    # ejecutamos el manejador directamente.
    def _toggle_led(_):
        led.value(not led.value())

    def _irq_handler(pin):  # noqa: ARG001
        _toggle_led(None)

# Registra la interrupción por flanco de bajada (pulsador presionado)
button.irq(trigger=machine.Pin.IRQ_FALLING, handler=_irq_handler)

# --- App -----------------------------------------------------
app = Microdot()
Response.default_content_type = 'text/html; charset=utf-8'

@app.route('/')                 # Página principal
async def index(req):
    return Response(body=open('/www/index.html', 'rb').read())

@app.route('/led')              # /led?state=on|off
async def led_ctrl(req):
    state = req.args.get('state', 'off')
    led.value(1 if state == 'on' else 0)
    return Response(status_code=204)   # 204 = sin contenido

# Devuelve una cadena "on" o "off" con el estado actual.
# Esto permite a la página web consultar
# periódicamente el estado del LED y actualizar la interfaz sin necesidad de
# recargarla.

@app.route('/status')            # Devuelve "on" | "off"
async def led_status(req):
    return Response(body='on' if led.value() else 'off')

async def main():
    ip = network.WLAN(network.AP_IF).ifconfig()[0]
    print('Servidor en  http://%s/' % ip)
    await app.start_server(host='0.0.0.0', port=80)

uasyncio.run(main())
