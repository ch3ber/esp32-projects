import network
import espnow
import machine
import socket
import json
import utime
import _thread
from machine import Pin, PWM
import urequests

# Configuración DRV8825 (Motor NEMA17)
STEP_PIN = Pin(12, Pin.OUT)    # GPIO12 → STEP
DIR_PIN = Pin(13, Pin.OUT)     # GPIO13 → DIR
ENABLE_PIN = Pin(14, Pin.OUT, value=1)  # GPIO14 → ENABLE (activo bajo)

# Configuración WiFi - Dual Mode Setup
ap = network.WLAN(network.AP_IF)
ap.active(True)
ap.config(essid='Motor-Control', password='123456789')

sta = network.WLAN(network.STA_IF)
sta.active(True)
sta.disconnect()  # Important for ESP-NOW stability

# ESP32-CAM configuration
ESP32_CAM_IP = "192.168.1.100"
ESP32_CAM_ENDPOINT = "/160x120.jpg"
#WIFI_SSID = "INFINITUM0CF6"
#WIFI_PASSWORD = "UYcnS7cCEU"

WIFI_SSID = "Jaguares Free Time"
WIFI_PASSWORD = "Tim3ToFun!"


# Configuración ESP-NOW
esp = espnow.ESPNow()
esp.active(True)
motor_peer = b'\xec\xe3\x34\xdb\xb0\xa8'  # MAC del receiver (bomba)
esp.add_peer(motor_peer)

# Variables para control de música
is_playing = False
stop_requested = False
tempo = 180  # pulsos por minuto

# Definición de notas musicales (RPM para cada nota)
NOTE_RPM = {
    'C4': 630, 'D4': 660, 'E4': 700, 'F4': 740, 'G4': 784, 'A4': 830, 'B4': 880,
    'C5': 930, 'D5': 990, 'E5': 1050, 'F5': 1110, 'G5': 1175, 'A5': 1250, 'B5': 1320,
    'C6': 1400, 'D6': 1480, 'E6': 1570, 'F6': 1660, 'G6': 1760, 'A6': 1860, 'B6': 1970,
    'R': 0  # Silencio (Rest)
}

# Melodías
MELODIES = {
    'mozart': [
        ('E5', 8), ('D5', 8), ('C5', 8), ('D5', 8), ('E5', 8), ('E5', 8), ('E5', 4),
        ('D5', 8), ('D5', 8), ('D5', 4), ('E5', 8), ('G5', 8), ('G5', 4),
        ('E5', 8), ('D5', 8), ('C5', 8), ('D5', 8), ('E5', 8), ('E5', 8), ('E5', 8), ('E5', 8),
        ('D5', 8), ('D5', 8), ('E5', 8), ('D5', 8), ('C5', 2)
    ],
    'beethoven': [
        ('E5', 8), ('E5', 8), ('F5', 8), ('G5', 8), ('G5', 8), ('F5', 8), ('E5', 8), ('D5', 8),
        ('C5', 8), ('C5', 8), ('D5', 8), ('E5', 4), ('E5', 8), ('D5', 8), ('D5', 2),
        ('E5', 8), ('E5', 8), ('F5', 8), ('G5', 8), ('G5', 8), ('F5', 8), ('E5', 8), ('D5', 8),
        ('C5', 8), ('C5', 8), ('D5', 8), ('E5', 4), ('D5', 8), ('C5', 8), ('C5', 2)
    ]
}

def connect_to_wifi():
    """Connect to WiFi temporarily for camera access"""
    if not sta.isconnected():
        print("Connecting to WiFi...")
        sta.active(True)
        sta.connect(WIFI_SSID, WIFI_PASSWORD)
        for _ in range(10):  # Wait up to 10 seconds
            if sta.isconnected():
                print("WiFi Connected:", sta.ifconfig())
                return True
            utime.sleep(1)
        print("WiFi Connection Failed")
        return False
    return True

def disconnect_wifi():
    """Disconnect WiFi to maintain ESP-NOW stability"""
    sta.disconnect()
    sta.active(False)
    print("WiFi Disconnected")

