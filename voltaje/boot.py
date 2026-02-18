import network
import esp

esp.osdebug(None)  # Silencia logs Wi-Fi

ap = network.WLAN(network.AP_IF)
ap.config(
    essid="ESP32_ch3ber", password="chavez123", authmode=network.AUTH_WPA_WPA2_PSK
)
ap.config(max_clients=4, channel=6, hidden=False)
ap.active(True)
# IP por defecto 192.168.4.1/24; si quieres fija personalizada, descomenta:
# ap.ifconfig(('192.168.10.1', '255.255.255.0', '192.168.10.1', '8.8.8.8'))
