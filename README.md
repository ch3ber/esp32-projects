# ESP32 MicroPython Mini-Projects

This repository is a collection of **small, self-contained projects** for the ESP32 family of micro-controllers programmed with **MicroPython**.  
Every top-level directory contains one ready-to-flash project that demonstrates or tests a single concept – for example running a web server, blinking an LED, or exposing sensor data.

| Folder | Short description |
| ------ | ----------------- |
| `esp32-ap-led` | Turn the ESP32 into a Wi-Fi access-point and blink an on-board LED that can be toggled from a web page. |
| `hello_world` | The obligatory *Hello, world!* for MicroPython on the ESP32. |
| `MicroPython` | Miscellaneous helper scripts and notes. |
| `physic-led-web-monitor` | Simple web based monitor for a physical LED. |

> **Tip**: Feel free to copy a project folder, tweak the code, and flash it to your own board – that is exactly what these examples are for!

---

## 1. Getting MicroPython on your ESP32

These projects assume your board already runs MicroPython.  
If this is the first time you use MicroPython on an ESP32 follow the steps below (takes ~5 minutes):

1. **Install prerequisites**
   ```bash
   # Linux / macOS
   pip install esptool mpremote

   # Windows (PowerShell)
   py -m pip install esptool mpremote
   ```

2. **Download the correct firmware**  
   Grab the latest *ESP32 generic* `.bin` file from the official website:  
   https://micropython.org/download/esp32/  
   (The file name looks like `esp32-<date>-vX.Y.Z.bin`).

3. **Put the board in download mode**  
   • Hold the *BOOT* (or *IO0*) button, press *EN / RST*, then release *BOOT* after ~1 s.  
   (Some boards enter download mode automatically – if flashing works you are good.)

4. **Erase the flash** *(optional but recommended when switching languages)*  
   ```bash
   esptool.py --port /dev/ttyUSB0 erase_flash      # adapt the serial port
   ```

5. **Flash MicroPython**
   ```bash
   esptool.py --chip esp32 --port /dev/ttyUSB0 \
              --baud 460800 write_flash -z 0x1000 esp32-<date>.bin
   ```

6. **Check the REPL**  
   ```bash
   mpremote connect /dev/ttyUSB0 repl
   ```
   You should be greeted by the friendly `>>>` prompt.

---

## 2. Deploying a project from this repository

All example projects are pure Python – just copy their files onto the board’s internal filesystem.

1. **Connect the board and enter the project folder**
   ```bash
   cd esp32-ap-led          # example
   ```

2. **Upload every file** (newer versions of *mpremote* support a convenient `cp` command)
   ```bash
   mpremote connect /dev/ttyUSB0 fs cp main.py :      # copy main.py to /
   mpremote connect /dev/ttyUSB0 fs cp *.py lib/ :/lib # copy helper modules
   ```
   Alternative helpers you can use are *ampy*, *rshell* or any other tool you prefer.

3. **Reset the board**
   ```bash
   mpremote connect /dev/ttyUSB0 reset
   ```
   The script`s `main.py` is executed automatically after every reset.

### Quick one-liner for small projects

If the project only consists of a single `main.py` you can do:

```bash
mpremote connect /dev/ttyUSB0 fs cp main.py : && mpremote reset
```

---

## 3. Creating your own project folder

1. Copy one of the existing directories.
2. Remove the files you do not need.
3. Hack away on the Python code.

When you are ready, upload the files as shown above – that’s it.

---

## 4. Helpful links

• Official documentation: https://docs.micropython.org  
• ESP32 pin-out reference: https://randomnerdtutorials.com/esp32-pinout/  
• mpremote user guide: https://github.com/micropython/micropython/blob/master/tools/mpremote/README.md

---

**Have fun exploring MicroPython on the ESP32!**

