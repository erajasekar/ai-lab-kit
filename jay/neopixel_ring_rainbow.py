# ====================================================================
# DISCLAIMER:
# This code is provided as-is for educational and experimental 
# purposes only. The author makes no representations or warranties of 
# any kind concerning the safety, suitability, or accuracy of this 
# code. Use at your own risk. The author assumes no liability for any 
# damages, system failures, security breaches, or network issues 
# resulting from the use or implementation of this script.
# ====================================================================
 
import time
import board
import neopixel_spi as neopixel
import colorsys
spi = board.SPI()
LC = 12
PO = neopixel.GRB
strip = neopixel.NeoPixel_SPI(spi,
            LC,pixel_order=PO,
            auto_write=False)
strip.fill(0)
strip.show()
def hsv2rgb(h):
    r, g, b = colorsys.hsv_to_rgb(h,1,1)
    return ( int(255*r), int(255*g),int(255*b))
ts=1
ts2=.1
ts3=.05
try:
    for i in range(12):
        hue = i/12
        color = hsv2rgb(hue)
        strip[i] = color
    strip.show()
    time.sleep(ts)
    for lap in range(70):
        startColor = strip[0]
        for i in range(11):
            strip[i]= strip[i+1]
        strip[11] = startColor
        time.sleep(ts2)
        strip.show()
    offset = 0
    while True:
        for i in range(12):
            hue = (i/12 + offset)%1
            strip[i] = hsv2rgb(hue)
        strip.show()
        offset = (offset + 1/100)%1
        time.sleep(ts3)
    
except KeyboardInterrupt:
    strip.fill(0)
    strip.show()
    print("That's All Folks!")