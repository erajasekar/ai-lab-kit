# ====================================================================
# DISCLAIMER:
# This code is provided as-is for educational and experimental 
# purposes only. The author makes no representations or warranties of 
# any kind concerning the safety, suitability, or accuracy of this 
# code. Use at your own risk. The author assumes no liability for any 
# damages, system failures, security breaches, or network issues 
# resulting from the use or implementation of this script.
# ====================================================================
 
from fusion_hat.pwm import PWM
from fusion_hat.stt import STT
import threading
from queue import Queue
from time import sleep
from fusion_hat.tts import Piper
tts = Piper()
tts.set_model('en_US-kristin-medium')
msg = 'Speak your favorite color, and your wish is my command'
tts.say(msg,stream=False)

redPin = 0
greenPin = 1
bluePin = 2

redLED= PWM(redPin)
greenLED=PWM(greenPin)
blueLED=PWM(bluePin)

rVal=0
gVal=0
bVal=0

stt = STT('en-us')
running=True
colorQ = Queue()

def getColor():
    print("Input Thread is Running")
    global running
    while running:
        print('What color: red, green, blue, cyan, magenta, yellow, off, quit')
        myColor = stt.listen(stream=False)
        myColor=myColor.strip()
        if myColor == 'quit':
            running = False
            msg = 'So Sorry to See you go, Please Call Me Again Soon'
            tts.say(msg, stream=False)
            break
        colorQ.put(myColor)
    print("Thread is Terminated")
colorThread= threading.Thread(target=getColor,daemon=True)
colorThread.start()
print("Main Program is Started")
try:
    while running:
        if colorQ.empty() == False:
            myColor = colorQ.get()
            print('Color: ',myColor)
            if myColor == 'off':
                rVal = 0
                gVal = 0
                bVal = 0
                msg = 'Please bring back your beautiful colors!'
                tts.say(msg, stream=False)
            if myColor == 'red' or myColor=='read':
                rVal = 100
                gVal = 0
                bVal = 0
                msg = 'I can not get you out of my head, so I will turn it red'
                tts.say(msg, stream=False)
            if myColor == 'green':
                rVal = 0
                gVal = 100
                bVal = 0
                msg = 'Because I want you to be seen, I will turn it green'
                tts.say(msg, stream=False)
            if myColor == 'blue':
                rVal = 0
                gVal = 0
                bVal = 100
                msg = 'Because I love you, I will turn it blue'
                tts.say(msg, stream=False)
            if myColor == 'cyan':
                rVal = 0
                gVal = 100
                bVal = 25
                msg = 'You turn my world cyan and bright, what a beautiful sight!'
                tts.say(msg, stream=False)
            if myColor == 'magenta':
                rVal = 100
                gVal = 0
                bVal = 100
                msg = 'You Light my Magenta Fire, You are my burning Desire'
                tts.say(msg, stream=False)
            if myColor == 'yellow':
                rVal = 100
                gVal = 25
                bVal = 0
                msg = 'Yes, I will turn it yellow'
                tts.say(msg, stream=False)          
            myColor = 'null'
            redLED.pulse_width_percent(rVal)
            greenLED.pulse_width_percent(gVal)
            blueLED.pulse_width_percent(bVal)
    redLED.pulse_width_percent(0)
    greenLED.pulse_width_percent(0)
    blueLED.pulse_width_percent(0)
    redLED.enable(False)
    greenLED.enable(False)
    blueLED.enable(False)
    print("LEDs are Released")
    print("Program is Terminated")            
         
except KeyboardInterrupt:
    running = False
    redLED.pulse_width_percent(0)
    greenLED.pulse_width_percent(0)
    blueLED.pulse_width_percent(0)
    redLED.enable(False)
    greenLED.enable(False)
    blueLED.enable(False)
    print("LEDs are Released")
    print("Program is Terminated")