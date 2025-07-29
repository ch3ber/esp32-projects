import network
import espnow
import machine
import ubinascii
import utime
# Configuración del relé (GPIO5)
RELAY_PIN = machine.Pin(5, machine.Pin.OUT, value=0)

# Inicialización robusta de ESP-NOW
def init_espnow():
    sta = network.WLAN(network.STA_IF)
    sta.active(True)
    sta.disconnect()  # ¡Crítico para ESP-NOW!
    utime.sleep(1)
    
    esp = espnow.ESPNow()
    esp.active(True)
    return esp

esp = init_espnow()
print("MAC:", ubinascii.hexlify(network.WLAN(network.STA_IF).config('mac')).decode())

while True:
    try:
        peer, msg = esp.recv(1000)  # Timeout 1s
        if msg == b'bombaOn':
            RELAY_PIN.on()
            print("Bomba: ENCENDIDA")
        elif msg == b'bombaOff':
            RELAY_PIN.off()
            print("Bomba: APAGADA")
            
    except Exception as e:
        print("Error:", e)
        # Reinicio completo ante fallos
        esp.active(False)
        utime.sleep(2)
        esp = init_espnow()