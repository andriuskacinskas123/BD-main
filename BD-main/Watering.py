import time
import board
import serial
import threading
import adafruit_dht
import RPi.GPIO as GPIO
import requests

GPIO.setwarnings(False)  # Disable warnings from GPIO
GPIO.setmode(GPIO.BCM)

ser = serial.Serial("/dev/ttyS0", 115200)
ser.flushInput()

phone_number = '+37062920303'  # ********** change it to the phone number you want to text
text_message = ''
power_key = 6
rec_buff = ''

eco_mode = False

# Define pins
water_pin = 14
pump_pin = 22
humidity_pin = 8
temp_pin = 4

# Define the hydration and temperature threshholds for the different plant types
plant_type = ''
dry = [10, 40]
medium = [40, 70]
wet = [70, 100]

# Define the minimum the and maximum delay between watering function activations
min_delay = 1800  # 30 minutes
max_delay = 86400  # 24 hours

# ThingSpeak API parameters
WRITE_API_KEY = "3F0UCN02XP8HTKQP"
BASE_URL = "https://api.thingspeak.com/update?api_key={3F0UCN02XP8HTKQP}"

command_lut = ['eco_mode', 'send_water', 'quit', 'help', 'set_plant_dry', 'set_plant_medium', 'set_plant_wet']


def read_water_level():
    # Configure the GPIO pin as an input pin
    GPIO.setup(water_pin, GPIO.IN)
    # Read the water level from the sensor
    if GPIO.input(water_pin) == GPIO.HIGH:
        water_level = 1
    else:
        water_level = 0
    return water_level


def convert_to_temperature(raw_value):
    voltage = raw_value * 3.3 / 65535  # Convert the raw value to voltage (0-3.3V)
    temperature_c = (voltage - 0.5) * 100  # Convert the voltage to temperature in Celsius
    return temperature_c


def read_temp():
    # Read the raw data
    # raw_value = channel.value
    # Convert the raw value to temperature in Clesius
    # temperature_c = convert_to_temperature(raw_value)
    # Print the value
    # print(f"Temperature: {temperature_c:.2f} C")
    return 0


def water_plant():
    if read_water_level() == 1:
        GPIO.output(pump_pin, GPIO.HIGH)
        time.sleep(5)
        GPIO.output(pump_pin, GPIO.LOW)
    else:
        send_error(3)


def read_humidity():
    return 0


def schedule_watering():
    # Read the current hydration and temperature levels from the sensors
    hydration_level = read_humidity()
    temperature_level = read_temp()
    # Convert to Celsius
    temperature_level = convert_to_temperature(temperature_level)

    file = open('plant_type.txt', 'r')
    plant_type = file.read()
    file.close()
    if plant_type == '':
        SendShortMessage(phone_number, "No plant type specified, assuming medium plant type")
        set_plant_medium()

    # Calculate the recommended delay based on the current plant type and temperature level
    if plant_type == "dry":
        delay = max(min_delay, (dry[1] - hydration_level) * 600)  # 10 minutes per 1% of missing hydration
    elif plant_type == "medium":
        delay = max(min_delay, (medium[1] - hydration_level) * 600)  # 10 minutes per 1% of missing hydration
    elif plant_type == "wet":
        delay = max(min_delay, (wet[1] - hydration_level) * 600)  # 10 minutes per 1% of missing hydration
    else:
        delay = max_delay

    if temperature_level >= 30:
        delay //= 2  # Divide delay by 2 if temperature is above 30 degrees Celsius

    water_plant()

    # Schedule the next watering function activation and return the recommended delay
    next_activation_time = time.monotonic() + delay
    if time.monotonic() <= next_activation_time:
        time.sleep(0.1)
    schedule_watering()


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
        if parse_command(message): print(rec_buff.decode), time.sleep(3),
        #if 'Raspi' in rec_buff.decode(): print(rec_buff.decode), time.sleep(3),
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
            if 'red' in rec_buff:
                answer = 1
                print('Turning LEDS onto RED')
            else:
                print('No New text')
                return False
            return True
        else:
            time.sleep(10)
            power_down_hat(power_key)
            break


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
        water_plant()
    if func_number == 2:
        SendShortMessage(phone_number, "Quitting the program...")
        power_down_hat(power_key)
        if ser != None:
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


def help():
    SendShortMessage(phone_number, '''Here is a lit of all the commands : eco_mode - turns off all non-watering functions, water_plant - manual watering 
                     ahead of schedule, exit - stops all functionality''')
    SendShortMessage(phone_number,
                     'help - prints list of commands, set_plant_[dry,medium,wet] - sets plant type to dry/medium/wet, quit - kills program')


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


def send_error(error_number):
    error_codes = {
        1: 'Incorrect command syntax or non-existent command',
        2: 'Failed to send data to ThingSpeak',
        3: 'Failed to water plants - not enough water'
    }
    print(error_codes.get(error_number))
    write_log(error_codes.get(error_number) + time.ctime())
    if error_number == 1 or error_number == 3:
        SendShortMessage(phone_number, error_codes.get(error_number))


# ThingSpeak data transmission
def send_to_Thingspeak():
    try:
        # Read temperature
        temperature_c = read_temp()
        temperature_c = convert_to_temperature(temperature_c)
        # Read humidity
        humidity = read_humidity()
        # Read water level
        water_level = read_water_level()
        data = {
            "field1": temperature_c,
            "field2": humidity,
            "field3": water_level
        }
        response = requests.get(BASE_URL, params=data)
        if response.status_code != 200:
            print("Error - could not send data to ThingSpeak")
        else:
            print("Data transmission to ThingSpeak was successful")
            time.sleep(3600)
    except:
        send_error(2)


def write_log(text):
    file = open("error_log.txt", "a")
    file.write(text)
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
    if ser != None:
        ser.close()
    GPIO.cleanup()
