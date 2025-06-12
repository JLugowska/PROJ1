import network
import time
import ujson
import struct
from umqtt.simple import MQTTClient
import machine

# --- Zmienne globalne Wi-Fi i MQTT ---
SSID = ""
PASSWORD = ""

MQTT_BROKER = "broker.emqx.io"
MQTT_PORT = 1883
MQTT_CLIENT_ID = "esp32_test_client"
MQTT_TOPIC_DATA = b'projekt1-2/pw/dane'
MQTT_TOPIC_STATUS = b'projekt1-2/pw/status'

# --- Funkcje pomocnicze Wi-Fi i MQTT ---
def connect_wifi():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    wlan.connect(SSID, PASSWORD)
    print("Łączenie z Wi-Fi...")
    while not wlan.isconnected():
        time.sleep(1)
        print(".", end="")
    print("\nPołączono z Wi-Fi:", wlan.ifconfig())

def connect_mqtt():
    print("Łączenie z MQTT...")
    client = MQTTClient(
        client_id=MQTT_CLIENT_ID,
        server=MQTT_BROKER,
        port=MQTT_PORT,
        keepalive=30
    )
    client.set_last_will(MQTT_TOPIC_STATUS, b"offline", retain=True)
    client.connect()
    client.publish(MQTT_TOPIC_STATUS, b"online", retain=True)
    print("Połączono z MQTT")
    return client

# --- Stałe i definicje klas (bez zmian) ---
REG_ADC_VAL = 0x00
REG_CFG = 0x01
START_CONVERSION_BIT = 0x8000
MUX_DIFF_0_1 = 0x0000
MUX_DIFF_2_3 = 0x3000
PGA_6V    = 0x0000
PGA_4V    = 0x0200
PGA_2V    = 0x0400
PGA_1V    = 0x0600
PGA_0_5V  = 0x0800
PGA_0_25V = 0x0A00
PGA_NAPIECIA = {
    PGA_6V: 6.144, PGA_4V: 4.096, PGA_2V: 2.048,
    PGA_1V: 1.024, PGA_0_5V: 0.512, PGA_0_25V: 0.256
}
MODE_ONE_SHOT    = 0x0100
ADS1115_DR_860SPS  = 0x00E0
COMPARATOR_DISABLE = 0x0003
I2C0_SDA_PIN_NUM = 8
I2C0_SCL_PIN_NUM = 9
I2C1_SDA_PIN_NUM = 6
I2C1_SCL_PIN_NUM = 7
R_SHUNT1_OHM = 1
R_SHUNT2_OHM = 1
MNOZNIK_DZIELNIKA_V_SYS = 1.6557
ADC1_ADDR = 0x48
ADC2_ADDR = 0x49
PGA_FOR_DIVIDED_V_SYS = PGA_4V
PGA_FOR_CURRENT_SHUNTS = PGA_6V
DATA_RATE_SETTING = ADS1115_DR_860SPS

class BazowyADS:
    def __init__(self, i2c_instance, device_address):
        self.i2c = i2c_instance
        self.address = device_address
        self.config_buffer = bytearray(2)
        self.read_buffer = bytearray(2)

    def _write_config(self, config_value):
        self.config_buffer[0] = (config_value >> 8) & 0xFF
        self.config_buffer[1] = config_value & 0xFF
        try:
            self.i2c.writeto_mem(self.address, REG_CFG, self.config_buffer)
        except OSError as e:
            print(f"!!! EIO _write_config ADC {hex(self.address)}: {e}")
            raise

    def _wait_for_conversion(self, timeout_ms=2):
        start_time = time.ticks_ms()
        operational_status_byte_msb = 0
        while not (operational_status_byte_msb & (START_CONVERSION_BIT >> 8)):
            if time.ticks_diff(time.ticks_ms(), start_time) > timeout_ms:
                raise OSError(f"Timeout conv ADC {hex(self.address)}")
            try:
                self.i2c.writeto(self.address, b'\x01')
                self.i2c.readfrom_into(self.address, self.config_buffer)
                operational_status_byte_msb = self.config_buffer[0]
            except OSError as e:
                print(f"!!! EIO _wait_for_conv ADC {hex(self.address)}: {e}")
                raise

    def _read_conversion_register(self):
        try:
            self.i2c.readfrom_mem_into(self.address, REG_ADC_VAL, self.read_buffer)
            return self.read_buffer
        except OSError as e:
            print(f"!!! EIO _read_conv_reg ADC {hex(self.address)}: {e}")
            raise

class CzujnikADS1115(BazowyADS):
    def __init__(self, i2c_instance, device_address):
        super().__init__(i2c_instance, device_address)
        self.current_pga_fs_voltage = PGA_NAPIECIA[PGA_4V]

    def odczytaj_napiecie(self, mux_setting, pga_setting=PGA_4V, dr_setting=ADS1115_DR_860SPS):
        try:
            self.current_pga_fs_voltage = PGA_NAPIECIA[pga_setting]
        except KeyError:
            print(f"ERR PGA {hex(pga_setting)} ADC {hex(self.address)}")
            self.current_pga_fs_voltage = PGA_NAPIECIA[PGA_4V]
            pga_setting = PGA_4V
        config = (START_CONVERSION_BIT | mux_setting | pga_setting |
                  MODE_ONE_SHOT | dr_setting | COMPARATOR_DISABLE)
        self._write_config(config)
        self._wait_for_conversion()
        raw_bytes = self._read_conversion_register()
        raw_value = struct.unpack('>h', raw_bytes)[0]
        voltage = (raw_value / 32767.0) * self.current_pga_fs_voltage
        return voltage

