#! /usr/local/bin/python3
'''
ktry
A toy program to try to decipher Elecraft KX3 memories.
- Originally reads from "commands" file in same directory, which included
    selected data from the Elecraft Memory Windoze program.
- Eventually made it to using and parsing NamedTuples. Unfortunately,
    these never made it into the CHIRP driver, because they're immutable!

Plans include parsing the status bytes (xvtr and band)
Plans also include reading directly from radio via USB, but that requires
    live connection to radio, which prohibits playing with data offline.

2025-08-09
@Copyright 2024-2025 by Declan Rieb, WD5EQY@ARRL.net
'''

import string
from struct import pack, unpack, calcsize
from typing import NamedTuple

MEMSTART = 0x0C00
MEMSIZE = 0x40
BNDSTART = 0x0100
BNDSIZE = 0x10
XVTRSTART = 0x02A2
XVTRSIZE = 0x0A

VALID_CHARS = ' ' + string.ascii_uppercase + string.digits + '*+/@_'
RADIO_CHARS = "\x00\x01\x02\x03\x04\x05\x06\x07\x08\x09\x0a\x0b\x0c\x0d\x0e\x0f" \
              "\x10\x11\x12\x13\x14\x15\x16\x17\x18\x19\x1a\x1b\x1c\x1d\x1e\x1f" \
              "\x20\x21\x22\x23\x24\x25\x26\x27\x28\x29"
my_valids = str.maketrans(RADIO_CHARS, VALID_CHARS, "\xFF")
MODES = ['CW', 'USB', 'LSB', 'Data', 'AM', 'FM']
SUB_MODES = ['DATA-A', 'AFSK-A', 'FSK-D', 'PSK-D']
# Following file contains dialog corresponding to "read status"
FILENAME = 'commands_status'
# Following file contains results of partial radio memory reads
# FILENAME = 'commands'

class ElecraftMemory(NamedTuple):
    """ Elecraft regular  memory message format
        (unpacked from 0x40 bytes, which includes the ER/EW command """
    # opcode: bytes  # two bytes  But it's not stored in the radio
    address: int
    length: int
    rvfoa: bytes
    rvfob: bytes
    modes: bytes    # modeb and modea in one byte
    dmode: bytes    # digital submode, speed and ¿bits?
    f2: bytes
    f3: bytes
    f4: bytes
    band: bytes     # xvrtr bit and band index
    subtone: bytes
    offset: bytes   # repeater offset in 20kHz increments (0-5000kHz)
    repflag: bytes
    f9: bytes
    fa: bytes
    fb: bytes
    fc: bytes
    fd: bytes
    rlabel: bytes
    comment: bytes
    cksum: int

class ElecraftCommand(NamedTuple):
    """ Elecraft regular command message format
        (unpacked from 0x40 bytes, which includes the ER/EW command """
    #  opcode: bytes  # two bytes  But it's not stored in the radio
    address: int
    length: int
    cksum: int

""" Magic for decoding the radio's responses are in FMT here:
    Assumes 68 characters, converted from text hex string of 136 chars
    These will be decoded into the ElecraftMem NamedTuple above
    >   Big-endian
    H   unsigned short (2 bytes):  address
    B   Unsigned char-sized integer: length
    5s  string, freq spec (two, one per VFO)
    B   unsigned char-sized integer: Modes
    13B for other flags
    x   5 ignored
    5s  string, label (in vc format)
    24s string, comment field (in ascii)
    i   4-byte signed integer for checksum
"""
FMT3 = '8B8x5s24s'
FMT0 = '>H'
FMT1 = 'B'
FMT2 = '5s5s6B'
FMTn = 'b'
FMTo = 'i'

band_state = [bytes(16) for _ in range(25)]
xvtr_state = [bytes(10) for _ in range(9)]

def parse_VFO(byt : bytes) -> int:
    MHz = byt[0]
    tkH = byt[1]
    hHz = byt[2]
    tHz = byt[3]
    Hz  = byt[4]
    VFO = Hz + 10*tHz + 100*hHz + 10000*tkH + 1000000*MHz
    if MHz == 0xFF and tkH == 0xFF and hHz == 0xFF and Hz == 0xFF:
        VFO = 0
    return VFO


def parse_memslot(n : int, byt : bytearray):
    if n < len(byt):
        return 0, n, len(byt), 0, '', '', ''
    modes = int(byt[11])
    # VFO A
    VFOA, sfreqA = parse_VFO(byt[:6])
    modeA = modes & 0x0F
    if modeA <= len(MODES):
        modeA = MODES[modes & 0x0F]
    else:
        modeA = ''
    # VFO b
    VFOB, sfreqB = parse_VFO(byt[6:])
    modeB = (modes & 0xF0) >> 4
    if modeB <= len(MODES):
        modeB = MODES[modeB]
    else:
        modeB = ''
    submode = (int(byt[13]) ^ 0xF0) >> 4
    if submode < len(SUB_MODES) and (modeA == 'Data' or modeB == 'Data'):
        submode = SUB_MODES[submode]
    else:
        submode = ''
    return VFOA, sfreqA, modeA, VFOB, sfreqB, modeB, submode


