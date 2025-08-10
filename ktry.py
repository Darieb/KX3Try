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

class ElecraftSpecial(NamedTuple):
    """ Elecraft special memory message format
        (unpacked from 0x40 bytes, which includes the ER/EW command """
    #  opcode: bytes  # two bytes  But it's not stored in the radio
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
    rvfoa1: bytes
    rvfob1: bytes
    modes1: bytes    # modeb and modea in one byte
    dmode1: bytes    # digital submode, speed and ¿bits?
    f21: bytes
    f31: bytes
    f41: bytes
    band1: bytes     # xvrtr bit and band index
    rvfoa2: bytes
    rvfob2: bytes
    modes2: bytes    # modeb and modea in one byte
    dmode2: bytes    # digital submode, speed and ¿bits?
    f22: bytes
    f32: bytes
    f42: bytes
    band2: bytes     # xvrtr bit and band index
    rvfoa3: bytes
    rvfob3: bytes
    modes3: bytes    # modeb and modea in one byte
    dmode3: bytes    # digital submode, speed and ¿bits?
    f23: bytes
    f33: bytes
    f43: bytes
    band3: bytes     # xvrtr bit and band index
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

def parse_VFO(byt : bytearray) -> int:
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
with open("commands", "r") as f:
    a = ' '
    print("OP    Mem  Label Freq A   mode  Freq B     mode Submode\n")
    while a != '':
        a = f.readline().rstrip()
        n = len(a)
        # data too short to even try
        if n <= 3:
            break
        b = bytes.fromhex(a[2:-1])
        c = len(b)
        address = unpack(FMT0, b[:2])[0]
        if address >= MEMSTART:
            memnum = int((address - MEMSTART) / MEMSIZE)
            FMT = FMT0 + FMT1 + FMT2 + FMT3 + FMTn
            MEM = ElecraftMemory
        elif BNDSTART <= address <= MEMSTART:
            memnum = int((address - BNDSTART) / BNDSIZE)
            FMT = FMT0 + FMT1 + FMT2 + FMT2 + FMT2 + FMT2 + FMTn
            MEM = ElecraftSpecial
            print(f"\nSpecial {memnum} {address:04x} {FMT} {c} {calcsize(FMT)}")
            print(a,"\n",b)
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
