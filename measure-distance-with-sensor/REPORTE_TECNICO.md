# Reporte Tecnico - Proyecto `measure-distance-with-sensor`

## 1. Resumen del proyecto
Este proyecto implementa un medidor de distancia con un sensor ultrasonico **HC-SR04** conectado a un **ESP32** con **MicroPython**. El ESP32:
- toma mediciones periodicas de distancia,
- aplica un filtrado para estabilizar la lectura,
- publica los datos en un servidor web local,
- y muestra la informacion en una interfaz web ligera (HTML/CSS/JS).

El sistema esta pensado para uso local sin internet, usando el ESP32 como punto de acceso Wi-Fi.

---

## 2. Que hace el sistema
Funcionalmente, el sistema:
1. Crea una red Wi-Fi propia (modo Access Point).
2. Ejecuta un servidor HTTP en el ESP32 (puerto 80).
3. Lee distancia del HC-SR04 cada `300 ms`.
4. Expone un endpoint JSON con el valor de distancia y estado.
5. Sirve una pagina web que consulta ese endpoint cada segundo y grafica la serie en tiempo real.
6. Calcula y muestra una metrica de linealidad (`R^2`) sobre las ultimas muestras visibles.

---

## 3. Arquitectura general
El proyecto se organiza en 3 archivos:

- `boot.py`: configuracion de red AP del ESP32.
- `main.py`: logica de medicion, estado y servidor web.
- `www/index.html`: dashboard web liviano para visualizar datos.

Flujo general:

1. Arranque del ESP32.
2. `boot.py` levanta la red Wi-Fi AP.
3. `main.py` inicia tarea asincrona de medicion.
4. `main.py` inicia servidor Microdot (`/` y `/metrics`).
5. Cliente abre `http://192.168.4.1/`.
6. Frontend consulta `/metrics` periodicamente y actualiza UI/grafica.

---

## 4. Requisitos de hardware
- 1x ESP32.
- 1x Sensor ultrasonico HC-SR04.
- Cables Dupont.
- Fuente de alimentacion estable para el ESP32.

### Conexion de pines (segun codigo actual)
- `TRIG_PIN = 5` (ESP32 GPIO5 -> TRIG del HC-SR04)
- `ECHO_PIN = 18` (ESP32 GPIO18 <- ECHO del HC-SR04)

> Nota tecnica: el pin ECHO del HC-SR04 suele ser de 5V en algunos modulos; en disenos robustos se recomienda adaptar nivel a 3.3V para proteger el ESP32.

---

## 5. Requisitos de software
- Firmware MicroPython compatible con ESP32.
- Libreria `microdot` disponible en el filesystem del ESP32.
- Archivos del proyecto copiados al dispositivo:
  - `/boot.py`
  - `/main.py`
  - `/www/index.html`

---

## 6. Funcionamiento interno (backend MicroPython)

### 6.1 Configuracion de red (`boot.py`)
Al iniciar, el ESP32 activa interfaz AP:
- SSID: `ESP32_ch3ber`
- Password: `chavez123`
- Seguridad: WPA/WPA2 PSK
- Canal: 6
- Max clientes: 4
- IP por defecto del AP: `192.168.4.1`

Esto permite que un telefono o PC se conecte directamente al ESP32 sin router externo.

### 6.2 Lectura del sensor (`main.py`)
La funcion `read_distance_cm()`:
1. Envia un pulso de 10 us en TRIG.
2. Mide el tiempo del pulso de retorno en ECHO con `machine.time_pulse_us(...)`.
3. Si hay timeout (`< 0`), retorna `None`.
4. Convierte tiempo a distancia:

`distancia_cm = (tiempo_us * 0.0343) / 2`

Donde `0.0343 cm/us` es la velocidad aproximada del sonido.

### 6.3 Tarea de medicion asincrona
`measure_task()` se ejecuta en bucle cada `SAMPLE_MS = 300` ms:
- si hay lectura valida, actualiza la distancia,
- si falla, marca estado no valido y registra error.

Se aplica filtro exponencial (suavizado):

`distance_filtrada = ALPHA * nueva + (1 - ALPHA) * anterior`

Con `ALPHA = 0.3`, que reduce ruido sin perder demasiada respuesta.

### 6.4 Estado global
Variables compartidas del sistema:
- `distance_cm`: ultima distancia filtrada.
- `distance_ok`: bandera booleana de validez de lectura.
- `last_error`: texto de error (ej. `timeout`).