# --- ZMIANA W TEJ FUNKCJI ---
def zbieraj_i_przetwarzaj_dane(adc1, adc2):
    while True:
        val_V_sys_actual = float('nan')
        val_I_1 = float('nan')
        val_I_2 = float('nan')

        if adc1:
            try:
                val_V_sys_at_adc = adc1.odczytaj_napiecie(
                    mux_setting=MUX_DIFF_0_1, pga_setting=PGA_FOR_DIVIDED_V_SYS, dr_setting=DATA_RATE_SETTING
                )
                if val_V_sys_at_adc == val_V_sys_at_adc:
                    val_V_sys_actual = val_V_sys_at_adc * MNOZNIK_DZIELNIKA_V_SYS

                v_drop_shunt1 = adc1.odczytaj_napiecie(
                    mux_setting=MUX_DIFF_2_3, pga_setting=PGA_FOR_CURRENT_SHUNTS, dr_setting=DATA_RATE_SETTING
                )
                if v_drop_shunt1 == v_drop_shunt1:
                    val_I_1 = v_drop_shunt1 / R_SHUNT1_OHM
            except OSError:
                pass

        if adc2:
            try:
                v_drop_shunt2 = adc2.odczytaj_napiecie(
                    mux_setting=MUX_DIFF_0_1, pga_setting=PGA_FOR_CURRENT_SHUNTS, dr_setting=DATA_RATE_SETTING
                )
                if v_drop_shunt2 == v_drop_shunt2:
                    val_I_2 = v_drop_shunt2 / R_SHUNT2_OHM
            except OSError:
                pass

        yield val_V_sys_actual, val_I_1, val_I_2
        time.sleep(0.2)

# --- Sekcja inicjalizacji I2C i ADC (bez zmian) ---
i2c0, i2c1 = None, None
print(f"Init I2C0: SDA=GP{I2C0_SDA_PIN_NUM}, SCL=GP{I2C0_SCL_PIN_NUM}")
try:
    i2c0 = machine.I2C(0, sda=machine.Pin(I2C0_SDA_PIN_NUM), scl=machine.Pin(I2C0_SCL_PIN_NUM), freq=25000)
except Exception as e:
    print(f"FAIL I2C0 init: {e}")

print(f"Init I2C1: SDA=GP{I2C1_SDA_PIN_NUM}, SCL=GP{I2C1_SCL_PIN_NUM}")
try:
    i2c1 = machine.I2C(1, sda=machine.Pin(I2C1_SDA_PIN_NUM), scl=machine.Pin(I2C1_SCL_PIN_NUM), freq=25000)
except Exception as e:
    print(f"FAIL I2C1 init: {e}")

detected_on_i2c0, detected_on_i2c1 = [], []
if i2c0:
    print("Scan I2C0...")
    try: detected_on_i2c0 = i2c0.scan()
    except Exception as e: print(f"  ERR Scan I2C0: {e}")
    print(f"  Found I2C0: {[hex(addr) for addr in detected_on_i2c0]}")

if i2c1:
    print("Scan I2C1...")
    try: detected_on_i2c1 = i2c1.scan()
    except Exception as e: print(f"  ERR Scan I2C1: {e}")
    print(f"  Found I2C1: {[hex(addr) for addr in detected_on_i2c1]}")

adc1, adc2 = None, None
if i2c0 and ADC1_ADDR in detected_on_i2c0:
    try:
        adc1 = CzujnikADS1115(i2c0, ADC1_ADDR)
        print(f"ADC1 ({hex(ADC1_ADDR)}) I2C0 init OK.")
    except Exception as e: print(f"ERR ADC1 init ({hex(ADC1_ADDR)}): {e}")
else:
    if i2c0: print(f"ADC1 ({hex(ADC1_ADDR)}) not found I2C0.")

if i2c1 and ADC2_ADDR in detected_on_i2c1:
    try:
        adc2 = CzujnikADS1115(i2c1, ADC2_ADDR)
        print(f"ADC2 ({hex(ADC2_ADDR)}) I2C1 init OK.")
    except Exception as e: print(f"ERR ADC2 init ({hex(ADC2_ADDR)}): {e}")
else:
    if i2c1: print(f"ADC2 ({hex(ADC2_ADDR)}) not found I2C1.")

# --- Główna pętla (bez zmian) ---
print("\n--- Start pętli głównej (usuwanie tylko w pierwszej paczce) ---")
try:
    if not adc1 and not adc2:
        print("Nie zainicjowano żadnego przetwornika ADC. Zatrzymywanie.")
    else:
        connect_wifi()
        mqtt_client = connect_mqtt()
        
        generator_danych = zbieraj_i_przetwarzaj_dane(adc1, adc2,)

        for numer_paczki, (napiecie, prad1, prad2) in enumerate(generator_danych, 1):
            print(f"\n--- PACZKA DANYCH NR {numer_paczki} ---")
            
            print(f"V_sys: {napiecie}")
            print(f"I_1: {prad1}")
            print(f"I_2: {prad2}")
            
            payload = {
                "voltage": round(napiecie, 3) if napiecie == napiecie else None,
                "current1": round(prad1, 3) if prad1 == prad1 else None,
                "current2": round(prad2, 3) if prad2 == prad2 else None
            }

            msg = ujson.dumps(payload)
            try:
                mqtt_client.publish(MQTT_TOPIC_DATA, msg)
                print("MQTT wysłano:", msg)
            except Exception as e:
                print("Błąd MQTT:", e)



except KeyboardInterrupt:
    print("\nPętla zatrzymana przez użytkownika.")
except Exception as e:
    print(f"\nKRYTYCZNY BŁĄD GŁÓWNEJ PĘTLI: {e}")
finally:
    print("Program zakończył działanie.")


