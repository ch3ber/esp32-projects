# Item Detector — Detector de objetos con infrarrojo

Este proyecto usa un ESP32 con MicroPython para detectar objetos que
interrumpan un haz infrarrojo entre un emisor (KY-005) y un receptor
(KY-022). Cuando un objeto bloquea el haz, el buzzer suena como alerta.

## Componentes necesarios

| Componente | Descripción |
|---|---|
| ESP32 | Microcontrolador principal |
| KY-005 | Módulo emisor infrarrojo (LED IR) |
| KY-022 | Módulo receptor infrarrojo (TSOP1838) |
| Buzzer pasivo | Buzzer sin oscilador interno (controlado por PWM) |
| Cables dupont | Para las conexiones |

> **Note:** El buzzer debe ser **pasivo** (sin oscilador interno) para
> que funcione con PWM. Si usas un buzzer activo, necesitas modificar
> el código para usar un `Pin` digital en lugar de PWM.

## Diagrama de conexiones

```
ESP32              KY-005 (Emisor IR)
─────              ──────────────────
GPIO 26  ────────► S  (señal)
3.3V     ────────► medio (VCC)
GND      ────────► -  (GND)

ESP32              KY-022 (Receptor IR)
─────              ────────────────────
GPIO 14  ◄──────── S  (señal)
3.3V     ────────► medio (VCC)
GND      ────────► -  (GND)

ESP32              Buzzer pasivo
─────              ─────────────
GPIO 27  ────────► +
GND      ────────► -
```

### Tabla de pines

| Componente | Pin del módulo | GPIO del ESP32 |
|---|---|---|
| KY-005 (emisor) | S (señal) | GPIO 26 |
| KY-022 (receptor) | S (señal) | GPIO 14 |
| Buzzer | + | GPIO 27 |

## Cómo funciona

El sistema opera en tres etapas: emisión, recepción y alerta.

### 1. Emisión de señal IR (KY-005)

El módulo KY-005 contiene un LED infrarrojo. El ESP32 genera una señal
**PWM a 38 kHz** en GPIO 26 que alimenta el LED. Esta frecuencia es
necesaria porque el receptor KY-022 (TSOP1838) solo reconoce señales
IR moduladas a 38 kHz — ignora luz IR constante o a otras frecuencias.

```python
ir_emitter = PWM(Pin(IR_EMITTER_PIN), freq=38000, duty=512)
```

### 2. Recepción de señal IR (KY-022)

El módulo KY-022 contiene un sensor TSOP1838 que demodula la señal de
38 kHz y produce una salida digital:

- **LOW (0):** Está recibiendo el haz IR correctamente (sin obstáculo).
- **HIGH (1):** No recibe señal IR (el haz fue interrumpido por un
  objeto).

```python
ir_receiver = Pin(IR_RECEIVER_PIN, Pin.IN)
current_state = ir_receiver.value()
```

### 3. Activación del buzzer

El buzzer pasivo se controla mediante PWM. Cuando el receptor detecta
una interrupción en el haz (salida HIGH), el buzzer emite un tono a
2000 Hz. Cuando el haz se restaura, el buzzer se apaga.

```python
def buzzer_on():
    buzzer.freq(BUZZER_FREQ)
    buzzer.duty(BUZZER_DUTY)

def buzzer_off():
    buzzer.duty(0)
```

### Flujo del loop principal

El programa ejecuta un ciclo cada 50 ms que sigue esta lógica:

```
┌─────────────────────────┐
│  Leer estado del KY-022 │
└────────────┬────────────┘
             │
      ┌──────┴──────┐
      │ ¿Estado = 1?│
      └──────┬──────┘
         Sí  │  No
      ┌──────┴──────┐
      │             │
 Buzzer ON     Buzzer OFF
      │             │
      └──────┬──────┘
             │
   ┿ Esperar 50 ms ┿
             │
        (repetir)
```

El programa también detecta **transiciones de estado** (de 0 a 1 y
viceversa) para imprimir mensajes en la consola serial solo cuando el
estado cambia, evitando llenar la terminal con mensajes repetidos.

## Estructura del código

El archivo `main.py` contiene todo el proyecto con la siguiente
estructura:

| Sección | Líneas | Descripción |
|---|---|---|
| Imports | 1-2 | Módulos `machine` y `time` de MicroPython |
| Configuración de pines | 4-7 | Constantes con los números de GPIO |
| Emisor IR | 9-12 | PWM a 38 kHz para el KY-005 |
| Receptor IR | 14-16 | Pin digital de entrada para el KY-022 |
| Buzzer | 18-22 | PWM para el buzzer y sus parámetros |
| Funciones | 25-31 | `buzzer_on()` y `buzzer_off()` |
| Loop principal | 34-59 | Lectura del sensor y control del buzzer |

## Cómo cargar el proyecto al ESP32

Sigue estos pasos para cargar y ejecutar el proyecto en tu ESP32:

1. Instala MicroPython en tu ESP32 si aún no lo tienes. Puedes
   descargarlo de [micropython.org](https://micropython.org/download/ESP32_GENERIC/).
2. Conecta el ESP32 a tu computadora por USB.
3. Usa una herramienta como **Thonny**, **mpremote** o **ampy** para
   transferir el archivo `main.py` al ESP32.
4. Reinicia el ESP32. El programa inicia automáticamente.

Ejemplo con `mpremote`:

```bash
mpremote connect /dev/ttyUSB0 cp main.py :main.py
mpremote connect /dev/ttyUSB0 reset
```

## Personalización

Puedes ajustar estos parámetros en `main.py` según tus necesidades:

| Parámetro | Valor por defecto | Descripción |
|---|---|---|
| `IR_EMITTER_PIN` | 26 | GPIO del emisor KY-005 |
| `IR_RECEIVER_PIN` | 14 | GPIO del receptor KY-022 |
| `BUZZER_PIN` | 27 | GPIO del buzzer |
| `BUZZER_FREQ` | 2000 | Frecuencia del tono del buzzer (Hz) |
| `BUZZER_DUTY` | 512 | Volumen del buzzer (0-1023) |

## Solución de problemas

- **El buzzer no suena:** Verifica que sea un buzzer pasivo. Los buzzers
  activos no responden a PWM correctamente.
- **El sensor no detecta nada:** Asegura que el emisor y receptor estén
  alineados y enfrentados entre sí.
- **Detecciones falsas constantes:** Reduce la luz ambiental o acorta
  la distancia entre KY-005 y KY-022.
- **Sin salida en consola:** Conecta un monitor serial a 115200 baudios
  para ver los mensajes de depuración.
