I have setup where my main controller is a RPi pico which controlls sevreal processes. and uses the default USB CDC serial as the logger so as to be able to see the logs when connected to any laptop over USB serial. I want to be able to remotely monitor the logs form the system. with ability to store the logs for the individual runs and separate them by run and time and days etc.

I have attached a rpi zero 2W to the picos usb interface. So i am trying to develop a python script for the Zero whcih 
can do connection, reconneciton on disconnect, read the serial and save them files etc, connect to the remote server and save the files in chunks, eventually needs to send the stored log files over to the server using requestes

Programming - Arduino Default programming method for rpi PICO (uploads code in the bootloader mode with the UF2 file)
Microcontroller - Rpi PICO
Microprocessor - Rpi Zero 2W (connects to pico over the USB serial)
Software stack for PICO
Arduino based CPP programming
Adafruit tiny USB library for the USB CDC functionality
Flask App with python -> bootstrap with jinja templates

Handshake Between PICO and Zero
1. Zero Send ::RPI-ZERO-LOG::READY to the pico after the boot, as it takes a lot of time for the zero 2W to boot
2. Pico send ::RPI-PICO-LOG::START after receiving the ready from the Zero marking the start of a new session. (PICO Waits for 15Sec before suspending the Logging and continuing with the normal operation)

Log file Creation
1. At the boot when the handshake marker is received from the pico, the zero creates a new log file
2. All subsequence marker ::RPI-PICO-LOG::START will create a new log file with incremented session number
3. Ideally at the boot of the zero we will receive the first marker from the pico (it should not be received after the boot)