import time
import board
import serial
import busio
import os
import threading
import adafruit_ads1x15.ads1115 as ADS
import RPi.GPIO as GPIO
import requests

from adafruit_ads1x15.analog_in import AnalogIn

i2c = busio.I2C(board.SCL, board.SDA)
ads = ADS.ADS1115(i2c)
chan_0 = AnalogIn(ads, ADS.P0)
chan_1 = AnalogIn(ads, ADS.P1)

# Define pins
water_pin = 18
pump_pin = 17

GPIO.setwarnings(False)  # Disable warnings from GPIO
GPIO.setmode(GPIO.BCM)

ser = serial.Serial("/dev/ttyS0", 115200)
ser.flushInput()

phone_number = '+37062920303'  # ********** change it to the phone number you want to text
text_message = ''
power_key = 6
rec_buff = ''

first_temp_check = True
first_moist_check = True
eco_mode = False

# Define the hydration and temperature threshholds for the different plant types
dry = [30, 45]
medium = [40, 80]
wet = [40, 90]

# Define the minimum the and maximum delay between watering function activations
min_delay = 1800  # 30 minutes
max_delay = 604800  # 7 days

# ThingSpeak API parameters
WRITE_API_KEY = "3F0UCN02XP8HTKQP"
BASE_URL = "https://api.thingspeak.com/update?api_key={}".format(WRITE_API_KEY)

command_lut = ['eco_mode', 'send_water', 'quit', 'help_me', 'set_plant_dry', 'set_plant_medium', 'set_plant_wet',
               'set_pot_small', 'set_pot_big', 'get_water_level', 'get_hydration', 'get_temp', 'get_data',
               'I love you, Raspi']


def read_water_level():
    # Read the water level from the sensor
    # When the sensor is in the water - the reading is 0, when there is no water the reading is 1
    if GPIO.input(water_pin) == 0:
        water_level = 1
    else:
        water_level = 0
    return water_level


def num_to_range(num, inMin, inMax, outMin,
                 outMax):  # Function to convert voltage to percentage with predefined max and min ranges
    return round(outMin + float(num - inMin) / float(inMax - inMin) * (outMax - outMin), 2)


def read_temp():
    sample = 0
    sample_count = 0
    global first_temp_check

    while sample_count <= 10:
        sample += chan_1.value
        sample_count += 1

    sample /= 10

    temp_a = sample
    temp_v = temp_a * .00005
    temp_c = round((temp_v * 220), 1)
    temp_f = round((temp_c * 1.8 + 32), 1)

    if first_temp_check is True:
        first_temp_check = False
        temp_c = temp_c / 1.75
        temp_f = temp_f / 1.45

    print(str(temp_c) + ' ' + str(temp_f))
    return temp_c, temp_f


def water_plant(time_to_water):
    if read_water_level() == 1:
        GPIO.setup(pump_pin, GPIO.LOW)
        time.sleep(time_to_water)
        GPIO.setup(pump_pin, GPIO.HIGH)
    else:
        send_error(3)


def read_humidity():
    avg_hydro = 0
    hydro_samples = 0
    while hydro_samples != 10:
        sensor_value = chan_0.value
        avg_hydro += sensor_value
        hydro_samples += 1
    avg_hydro = avg_hydro / 10
    # 22000 is dry (air) and 13000 is water
    avg_hydro = num_to_range(avg_hydro, 22000, 12000, 0, 100)
    print(avg_hydro)
    return avg_hydro


def get_data():
    get_hydration()
    get_temp()
    get_water_level()


def get_hydration():
    SendShortMessage(phone_number, 'Current moisture level - ' + str(read_humidity()) + '%')


def get_temp():
    temp_c, temp_f = read_temp()
    SendShortMessage(phone_number, 'Current temperature level - ' + str(temp_c) + 'C*, ' + str(temp_f) + 'F')


def get_water_level():
    if read_water_level() == 1:
        SendShortMessage(phone_number, 'There is currently enough water')
    elif read_water_level() == 0:
        SendShortMessage(phone_number, 'There is currently not enough water')


