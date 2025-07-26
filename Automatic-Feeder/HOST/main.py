import network
import espnow
import machine
import socket
import json
import utime
from machine import Pin, PWM

# Configuración DRV8825
STEP_PIN = Pin(12, Pin.OUT)    # GPIO12 → STEP
DIR_PIN = Pin(13, Pin.OUT)     # GPIO13 → DIR
ENABLE_PIN = Pin(14, Pin.OUT, value=1)  # GPIO14 → ENABLE (activo bajo)
MODE_PINS = [Pin(15, Pin.OUT), Pin(16, Pin.OUT), Pin(17, Pin.OUT)]  # M0,M1,M2

# Configuración de micropasos (selecciona uno)
MICROSTEPS = {
    'Full': (0, 0, 0),
    '1/2': (1, 0, 0),
    '1/4': (0, 1, 0),
    '1/8': (1, 1, 0),
    '1/16': (0, 0, 1),
    '1/32': (1, 0, 1)
}

# Configurar micropasos (ej. 1/16)
for pin, val in zip(MODE_PINS, MICROSTEPS['1/16']):
    pin.value(val)

# Variables de control
current_rpm = 10
steps_per_rev = 200 * 16  # 200 pasos * micropasos 1/16
pwm = PWM(STEP_PIN, freq=100, duty=512)
pwm.deinit()

# Configuración WiFi y ESP-NOW
ap = network.WLAN(network.AP_IF)
ap.active(True)
ap.config(essid='Motor-Control', password='123456789')

esp = espnow.ESPNow()
esp.active(True)
peer = b'\xec\xe3\x34\xdb\xb0\xa8'  # MAC del cliente
esp.add_peer(peer)

def set_rpm(rpm):
    """Configura la velocidad en RPM"""
    global current_rpm
    current_rpm = rpm
    delay_us = int(60000000 / (steps_per_rev * rpm))
    pwm.init(freq=1000000//delay_us, duty=512)
    print(f"Velocidad: {rpm} RPM")

def move_steps(steps, direction):
    """Mueve N pasos en dirección especificada"""
    DIR_PIN.value(direction)
    ENABLE_PIN.value(0)  # Habilita el driver
    print(f"Moviendo {abs(steps)} pasos {'CW' if direction else 'CCW'}")
    
    # Para movimiento continuo, usamos PWM
    if steps == 0:  # Movimiento continuo
        return
    
    # Para pasos exactos
    for _ in range(abs(steps)):
        STEP_PIN.value(1)
        utime.sleep_us(2)
        STEP_PIN.value(0)
        utime.sleep_us(2)
    
    ENABLE_PIN.value(1)  # Deshabilita el driver

def control_pump(state):
    """Controla la bomba remota"""
    cmd = b'pumpOn' if state else b'pumpOff'
    try:
        if esp.send(peer, cmd):
            print(f"Comando bomba: {'ON' if state else 'OFF'}")
            return True
    except Exception as e:
        print("Error ESP-NOW:", e)
    return False

# HTML Interface
HTML = """<!DOCTYPE html>
<html>
<head>
    <title>Control de Motores</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        /* Estilos optimizados */
        .control-panel {background: #f0f0f0; border-radius: 10px; padding: 15px; margin: 10px 0;}
        .motor-control {display: flex; flex-wrap: wrap; gap: 10px; align-items: center;}
        button {padding: 10px 15px; background: #4285f4; color: white; border: none; border-radius: 5px;}
        #status {margin-top: 15px; padding: 10px; background: #e8f5e9; border-radius: 5px;}
    </style>
</head>
<body>
    <div class="control-panel">
        <h2>Control NEMA17 (DRV8825)</h2>
        <div class="motor-control">
            <input type="number" id="rpm" min="1" max="150" value="10" placeholder="RPM">
            <input type="number" id="steps" min="0" max="5000" value="200" placeholder="Pasos (0=continuo)">
            <select id="direction">
                <option value="1">Horario</option>
                <option value="0">Antihorario</option>
            </select>
            <button onclick="moveMotor()">Mover</button>
            <button onclick="stopMotor()">Detener</button>
        </div>
    </div>

    <div class="control-panel">
        <h2>Control Bomba de Agua</h2>
        <button onclick="controlPump(true)">Encender</button>
        <button onclick="controlPump(false)">Apagar</button>
    </div>

    <div id="status">Listo</div>

    <script>
        async function sendCommand(cmd) {
            const status = document.getElementById('status');
            try {
                const response = await fetch('/control', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({command: cmd})
                });
                const result = await response.json();
                status.textContent = result.message || 'Comando ejecutado';
            } catch (e) {
                status.textContent = 'Error: ' + e.message;
            }
        }

        function moveMotor() {
            const rpm = document.getElementById('rpm').value;
            const steps = document.getElementById('steps').value;
            const dir = document.getElementById('direction').value;
            sendCommand(`motor:${rpm}:${steps}:${dir}`);
        }

        function stopMotor() {
            sendCommand('motorStop');
        }

        function controlPump(state) {
            sendCommand(state ? 'pumpOn' : 'pumpOff');
        }
    </script>
</body>
</html>"""

# Servidor web
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.bind(('0.0.0.0', 80))
s.listen(1)
print('Servidor iniciado en', ap.ifconfig()[0])

while True:
    conn, addr = s.accept()
    request = conn.recv(2048)
    
    try:
        if b'POST /control' in request:
            headers, body = request.split(b'\r\n\r\n', 1)
            data = json.loads(body.decode())
            cmd = data['command']
            
            if cmd.startswith('motor:'):
                _, rpm, steps, dir = cmd.split(':')
                set_rpm(int(rpm))
                move_steps(int(steps), int(dir))
                response = {'message': f'Motor moviendo {steps} pasos a {rpm} RPM'}
            elif cmd == 'motorStop':
                pwm.deinit()
                ENABLE_PIN.value(1)
                response = {'message': 'Motor detenido'}
            elif cmd == 'pumpOn':
                control_pump(True)
                response = {'message': 'Bomba encendida'}
            elif cmd == 'pumpOff':
                control_pump(False)
                response = {'message': 'Bomba apagada'}
            else:
                response = {'message': 'Comando no válido'}
            
            conn.send(b'HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n\r\n')
            conn.send(json.dumps(response))
        else:
            conn.send(b'HTTP/1.1 200 OK\r\nContent-Type: text/html\r\n\r\n')
            conn.send(HTML)
    except Exception as e:
        print('Error:', e)
    finally:
        conn.close()