### 6.5 Servidor web
Se usa Microdot con 2 rutas:

- `GET /`
  - devuelve `www/index.html`.
- `GET /metrics`
  - devuelve JSON con:
    - `distance_cm` (float)
    - `ok` (bool)
    - `error` (string)
    - `sample_ms` (int)

Ejemplo de respuesta:
```json
{"distance_cm": 42.38, "ok": true, "error": "", "sample_ms": 300}
```

---

## 7. Funcionamiento interno (frontend)
El archivo `www/index.html` es una interfaz optimizada para bajo peso:

- muestra 3 tarjetas: distancia, linealidad R2 y estado,
- consulta `/metrics` cada 1000 ms,
- mantiene un buffer de las ultimas `MAX = 72` muestras,
- dibuja grafica en `<canvas>` (serie real + linea de tendencia),
- calcula `R2` por regresion lineal simple sobre las muestras visibles.

### 7.1 Metrica R2
`R2` ayuda a estimar que tan lineal/estable ha sido la evolucion reciente:
- cercano a 1: comportamiento altamente lineal,
- cercano a 0 o negativo: variacion irregular o ruido alto.

### 7.2 Resiliencia del frontend
- usa bandera `busy` para evitar solicitudes simultaneas si una tarda.
- en desconexion, muestra estado `sin conexion`.
- en error de medicion backend, muestra `error`.

---

## 8. Parametros clave del sistema
Configurables en `main.py`:
- `TRIG_PIN`, `ECHO_PIN`: pines GPIO.
- `SAMPLE_MS`: periodo de muestreo backend (actual 300 ms).
- `ECHO_TIMEOUT_US`: timeout de eco (actual 30000 us).
- `ALPHA`: suavizado exponencial (actual 0.3).

Configurables en `index.html`:
- `MAX`: cantidad de muestras en grafica (actual 72).
- intervalo de polling en frontend (`setInterval(tick, 1000)`).

---

## 9. Guia de uso desde cero
1. Flashear MicroPython en el ESP32.
2. Copiar `boot.py`, `main.py` y carpeta `www/` al dispositivo.
3. Asegurar que la libreria `microdot` este instalada en el ESP32.
4. Reiniciar ESP32.
5. Conectar el telefono/PC a la red Wi-Fi `ESP32_ch3ber`.
6. Abrir navegador en `http://192.168.4.1/`.
7. Verificar que el estado sea `ok` y cambie la distancia al mover un objeto.

---

## 10. Rendimiento y limitaciones

### Fortalezas
- Arquitectura simple y mantenible.
- Interfaz web ligera (adecuada para ESP32).
- No requiere internet ni broker externo.
- Filtrado reduce ruido en medicion.

### Limitaciones
- Seguridad basica: AP con credenciales fijas en codigo.
- `HTTP` sin cifrado.
- HC-SR04 sensible a angulo, superficie, temperatura y ruido ambiental.
- `R2` en frontend no es indicador fisico de precision absoluta, solo tendencia estadistica local.

---

## 11. Riesgos tecnicos y recomendaciones

Recomendaciones para produccion:
1. Cambiar SSID/password por valores configurables y mas robustos.
2. Validar proteccion de nivel logico del pin ECHO (5V -> 3.3V).
3. Agregar endpoint de salud (`/health`) y uptime.
4. Exponer telemetria adicional: minima, maxima, promedio, timestamp.
5. Ajustar `SAMPLE_MS` y `ALPHA` segun dinamica real del montaje.
6. Considerar autenticacion basica para la interfaz web.

---

## 12. Pruebas sugeridas
1. Prueba de conectividad AP: conexion y carga de `/`.
2. Prueba de API: respuesta JSON correcta en `/metrics`.
3. Prueba de rango: objetos a distancias conocidas (ej. 10, 20, 30 cm).
4. Prueba de perdida de eco: cubrir sensor o alejar fuera de rango y verificar `error`.
5. Prueba de estabilidad: ejecutar 30+ minutos y observar continuidad de actualizaciones.

---

## 13. Conclusiones
`measure-distance-with-sensor` es un proyecto IoT educativo/practico bien enfocado para medir distancia y visualizarla en tiempo real desde cualquier navegador conectado al ESP32. Su diseno minimiza dependencias y peso del frontend, lo que lo hace adecuado para recursos limitados. Con mejoras menores de seguridad y robustez electrica, puede evolucionar hacia un sistema de monitoreo mas confiable para uso continuo.