def get_esp32cam_image():
    """Retrieve image from ESP32-CAM with temporary WiFi connection"""
    if not connect_to_wifi():
        return None
    
    try:
        url = "http://{}{}".format(ESP32_CAM_IP, ESP32_CAM_ENDPOINT)
        print("Fetching image from:", url)
        response = urequests.get(url)
        image_data = response.content if response.status_code == 200 else None
        response.close()
        return image_data
    except Exception as e:
        print("Error getting image:", e)
        return None
    finally:
        disconnect_wifi()

# Control del motor paso a paso
def move_motor(steps, speed_rpm, direction):
    DIR_PIN.value(direction)
    ENABLE_PIN.value(0)
    
    delay = int(60000000 / (200 * speed_rpm))  # 200 pasos/rev
    for _ in range(abs(steps)):
        STEP_PIN.value(1)
        utime.sleep_us(delay)
        STEP_PIN.value(0)
        utime.sleep_us(delay)
    
    ENABLE_PIN.value(1)

# Control remoto de la bomba
def control_bomba(state):
    cmd = b'bombaOn' if state else b'bombaOff'
    try:
        if esp.send(motor_peer, cmd):
            print(f"Bomba {'ON' if state else 'OFF'} enviado")
            return True
        return False
    except Exception as e:
        print("Error ESP-NOW:", e)
        return False

# Funciones para reproducción musical
def music_player_thread(melody_name):
    """Hilo para reproducir música sin bloquear el servidor"""
    global is_playing, stop_requested
    
    if melody_name not in MELODIES:
        print("Melodía no encontrada")
        return
    
    is_playing = True
    stop_requested = False
    melody = MELODIES[melody_name]
    print(f"Reproduciendo: {melody_name}")
    
    for note, duration in melody:
        if stop_requested:
            break
        
        rpm = NOTE_RPM.get(note, 0)
        note_duration = int(60000 / tempo / duration)
        
        if rpm > 0:
            move_motor(2000, rpm, 1)  # 2000 pasos producen buen sonido
        else:
            ENABLE_PIN.value(1)  # Silencio
        
        start_time = utime.ticks_ms()
        while utime.ticks_diff(utime.ticks_ms(), start_time) < note_duration:
            if stop_requested:
                break
            utime.sleep_ms(10)
    
    ENABLE_PIN.value(1)
    is_playing = False
    print("Reproducción terminada")

def play_music(melody_name):
    """Inicia la reproducción de música en un hilo separado"""
    global is_playing
    if is_playing:
        stop_music()
        utime.sleep(0.5)  # Pequeña pausa antes de empezar nueva melodía
    
    try:
        _thread.start_new_thread(music_player_thread, (melody_name,))
    except:
        print("Error al iniciar hilo de música")

def stop_music():
    """Detiene la reproducción de música"""
    global stop_requested
    if is_playing:
        stop_requested = True
        print("Solicitando detener música...")
        # Espera hasta que la música realmente se detenga
        while is_playing:
            utime.sleep_ms(10)
        print("Música detenida")

