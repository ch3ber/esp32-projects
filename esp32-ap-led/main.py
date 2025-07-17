import network, machine, uasyncio
from microdot import Microdot, Response

# --- GPIO ----------------------------------------------------
LED_PIN = 2                     # Cambia si usas otro pin
led = machine.Pin(LED_PIN, machine.Pin.OUT)

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

async def main():
    ip = network.WLAN(network.AP_IF).ifconfig()[0]
    print('Servidor en  http://%s/' % ip)
    await app.start_server(host='0.0.0.0', port=80)

uasyncio.run(main())
