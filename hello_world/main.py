from machine import Pin
import time

# Ajusta el número de pin al LED de tu placa
LED_PIN = 2

led = Pin(LED_PIN, Pin.OUT)

print("Hello, world! MicroPython arrancó correctamente.")

i = 0
while True:
    i += 1
    led.value(not led.value())  # toggle por lectura/inversión
    print("Blink #", i)
    time.sleep(1)
