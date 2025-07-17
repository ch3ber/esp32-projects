# Physic-LED Web Monitor

Control and monitor an **ESP32 on-board (or external) LED** from a web page **and** from a physical push-button.  
The page reflects the real state of the LED in (near) real-time with no manual refresh.

```
┌─── physical world ───┐              ┌──── network ────┐
│ Push-button 15       │──IRQ──► ESP32 ▷ Web server ◁─── Browser / `curl`
│ LED 16               │◄────────────┘              └───────────┘
```

---

## 1. Hardware

* ESP32 (tested with **ESP32-DevKitC V4**)
* LED connected to **GPIO 16** *or* use the on-board LED (adapt `LED_PIN` in `main.py` if different).
* Momentary push-button between **GPIO 15** and **GND** (internal pull-up is enabled).

```
GPIO 15 ----┤ ├---- GND   <- push-button

GPIO 16 ---->|LED|---- GND
```

---

## 2. Flash MicroPython firmware

Download the latest binary from <https://micropython.org/download/esp32/> and flash:

```bash
esptool.py --chip esp32 erase_flash
esptool.py --chip esp32 --baud 460800 write_flash -z 0x1000 esp32-YYYYMMDD-vX.Y.bin
```

> `esptool.py` is installed with `pip install esptool`.

---

## 3. Upload the project

You only need the contents of the `physic-led-web-monitor` folder on the board.

### Using mpremote (recommended)

```bash
pip install mpremote

# Copy files recursively to the board root (/). Adjust port when needed.
mpremote connect /dev/ttyUSB0 fs cp -r physic-led-web-monitor/* :

# Set the project to run on boot (optional, if you already placed boot.py & main.py above).
mpremote connect /dev/ttyUSB0 reset
```

### Alternatives

* [ampy](https://github.com/scientifichackers/ampy)
* [rshell](https://github.com/dhylands/rshell)

---

## 4. Running

1. Reset or power-cycle the ESP32.
2. The board starts a **Wi-Fi Access Point** with the default MicroPython SSID (`MicroPython-xxxx`).  
   Connect your computer/phone to it.
3. Open the serial REPL or check the boot log — you will see a line like:

   ```text
   Servidor en  http://192.168.4.1/
   ```

4. Navigate to that URL. You should see the control page.

### What you can do

* Press **“Encender” / “Apagar”** – the LED toggles instantly.
* **Push the physical button** – the page updates automatically within 0.5 s.

---

## 5. HTTP API

You can script the LED with plain HTTP:

* `GET /` – Main HTML page.
* `GET /led?state=on` – Turn LED **on** (`off` to switch off). Returns **204 No Content**.
* `GET /status` – Returns `on` or `off` as plain text.

Example with `curl`:

```bash
# Turn on
curl "http://192.168.4.1/led?state=on"

# Query state
curl -s http://192.168.4.1/status

# Toggle from a shell script
state=$(curl -s http://192.168.4.1/status)
[ "$state" = on ] && new=off || new=on
curl "http://192.168.4.1/led?state=$new"
```

---

## 6. File tree on the board

```
/
├── boot.py          # minimal boot script (starts network, optional)
├── main.py          # web server + button interrupt logic
├── microdot.py      # Micro framework (included locally so no pip needed)
└── www/
    └── index.html   # frontend UI (pure HTML/JS/CSS)
```

---

## 7. Useful mpremote snippets

```bash
# Follow the serial output (REPL)
mpremote connect /dev/ttyUSB0 repl

# Soft reset without disconnecting
mpremote connect /dev/ttyUSB0 soft-reset

# List files on the board
mpremote connect /dev/ttyUSB0 fs ls

# Remove project (cleanup)
mpremote connect /dev/ttyUSB0 fs rm -r www main.py microdot.py boot.py
```

---

## 8. Tweaks & notes

* **Polling interval** – in `www/index.html` you can change the `500` ms of `setInterval` to a faster/slower value.
* **Different pins** – adjust `LED_PIN` and `BUTTON_PIN` constants in `main.py`.
* **Station mode** – replace the AP initialization in `main()` with your own Wi-Fi credentials to join an existing network.

---

## 9. License

This project is released under the terms of the **MIT license** (see `LICENSE`).