print("\n\n\n"
      "-----------------------------------------------------------------\n"
      "-----------------------------------------------------------------\n"
      )
with open(FILENAME, "r") as f:
    a = ' '
    print("OP    Mem  Label Freq A   mode  Freq B     mode Submode\n")
    while a != '':
        a = f.readline().rstrip()
        n = len(a)
        # data too short to even try
        if n <= 3 or a[0] == '#':
            continue
        b = bytes.fromhex(a[2:-1])
        c = len(b)
        slabl = ''
        address = unpack(FMT0, b[:2])[0]
        if address >= MEMSTART:
            memnum = int((address - MEMSTART) / MEMSIZE)
            FMT = FMT0 + FMT1 + FMT2 + FMT3 + FMTn
            MEM = ElecraftMemory
        elif BNDSTART <= address <= MEMSTART:
            # Here starts status reads
            lenstat = 10
            if address >= 0x2a2:
                # Transverter state
                # if using long reads, the state MAY be split between reads
                memnum = (address - 0x2a2) // lenstat
                nstats = (c - 4) // lenstat
                for i in range(nstats):
                    bstart = 3 + i * lenstat
                    bs = b[bstart: bstart + lenstat]
                    xvtr_state[memnum + i] = bs
                    print(f'XVTR State[{memnum + i}]="{bs.hex()}"'
                         )
                continue
            else:
                lenstat = 0x10   
                memnum = (address - BNDSTART) // BNDSIZE
                nstats = (c - 4) // lenstat
                if nstats <= 0:
                    # This is a command or broken; ignore it
                    continue
                # This contains state data
                for i in range(nstats):
                    bstart = 3 + i * lenstat
                    bs = b[bstart: bstart + lenstat]
                    band_state[memnum + i] = bs
                    # print(f'{memnum + i:2d}={band_state[memnum+i].hex()}')
                    l = parse_VFO(bs[:5])
                    lfreq = f'{l // 1000000:2d}.{l % 1000000:<6d}'
                    h = parse_VFO(bs[5:10])
                    hfreq = f'{h // 1000000:2d}.{h % 1000000:<6d}'
                    print(f'Band[{memnum + i + 1:2d}]: '
                          f'VFO A={lfreq}, VFO B={hfreq}.'
                          f'\tstate="{bs[10:].hex()}"'
                         )
                continue
        if n == 11:
            FMT = FMT0 + FMT1 + FMTn
            MEM = ElecraftCommand
        c = calcsize(FMT)
        y = MEM(*unpack(FMT, b[:min(n, c)]))
        byt = bytearray.fromhex(a[2:-1])
        opcode = a[:2]
        chksum = y.cksum
        if opcode == "ER":
            operation = "Read"
        elif opcode == "EW":
            operation = "Writ"
        else:
            operation = "Othr"
        add = ((int(sum(byt)) - 1) ^ 0xff) & 0xff
        if add != 0:
            print("Checksum bad. %x should be zero." % add)
            continue
        if n <= 11:
            # Response message from radio is short (no data)
            continue
        elif memnum < 0:
        # "Normal" and "Transverter" memories are different
        # 16 bytes per entry; three reads of 0x40, 0x40 and 0x1A.
        # TODO: decipher special memories.
            print("Normal/Transverter memories follow:\n"
                  "Op=%s, Address=%4x\n%s" % (operation, address, byt))
            slabl = ''
            for i in range(4, len(byt), 16):
                VFOA, sfreqA, modeA, VFOB, sfreqB, modeB, submode =\
                    parse_memslot(16, byt[i:])    
                print("%4s  %3d.%d  %5s %8s %4s  %8s %4s %6s" % (
                      operation, memnum, i, slabl, sfreqA, modeA,
                      sfreqB, modeB, submode))
            continue
        elif n == 139:
            if address >= MEMSTART:
                # label = (bytes.fromhex(a[72:82].rstrip('\x00')))
                label = y.rlabel
                slabl = ''
                for i in range(0,5):
                    if label[i] < len(VALID_CHARS):
                        slabl += VALID_CHARS[label[i]]
                    else:
                        slabl += " "
            # VFOA, sfreqA, modeA, VFOB, sfreqB, modeB, submode =\
            #     parse_memslot(n, byt[2:-1])
            VFOA = y.rvfoa
            sfreqA = parse_VFO(VFOA)
            VFOB = y.rvfob
            sfreqB = parse_VFO(VFOB)
            modea = y.modes & 0x0f
            modeA = MODES[modea] if modea < len(MODES) else ' '
            modeb = (y.modes & 0xf0) >> 4
            modeB = MODES[modeb] if modeb < len(MODES) else ' '
            submode = y.dmode
#            if modeA == 'Data' or modeB == 'Data':
#                print("Submode '%s'" % submode)
            print("%4s  %3d  %5s %8s %4s  %8s %4s %6s" % (
               operation, memnum, slabl, sfreqA, modeA, sfreqB, modeB, submode))
