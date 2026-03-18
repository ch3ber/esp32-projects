import machine

try:
    import utime as time
except ImportError:
    import time


# ====== Hardware y ajuste ======
LDR_PIN = 34
SERVO_PIN = 18
SERVO_FREQ = 50

ADC_MAX = 4095
READ_DELAY_MS = 20

SERVO_MIN_US = 500
SERVO_MAX_US = 2500
SERVO_MIN_ANGLE = 0
SERVO_MAX_ANGLE = 180

SWEEP_MIN_ANGLE = 10
SWEEP_MAX_ANGLE = 170

MIN_SPEED_DPS = 15
MAX_SPEED_DPS = 180
FILTER_ALPHA = 0.2

DEBUG_PRINT_EVERY = 25
PWM_PERIOD_US = 1000000 // SERVO_FREQ


# ====== Notas de cableado ======
# - La fotoresistencia debe ir en divisor resistivo entre 3.3V y GND.
# - El nodo del divisor va al GPIO34.
# - El SG90 debe compartir GND con el ESP32.
# - Si el servo vibra o reinicia la placa, alimentalo con una fuente externa.


ldr = machine.ADC(machine.Pin(LDR_PIN))
servo_pwm = machine.PWM(machine.Pin(SERVO_PIN), freq=SERVO_FREQ)

try:
    ldr.atten(machine.ADC.ATTN_11DB)
except AttributeError:
    pass
except Exception:
    pass

try:
    ldr.width(machine.ADC.WIDTH_12BIT)
except AttributeError:
    pass
except Exception:
    pass


def clamp(value, low, high):
    if value < low:
        return low
    if value > high:
        return high
    return value


def read_ldr_raw():
    try:
        raw = ldr.read_u16()
        if raw > ADC_MAX:
            raw >>= 4
        return int(raw)
    except AttributeError:
        return int(ldr.read())


def normalize_ldr(raw):
    raw = clamp(raw, 0, ADC_MAX)
    return raw / float(ADC_MAX)


def angle_to_pulse_us(angle):
    angle = clamp(angle, SERVO_MIN_ANGLE, SERVO_MAX_ANGLE)
    span_angle = SERVO_MAX_ANGLE - SERVO_MIN_ANGLE
    span_us = SERVO_MAX_US - SERVO_MIN_US
    return SERVO_MIN_US + ((angle - SERVO_MIN_ANGLE) * span_us / span_angle)


def pulse_us_to_duty(pulse_us):
    pulse_us = clamp(pulse_us, SERVO_MIN_US, SERVO_MAX_US)
    return int((pulse_us / PWM_PERIOD_US) * 65535)


def set_servo_angle(angle):
    pulse_us = angle_to_pulse_us(angle)
    duty_u16 = pulse_us_to_duty(pulse_us)

    try:
        servo_pwm.duty_u16(duty_u16)
    except AttributeError:
        duty_10bit = int((duty_u16 / 65535) * 1023)
        servo_pwm.duty(clamp(duty_10bit, 0, 1023))


def ticks_ms():
    return time.ticks_ms()


def ticks_diff(now, before):
    return time.ticks_diff(now, before)


def main():
    current_angle = float(SWEEP_MIN_ANGLE)
    direction = 1.0

    raw = read_ldr_raw()
    filtered_raw = float(raw)

    set_servo_angle(current_angle)

    last_tick = ticks_ms()
    loop_count = 0

    print("Iniciando fotoresistencia-servo")
    print("LDR en GPIO%d | Servo SG90 en GPIO%d" % (LDR_PIN, SERVO_PIN))
    print("Barrido entre %d y %d grados" % (SWEEP_MIN_ANGLE, SWEEP_MAX_ANGLE))

    while True:
        raw = read_ldr_raw()
        filtered_raw = (FILTER_ALPHA * raw) + ((1.0 - FILTER_ALPHA) * filtered_raw)

        light_level = normalize_ldr(int(filtered_raw))
        speed_dps = MIN_SPEED_DPS + (light_level * (MAX_SPEED_DPS - MIN_SPEED_DPS))

        now = ticks_ms()
        delta_s = ticks_diff(now, last_tick) / 1000.0
        last_tick = now

        delta_angle = speed_dps * delta_s
        current_angle += direction * delta_angle

        if current_angle >= SWEEP_MAX_ANGLE:
            current_angle = float(SWEEP_MAX_ANGLE)
            direction = -1.0
        elif current_angle <= SWEEP_MIN_ANGLE:
            current_angle = float(SWEEP_MIN_ANGLE)
            direction = 1.0

        current_angle = clamp(current_angle, SERVO_MIN_ANGLE, SERVO_MAX_ANGLE)
        set_servo_angle(current_angle)

        if loop_count % DEBUG_PRINT_EVERY == 0:
            print(
                "raw=%4d filtered=%4d light=%.3f speed=%.1f angle=%.1f"
                % (raw, int(filtered_raw), light_level, speed_dps, current_angle)
            )

        loop_count += 1
        time.sleep_ms(READ_DELAY_MS)


try:
    main()
finally:
    try:
        servo_pwm.deinit()
    except Exception:
        pass