def schedule_watering():
    while True:
        # Read the current hydration and temperature levels from the sensors
        delay = 0
        hydration_level = read_humidity()

        if not os.path.exists('plant_type.txt'):
            print("No plant type specified, assuming medium plant type")
            set_plant_medium()
        file = open('plant_type.txt', 'r')
        plant_type = file.read()
        file.close()

        if not os.path.exists('pot_type.txt'):
            print("No pot type specified, assuming medium plant type")
            set_pot_small()
        file = open('pot_type.txt', 'r')
        pot_size = file.read()
        file.close()

        if plant_type == '':
            # SendShortMessage(phone_number, "No plant type specified, assuming medium plant type")
            set_plant_medium()
        if pot_size == '':
            # SendShortMessage(phone_number, "No pot size specified, assuming small pot size")
            set_pot_small()

        # Calculate the recommended delay based on the current plant type and temperature level
        if plant_type == "dry":
            if hydration_level < dry[0]:
                water_plant(4)  # 100 mk
            delay = max_delay
        elif plant_type == "medium":
            if hydration_level < medium[0] and pot_size == 'small':
                water_plant(4)  # 100 ml
                time.sleep(3600)  # Wait for the water to be drained by the soil
            elif hydration_level < medium[0] and pot_size == 'big':
                water_plant(6)  # 150 ml
                time.sleep(3600)
            delay = round((medium[1] - hydration_level) * 3600)  # 1 hour per 1% of missing hydration
        elif plant_type == "wet":
            if hydration_level < wet[0] and pot_size == 'small':
                water_plant(4)  # 100 ml
                time.sleep(3600)
            elif hydration_level < wet[0] and pot_size == 'big':
                water_plant(8)  # 200 ml
                time.sleep(3600)
            delay = round((wet[1] - hydration_level) * 1800)  # 30 minutes per 1% of missing hydration

        # Schedule the next watering function activation and return the recommended delay
        next_activation_time = time.time() + delay
        while time.time() <= next_activation_time:
            time.sleep(60)


def send_at(command, back, timeout):
    rec_buff = ''
    ser.write((command + '\r\n').encode())
    time.sleep(timeout)

    if ser.inWaiting():
        time.sleep(0.01)
        rec_buff = ser.read(ser.inWaiting())
    if rec_buff != '':
        print(rec_buff.decode())
        message = rec_buff.decode('utf-8').split('\r\n')[2]  # Split the SMS code into specific command
        if parse_command(message): print(rec_buff.decode), time.sleep(10),
        # if 'Raspi' in rec_buff.decode(): print(rec_buff.decode), time.sleep(3),
        if back not in rec_buff.decode(): print(command + ' back:\t' + rec_buff.decode())
        return 0
    else:
        # print(rec_buff)
        global TEXTDATA
        TEXTDATA = str(rec_buff)
        print(TEXTDATA)
        return 1


def ReceiveShortMessage():
    while True:
        if (eco_mode != True):
            rec_buff = ''
            # print('Setting SMS mode...')
            send_at('AT+CMGF=1', 'OK', 1)
            send_at('AT+CMGL="REC UNREAD"', 'OK', 1)
            answer = send_at('AT+CMGL="REC UNREAD"', '+CMTI', 1)

            if 1 == answer:
                answer = 0
            else:
                print('No New text')
        else:
            time.sleep(10)
            power_down_hat(power_key)


def SendShortMessage(phone_number, text_message):
    print("Setting SMS mode...")
    send_at("AT+CMGF=1", "OK", 1)  # Turn on SMS mode (set message format)
    print("Sending Short Message")
    answer = send_at("AT+CMGS=\"" + phone_number + "\"", ">",
                     2)  # CMGS is used to send an SMS message to a phone number
    if 1 == answer:
        ser.write(text_message.encode())
        ser.write(b'\x1A')
        answer = send_at('', 'OK', 20)
        if 1 == answer:
            print('send successfully')
        else:
            print('error')
    else:
        print('error%d' % answer)


def parse_command(command):
    i = 0
    if command == '':
        return 0
    else:
        # Only accepts correct syntax
        try:
            i = command_lut.index(command)
            print(command_lut[i])
            execute_function(i)
            return True
        except:
            send_error('Incorrect command syntax or non-existent command')
            return False

    ''' Allows incorrect syntax (only searches for keywords)
    for item in command_lut:
    if command_lut[i] in my_var:
        print(command_lut[i])
        break
    else:
        i+=1
    print('Incorrect command syntax or non-existent command')
    '''


def execute_function(func_number):
    if func_number == 0:
        eco_mode()
    if func_number == 1:
        water_plant(2)
    if func_number == 2:
        SendShortMessage(phone_number, "Quitting the program...")
        power_down_hat(power_key)
        if ser is not None:
            ser.close()
        GPIO.cleanup()
        quit()
    if func_number == 3:
        help()
    if func_number == 4:
        set_plant_dry()
    if func_number == 5:
        set_plant_medium()
    if func_number == 6:
        set_plant_wet()
    if func_number == 7:
        set_pot_small()
    if func_number == 8:
        set_pot_big()
    if func_number == 9:
        get_hydration()
    if func_number == 10:
        get_temp()
    if func_number == 11:
        get_water_level()
    if func_number == 12:
        get_data()
    if func_number == 13:
        SendShortMessage(phone_number, "I love you too!")


