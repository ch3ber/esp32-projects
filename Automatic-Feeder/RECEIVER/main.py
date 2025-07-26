import network
import espnow
import machine
import ubinascii

# Configuración del relé
RELAY_PIN = machine.Pin(5, machine.Pin.OUT)
RELAY_PIN.off()  # Inicia apagado

# Configuración WiFi
sta = network.WLAN(network.STA_IF)
sta.active(True)
sta.disconnect()

# Configuración ESP-NOW
esp = espnow.ESPNow()
esp.active(True)

print(f"Cliente listo. MAC: {ubinascii.hexlify(sta.config('mac')).decode()}")

while True:
    try:
        peer, msg = esp.recv(1000)  # Timeout de 1s
        if msg == b'pumpOn':
            RELAY_PIN.on()
            print("Bomba: ENCENDIDA")
        elif msg == b'pumpOff':
            RELAY_PIN.off()
            print("Bomba: APAGADA")
    except Exception as e:
        print("Error:", e)
        # Reiniciar ESP-NOW si hay fallos
        esp.active(False)
        utime.sleep(1)
        esp.active(True)