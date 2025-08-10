#! /usr/local/bin/python3.11
'''
ktry
A toy program to try to decipher Elecraft KX3 memories.
presently set to build a bytearray structure of the whole memory (that I
know about, Should be useful for CHIRP to parse

2025-08-09
@Copyright 2024-2025 by Declan Rieb, WD5EQY@ARRL.net
'''

import string
import serial

MEMSTART = 0x0000
MEMSIZE = 0x40
MEMSIZEs = '\x40'
MEMSTOP = 0x3E00

VALID_CHARS = ' ' + string.ascii_uppercase + string.digits + '*+/@_'
# make byte-translation tables between 'ascii' and KX-characters
A2KX = bytes.maketrans(VALID_CHARS.encode('cp1252').ljust(256, b'.'),
                       bytes(range(256)))
KX2A = bytes.maketrans(bytes(range(256)),
                       VALID_CHARS.encode('cp1252').ljust(256, b'.'))

MODES = ['CW', 'USB', 'LSB', 'Data', 'AM', 'FM']
SUB_MODES = ['DATA-A', 'AFSK-A', 'FSK-D', 'PSK-D']

def command(text:str) -> str:
   """
   command() sends the text (command) on port, and reads data until a ";"
    is returned. No error checking here.
    Returns the data as a string.
   """
    port.write((text + ';').encode('cp1252'))
    line = ""
    while not line.endswith(';'):
        line += port.read(150).decode('cp1252')
    return line

def checksum(hex : str) -> int:
    b = bytes.fromhex(hex)[:-1]
    return (((sum(b) - 1) & 0xff) ^ 0xff)

memline = bytearray(MEMSIZE)
memory = [memline for i in range(MEMSTART, MEMSTOP, MEMSIZE)]

port = serial.Serial(
    port = '/dev/cu.usbserial-AD02DTZG',
    baudrate = 38400,
    timeout = 0.1,
    )

# wake up the radio
command('AI')
command('ID')

for addr in range(MEMSTART, MEMSTOP, MEMSIZE):
    data = f'{addr:04x}{MEMSIZE:02x}'
    # append a fake extra byte for checksum
    csum = checksum(data + '00')
    cmd = 'ER' + data + f'{csum:2x}'

    print(f'{addr:04x} {data}, {csum:2x}, "{cmd}"')


    # Send read command, line is returned
    line = command(cmd)
    index = (addr - MEMSTART) // MEMSIZE
    memory[index] = bytes.fromhex(line[8:-3])
    print(memory[index])