def help_me():
    SendShortMessage(phone_number, '''Here is a lit of all the commands : eco_mode - turns off all non-watering functions, 
    water_plant - manual watering ahead of schedule, exit - stops all functionality''')
    SendShortMessage(phone_number, '''help - prints list of commands, set_plant_[dry,medium,wet] - 
    sets plant type to dry/medium/wet, quit - kills program, get_[water_level/temp_hydration] - fetches sensor values''')
    SendShortMessage(phone_number, '''get_data - fetches all sensor values at once''')


def set_plant_dry():
    plant_type = 'dry'
    file = open('plant_type.txt', 'w')
    file.write(plant_type)
    file.close()
    SendShortMessage(phone_number, "Plant type set to dry")


def set_plant_medium():
    plant_type = 'medium'
    file = open('plant_type.txt', 'w')
    file.write(plant_type)
    file.close()
    SendShortMessage(phone_number, "Plant type set to medium")


def set_plant_wet():
    plant_type = 'wet'
    file = open('plant_type.txt', 'w')
    file.write(plant_type)
    file.close()
    SendShortMessage(phone_number, "Plant type set to wet")


def set_pot_small():
    pot_type = 'small'
    file = open('pot_type.txt', 'w')
    file.write(pot_type)
    file.close()
    SendShortMessage(phone_number, "Pot type set to small")


def set_pot_big():
    pot_type = 'big'
    file = open('pot_type.txt', 'w')
    file.write(pot_type)
    file.close()
    SendShortMessage(phone_number, "Pot type set to big")


def send_error(error_number):
    error_codes = {
        1: 'Incorrect command syntax or non-existent command',
        2: 'Failed to send data to ThingSpeak',
        3: 'Failed to water plants - not enough water'
    }
    print(error_codes.get(error_number))
    write_log(error_codes.get(error_number))
    if error_number == 1 or error_number == 3:
        SendShortMessage(phone_number, error_codes.get(error_number))


# ThingSpeak data transmission
def send_to_Thingspeak():
    try:
        while True:
            # Read temperature
            temp_c, temp_f = read_temp()
            # Read humidity
            humidity = read_humidity()
            # Read water level
            water_level = read_water_level()
            data = {
                "field1": water_level,
                "field2": humidity,
                "field3": temp_c,
                "field4": temp_f
            }
            response = requests.get(BASE_URL, params=data)
            if response.status_code != 200:
                print("Error - could not send data to ThingSpeak")
            else:
                print("Data transmission to ThingSpeak was successful")
                time.sleep(1800)
    except:
        send_error(2)


def write_log(text):
    file = open("error_log.txt", "a")
    file.write(text + ' ' + str(time.ctime()) + '\n')
    file.close()


def eco_mode():
    SendShortMessage(phone_number, "Eco mode activated")
    eco_mode = True


def power_on_hat(power_key):
    print('SIM7600X is starting:')
    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)
    GPIO.setup(power_key, GPIO.OUT)
    time.sleep(0.1)
    GPIO.output(power_key, GPIO.HIGH)
    time.sleep(2)
    GPIO.output(power_key, GPIO.LOW)
    time.sleep(20)
    ser.flushInput()
    print('SIM7600X is ready')


def power_down_hat(power_key):
    print('SIM7600X is loging off:')
    GPIO.output(power_key, GPIO.HIGH)
    time.sleep(3)
    GPIO.output(power_key, GPIO.LOW)
    time.sleep(18)
    print('Good bye')


try:
    # Configure the GPIO pin as an input pin
    GPIO.setup(water_pin, GPIO.IN)
    GPIO.setup(pump_pin, GPIO.OUT)
    GPIO.setup(pump_pin, GPIO.HIGH)

    power_on_hat(power_key)

    t1 = threading.Thread(target=ReceiveShortMessage)
    t2 = threading.Thread(target=schedule_watering)
    t3 = threading.Thread(target=send_to_Thingspeak)

    t1.start()
    t2.start()
    t3.start()
    while True:
        continue
except:
    if ser is not None:
        ser.close()
finally:
    power_down_hat(power_key)
    GPIO.cleanup()