# HTML Interface with Camera Controls
HTML = """<!DOCTYPE html>
<html>
<head>
    <title>Control de Motores y Cámara</title>
    <style>
        .control-panel { margin: 20px; padding: 15px; background: #f0f0f0; border-radius: 8px; }
        button { padding: 10px 15px; margin: 5px; border: none; border-radius: 4px; background: #4CAF50; color: white; }
        button:active { background: #45a049; }
        .music-control { margin-top: 15px; }
        .camera-control { margin-top: 15px; }
        #cameraImage { max-width: 320px; max-height: 240px; margin-top: 10px; border: 1px solid #ddd; }
        input[type="number"] { padding: 8px; margin: 5px; }
        #status { margin: 15px; padding: 10px; background: #e7f3fe; border-left: 6px solid #2196F3; }
    </style>
</head>
<body>
    <div class="control-panel">
        <h2>Motor Paso a Paso</h2>
        <input type="number" id="motor_steps" min="1" value="200" placeholder="Pasos">
        <input type="number" id="motor_speed" min="1" max="100" value="10" placeholder="RPM">
        <button onclick="controlMotor(true)">Mover</button>
        <button onclick="stopMotor()">Detener</button>
    </div>

    <div class="control-panel">
        <h2>Bomba de Agua</h2>
        <button onclick="controlBomba(true)">Encender Bomba</button>
        <button onclick="controlBomba(false)">Apagar Bomba</button>
    </div>

    <div class="control-panel music-control">
        <h2>Reproducción Musical</h2>
        <button onclick="playMusic('mozart')">Mozart</button>
        <button onclick="playMusic('beethoven')">Beethoven</button>
        <button onclick="stopMusic()">Detener Música</button>
    </div>

    <div class="control-panel camera-control">
        <h2>Cámara ESP32</h2>
        <button onclick="getCameraImage()">Actualizar Imagen</button>
        <div>
            <img id="cameraImage" src="" alt="Imagen de la cámara">
        </div>
    </div>

    <div id="status">Esperando comandos...</div>

    <script>
        async function sendCommand(cmd) {
            const status = document.getElementById('status');
            status.textContent = "Enviando...";
            
            try {
                const response = await fetch('/control', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({command: cmd})
                });
                const result = await response.json();
                status.textContent = result.message;
            } catch(e) {
                status.textContent = "Error: " + e.message;
            }
        }

        async function getCameraImage() {
            const status = document.getElementById('status');
            const imgElement = document.getElementById('cameraImage');
            
            status.textContent = "Obteniendo imagen de la cámara...";
            try {
                const response = await fetch('/get_image');
                if (response.ok) {
                    const blob = await response.blob();
                    imgElement.src = URL.createObjectURL(blob);
                    status.textContent = "Imagen actualizada: " + new Date().toLocaleTimeString();
                } else {
                    status.textContent = "Error al obtener imagen";
                }
            } catch(e) {
                status.textContent = "Error: " + e.message;
            }
        }

        function controlMotor() {
            const steps = document.getElementById('motor_steps').value;
            const speed = document.getElementById('motor_speed').value;
            sendCommand(`motor:${steps}:${speed}:1`);
        }

        function stopMotor() {
            sendCommand('motorStop');
        }

        function controlBomba(state) {
            sendCommand(state ? 'bombaOn' : 'bombaOff');
        }

        function playMusic(composer) {
            sendCommand(`playMusic:${composer}`);
        }

        function stopMusic() {
            sendCommand('stopMusic');
        }
        
        // Auto-refresh image every 5 seconds
        setInterval(getCameraImage, 5000);
        // Get first image on page load
        window.onload = getCameraImage;
    </script>
</body>
</html>"""

# Servidor Web
s = socket.socket()
s.bind(('0.0.0.0', 80))
s.listen(5)

print("Server started. AP IP:", ap.ifconfig()[0])

while True:
    conn, addr = s.accept()
    request = conn.recv(2048)
    
    if b'POST /control' in request:
        try:
            data = json.loads(request.split(b'\r\n\r\n')[1])
            cmd = data['command']
            response = {'message': 'Comando ejecutado'}
            
            if cmd.startswith('motor:'):
                _, steps, speed, dir = cmd.split(':')
                move_motor(int(steps), int(speed), int(dir))
                response['message'] = f'Motor movió {steps} pasos'
            elif cmd == 'motorStop':
                ENABLE_PIN.value(1)
                response['message'] = 'Motor detenido'
            elif cmd == 'bombaOn':
                control_bomba(True)
                response['message'] = 'Bomba encendida'
            elif cmd == 'bombaOff':
                control_bomba(False)
                response['message'] = 'Bomba apagada'
            elif cmd.startswith('playMusic:'):
                composer = cmd.split(':')[1]
                play_music(composer)
                response['message'] = f'Reproduciendo {composer}'
            elif cmd == 'stopMusic':
                stop_music()
                response['message'] = 'Música detenida'
            else:
                response['message'] = 'Comando inválido'
                
            conn.send(b'HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n\r\n')
            conn.send(json.dumps(response))
            
        except Exception as e:
            conn.send(b'HTTP/1.1 400 Bad Request\r\n\r\n')
    elif b'GET /get_image' in request:
        # Serve the image from ESP32-CAM
        image_data = get_esp32cam_image()
        if image_data:
            conn.send(b'HTTP/1.1 200 OK\r\nContent-Type: image/jpeg\r\n\r\n')
            conn.send(image_data)
        else:
            conn.send(b'HTTP/1.1 500 Internal Server Error\r\n\r\nFailed to get image')
    else:
        conn.send(b'HTTP/1.1 200 OK\r\nContent-Type: text/html\r\n\r\n' + HTML)
    
    conn.close()