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
HTML = """
<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>Control de Motores y Cámara</title>
    <style>
/*! tailwindcss v4.1.11 | MIT License | https://tailwindcss.com */@layer properties{@supports (((-webkit-hyphens:none)) and (not (margin-trim:inline))) or ((-moz-orient:inline) and (not (color:rgb(from red r g b)))){*,:before,:after,::backdrop{--tw-border-style:solid;--tw-font-weight:initial;--tw-outline-style:solid}}}@layer theme{:root,:host{--font-sans:ui-sans-serif,system-ui,sans-serif,"Apple Color Emoji","Segoe UI Emoji","Segoe UI Symbol","Noto Color Emoji";--font-mono:ui-monospace,SFMono-Regular,Menlo,Monaco,Consolas,"Liberation Mono","Courier New",monospace;--color-black:#000;--color-white:#fff;--spacing:.25rem;--text-sm:.875rem;--text-sm--line-height:calc(1.25/.875);--text-base:1rem;--text-base--line-height: 1.5 ;--text-lg:1.125rem;--text-lg--line-height:calc(1.75/1.125);--text-3xl:1.875rem;--text-3xl--line-height: 1.2 ;--font-weight-bold:700;--default-font-family:var(--font-sans);--default-mono-font-family:var(--font-mono)}}@layer base{*,:after,:before,::backdrop{box-sizing:border-box;border:0 solid;margin:0;padding:0}::file-selector-button{box-sizing:border-box;border:0 solid;margin:0;padding:0}html,:host{-webkit-text-size-adjust:100%;tab-size:4;line-height:1.5;font-family:var(--default-font-family,ui-sans-serif,system-ui,sans-serif,"Apple Color Emoji","Segoe UI Emoji","Segoe UI Symbol","Noto Color Emoji");font-feature-settings:var(--default-font-feature-settings,normal);font-variation-settings:var(--default-font-variation-settings,normal);-webkit-tap-highlight-color:transparent}hr{height:0;color:inherit;border-top-width:1px}abbr:where([title]){-webkit-text-decoration:underline dotted;text-decoration:underline dotted}h1,h2,h3,h4,h5,h6{font-size:inherit;font-weight:inherit}a{color:inherit;-webkit-text-decoration:inherit;text-decoration:inherit}b,strong{font-weight:bolder}code,kbd,samp,pre{font-family:var(--default-mono-font-family,ui-monospace,SFMono-Regular,Menlo,Monaco,Consolas,"Liberation Mono","Courier New",monospace);font-feature-settings:var(--default-mono-font-feature-settings,normal);font-variation-settings:var(--default-mono-font-variation-settings,normal);font-size:1em}small{font-size:80%}sub,sup{vertical-align:baseline;font-size:75%;line-height:0;position:relative}sub{bottom:-.25em}sup{top:-.5em}table{text-indent:0;border-color:inherit;border-collapse:collapse}:-moz-focusring{outline:auto}progress{vertical-align:baseline}summary{display:list-item}ol,ul,menu{list-style:none}img,svg,video,canvas,audio,iframe,embed,object{vertical-align:middle;display:block}img,video{max-width:100%;height:auto}button,input,select,optgroup,textarea{font:inherit;font-feature-settings:inherit;font-variation-settings:inherit;letter-spacing:inherit;color:inherit;opacity:1;background-color:#0000;border-radius:0}::file-selector-button{font:inherit;font-feature-settings:inherit;font-variation-settings:inherit;letter-spacing:inherit;color:inherit;opacity:1;background-color:#0000;border-radius:0}:where(select:is([multiple],[size])) optgroup{font-weight:bolder}:where(select:is([multiple],[size])) optgroup option{padding-inline-start:20px}::file-selector-button{margin-inline-end:4px}::placeholder{opacity:1}@supports (not ((-webkit-appearance:-apple-pay-button))) or (contain-intrinsic-size:1px){::placeholder{color:currentColor}@supports (color:color-mix(in lab,red,red)){::placeholder{color:color-mix(in oklab,currentcolor 50%,transparent)}}}textarea{resize:vertical}::-webkit-search-decoration{-webkit-appearance:none}::-webkit-date-and-time-value{min-height:1lh;text-align:inherit}::-webkit-datetime-edit{display:inline-flex}::-webkit-datetime-edit-fields-wrapper{padding:0}::-webkit-datetime-edit{padding-block:0}::-webkit-datetime-edit-year-field{padding-block:0}::-webkit-datetime-edit-month-field{padding-block:0}::-webkit-datetime-edit-day-field{padding-block:0}::-webkit-datetime-edit-hour-field{padding-block:0}::-webkit-datetime-edit-minute-field{padding-block:0}::-webkit-datetime-edit-second-field{padding-block:0}::-webkit-datetime-edit-millisecond-field{padding-block:0}::-webkit-datetime-edit-meridiem-field{padding-block:0}:-moz-ui-invalid{box-shadow:none}button,input:where([type=button],[type=reset],[type=submit]){appearance:button}::file-selector-button{appearance:button}::-webkit-inner-spin-button{height:auto}::-webkit-outer-spin-button{height:auto}[hidden]:where(:not([hidden=until-found])){display:none!important}}@layer components;@layer utilities{.mx-auto{margin-inline:auto}.mt-0{margin-top:calc(var(--spacing)*0)}.mt-16{margin-top:calc(var(--spacing)*16)}.mb-4{margin-bottom:calc(var(--spacing)*4)}.flex{display:flex}.w-16{width:calc(var(--spacing)*16)}.w-full{width:100%}.max-w-\[90\%\]{max-width:90%}.max-w-\[645px\]{max-width:645px}.flex-col{flex-direction:column}.items-center{align-items:center}.justify-end{justify-content:flex-end}.gap-1{gap:calc(var(--spacing)*1)}.gap-2\.5{gap:calc(var(--spacing)*2.5)}.gap-4{gap:calc(var(--spacing)*4)}.gap-8{gap:calc(var(--spacing)*8)}.rounded-\[5px\]{border-radius:5px}.border-t-4{border-top-style:var(--tw-border-style);border-top-width:4px}.border-black{border-color:var(--color-black)}.bg-\[\#FF7A05\]{background-color:#ff7a05}.bg-\[\#FFEDD6\]{background-color:#ffedd6}.bg-white{background-color:var(--color-white)}.p-2{padding:calc(var(--spacing)*2)}.p-5{padding:calc(var(--spacing)*5)}.p-8{padding:calc(var(--spacing)*8)}.px-3{padding-inline:calc(var(--spacing)*3)}.px-4{padding-inline:calc(var(--spacing)*4)}.py-2{padding-block:calc(var(--spacing)*2)}.pt-10{padding-top:calc(var(--spacing)*10)}.text-center{text-align:center}.text-3xl{font-size:var(--text-3xl);line-height:var(--tw-leading,var(--text-3xl--line-height))}.text-base{font-size:var(--text-base);line-height:var(--tw-leading,var(--text-base--line-height))}.text-sm{font-size:var(--text-sm);line-height:var(--tw-leading,var(--text-sm--line-height))}.text-\[32px\]{font-size:32px}.font-bold{--tw-font-weight:var(--font-weight-bold);font-weight:var(--font-weight-bold)}.outline-2{outline-style:var(--tw-outline-style);outline-width:2px}.placeholder\:text-black\/50::placeholder{color:#00000080}@supports (color:color-mix(in lab,red,red)){.placeholder\:text-black\/50::placeholder{color:color-mix(in oklab,var(--color-black)50%,transparent)}}@media (min-width:40rem){.sm\:text-lg{font-size:var(--text-lg);line-height:var(--tw-leading,var(--text-lg--line-height))}}}@property --tw-border-style{syntax:"*";inherits:false;initial-value:solid}@property --tw-font-weight{syntax:"*";inherits:false}@property --tw-outline-style{syntax:"*";inherits:false;initial-value:solid}
    </style>
  </head>
  <body class="bg-[#FFEDD6]">
    <main
      class="w-full mx-auto pt-10 max-w-[90%] flex flex-col gap-8 items-center"
    >
      <header class="flex flex-col gap-4 text-center">
        <h1 class="text-3xl font-bold p-2">Monitorea tu comedesp32</h1>
        <p class="mt-0 mb-4 sm:text-lg text-base font-base text-foreground">
          Comedesp32 es el comedero para mascotas impulsado por el poder
          conjunto de c++, Python y el esp32.
        </p>
      </header>
      <section
        class="w-full max-w-[645px] bg-white rounded-[5px] p-8 outline-2 flex flex-col gap-4"
      >
        <h2 class="text-3xl font-bold">Comida</h2>
        <div>
          <p>Selecciona el horario para dispensar la comida de tu mascota.</p>
          <p>
            El horario actual es a las
            <span class="font-bold">16:00</span> horas
          </p>
        </div>
        <div>
          <p class="font-bold text-sm">Horario (hh:mm:ss)</p>
          <div class="flex gap-1 items-center">
            <input
              type="number"
              min="0"
              max="24"
              class="outline-2 rounded-[5px] placeholder:text-black/50 py-2 px-3 w-16"
              placeholder="15"
            />
            <p class="font-bold text-[32px]">:</p>
            <input
              type="number"
              min="0"
              max="60"
              class="outline-2 rounded-[5px] placeholder:text-black/50 py-2 px-3 w-16"
              placeholder="30"
            />
            <p class="font-bold text-[32px]">:</p>
            <input
              type="number"
              min="0"
              max="60"
              class="outline-2 rounded-[5px] placeholder:text-black/50 py-2 px-3 w-16"
              placeholder="00"
            />
          </div>
        </div>
        <div class="w-full flex justify-end gap-2.5">
          <button class="outline-2 rounded-[5px] py-2 px-4">Borrar</button>
          <button class="outline-2 rounded-[5px] py-2 px-4 bg-[#FF7A05]">
            Guardar cambios
          </button>
        </div>
      </section>
      <section
        class="w-full max-w-[645px] bg-white rounded-[5px] p-8 outline-2 flex flex-col gap-4"
      >
        <h2 class="text-3xl font-bold">Agua</h2>
        <div>
          <p>Selecciona el horario para dispensar agua a tu mascota.</p>
          <p>
            El horario actual es a las
            <span class="font-bold">16:00</span> horas
          </p>
        </div>
        <div>
          <p class="font-bold text-sm">Horario (hh:mm:ss)</p>
          <div class="flex gap-1 items-center">
            <input
              type="number"
              min="0"
              max="24"
              class="outline-2 rounded-[5px] placeholder:text-black/50 py-2 px-3 w-16"
              placeholder="15"
            />
            <p class="font-bold text-[32px]">:</p>
            <input
              type="number"
              min="0"
              max="60"
              class="outline-2 rounded-[5px] placeholder:text-black/50 py-2 px-3 w-16"
              placeholder="30"
            />
            <p class="font-bold text-[32px]">:</p>
            <input
              type="number"
              min="0"
              max="60"
              class="outline-2 rounded-[5px] placeholder:text-black/50 py-2 px-3 w-16"
              placeholder="00"
            />
          </div>
        </div>
        <div class="w-full flex justify-end gap-2.5">
          <button class="outline-2 rounded-[5px] py-2 px-4">Borrar</button>
          <button class="outline-2 rounded-[5px] py-2 px-4 bg-[#FF7A05]">
            Guardar cambios
          </button>
        </div>
      </section>
    </main>
    <footer class="mt-16 border-t-4 border-black p-5 bg-white text-center">
      <p>
        Develop by
        <a class="font-bold" href="https://github.com/ch3ber">@ch3ber</a> and
        <a class="font-bold" href="https://github.com/j1leo">@j1eo</a> under MIT
        License.
      </p>
    </footer>
    <script>
      async function sendCommand(cmd) {
        const status = document.getElementById("status");
        status.textContent = "Enviando...";

        try {
          const response = await fetch("/control", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ command: cmd }),
          });
          const result = await response.json();
          status.textContent = result.message;
        } catch (e) {
          status.textContent = "Error: " + e.message;
        }
      }

      async function getCameraImage() {
        const status = document.getElementById("status");
        const imgElement = document.getElementById("cameraImage");

        status.textContent = "Obteniendo imagen de la cámara...";
        try {
          const response = await fetch("/get_image");
          if (response.ok) {
            const blob = await response.blob();
            imgElement.src = URL.createObjectURL(blob);
            status.textContent =
              "Imagen actualizada: " + new Date().toLocaleTimeString();
          } else {
            status.textContent = "Error al obtener imagen";
          }
        } catch (e) {
          status.textContent = "Error: " + e.message;
        }
      }

      function controlMotor() {
        const steps = document.getElementById("motor_steps").value;
        const speed = document.getElementById("motor_speed").value;
        sendCommand(`motor:${steps}:${speed}:1`);
      }

      function stopMotor() {
        sendCommand("motorStop");
      }

      function controlBomba(state) {
        sendCommand(state ? "bombaOn" : "bombaOff");
      }

      function playMusic(composer) {
        sendCommand(`playMusic:${composer}`);
      }

      function stopMusic() {
        sendCommand("stopMusic");
      }

      // Auto-refresh image every 5 seconds
      setInterval(getCameraImage, 5000);
      // Get first image on page load
      window.onload = getCameraImage;
    </script>
  </body>
</html>
"""

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