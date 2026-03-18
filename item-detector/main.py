from machine import Pin, PWM
from time import sleep_ms

# --- Configuración de pines ---
IR_EMITTER_PIN = 26  # Pin señal (S) del KY-005 (emisor IR)
IR_RECEIVER_PIN = 14  # Pin señal (S) del KY-022 (receptor IR)
BUZZER_PIN = 27  # Pin del buzzer

# --- Emisor IR KY-005 ---
# El KY-022 (TSOP1838) espera señal modulada a 38kHz
# Usamos PWM a 38kHz en el KY-005 para que el receptor la detecte
ir_emitter = PWM(Pin(IR_EMITTER_PIN), freq=38000, duty=512)

# --- Receptor IR KY-022 ---
# TSOP1838: LOW (0) = recibiendo señal IR | HIGH (1) = sin señal IR
ir_receiver = Pin(IR_RECEIVER_PIN, Pin.IN)

# --- Buzzer ---
buzzer = PWM(Pin(BUZZER_PIN), freq=2000, duty=0)

BUZZER_FREQ = 2000  # Frecuencia del tono en Hz
BUZZER_DUTY = 512  # Duty cycle (0-1023), 512 = 50%


def buzzer_on():
    buzzer.freq(BUZZER_FREQ)
    buzzer.duty(BUZZER_DUTY)


def buzzer_off():
    buzzer.duty(0)


# --- Loop principal ---
print("=== Detector de objetos con KY-005 / KY-022 ===")
print("Emisor IR (KY-005) en GPIO:", IR_EMITTER_PIN, "-> 38kHz PWM")
print("Receptor IR (KY-022) en GPIO:", IR_RECEIVER_PIN)
print("Buzzer en GPIO:", BUZZER_PIN)
print("Esperando interrupción del haz infrarrojo...")

prev_state = ir_receiver.value()

while True:
    current_state = ir_receiver.value()

    # KY-022 (TSOP1838):
    #   0 = recibiendo haz IR (sin obstáculo)
    #   1 = haz interrumpido (objeto detectado)
    if current_state == 1:
        buzzer_on()
        if prev_state == 0:
            print("-> Objeto detectado: haz IR interrumpido")
    else:
        buzzer_off()
        if prev_state == 1:
            print("-> Haz IR restaurado")

    prev_state = current_state
    sleep_ms(50)
