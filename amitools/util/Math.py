# various Amiga Math utils

import struct
import math


def int32(x):
    st = struct.pack("I", x)
    return struct.unpack("i", st)[0]


def int16(x):
    st = struct.pack("H", x)
    return struct.unpack("h", st)[0]


def int8(x):
    st = struct.pack("B", x)
    return struct.unpack("b", st)[0]


def signext16(x):
    # extend sign bit of 16 bit value to 32 bit
    if x & 0x8000 == 0x8000:
        return 0xFFFF0000 | x
    else:
        return x


def double_to_regs(number):
    """convert Python double to (hi, lo) reg pair"""
    st = struct.pack(">d", number)
    return struct.unpack(">LL", st)


def regs_to_double(hi, lo):
    """convert (hi, lo) Amiga reg pair to double"""
    st = struct.pack(">LL", hi, lo)
    return struct.unpack(">d", st)[0]


def float_to_reg(number):
    """convert Python float to reg value"""
    try:
        st = struct.pack(">f", number)
    except OverflowError:
        if number > 0.0:
            number = float("inf")
        else:
            number = float("-inf")
        st = struct.pack(">f", number)
    return struct.unpack(">L", st)[0]


def reg_to_float(reg):
    """convert reg value to Python float"""
    st = struct.pack(">L", reg)
    return struct.unpack(">f", st)[0]


# Motorola FFP
#
# 32 bit:
# 31       23       15       7      0
# MMMMMMMM MMMMMMMM MMMMMMMM SEEEEEEE
#
# - leading one in mantissa visible (one bit less accuracy)
# - 7bit exponent in excess-64 notation
#
# Single IEEE:
# SEEEEEEE EMMMMMMM MMMMMMMM MMMMMMMM
#
# - leading one is omitted
# - 8bit exponent in excess-128 notation


def float_to_ffp_reg(number):
    """convert Python number to ffp register"""
    # zero
    if number == 0.0:
        return 0
    # nan -> zero
    if math.isnan(number):
        return 0
    # inf -> largest value
    if math.isinf(number):
        if number < 0.0:
            return 0xFFFFFFFF
        else:
            return 0xFFFFFF7F
    # convert float to 32bit num
    b = struct.pack(">f", number)
    i = struct.unpack(">L", b)[0]
    # extract sign bit
    sign = b[0] & 0x80
    # extract 8 bit exponent
    exp = (i >> 23) & 0xFF
    # too small?
    if exp <= 0x3E:
        return 0
    # too large?
    elif exp >= 0xBD:
        exp = 0x7F
        mantissa = 0xFFFFFF00
    # convert
    else:
        exp -= 0x3E
        # mantissa (add leading one)
        mantissa = (i << 8) & 0x7FFFFF00
        mantissa |= 0x80000000
    # resulting ffp
    ffp = mantissa | sign | exp
    return ffp


def ffp_reg_to_float(ffp):
    """convert ffp register to Python float"""
    # zero
    if ffp == 0:
        return 0.0
    # get sign bit
    sign = ffp & 0x80
    # get exponent: 0 .. 127 and shift to 8 bit range
    exp = ffp & 0x7F
    exp += 0x3E
    # shift mantissa (skip leading one of ffp format)
    mantissa = ffp >> 8
    mantissa &= 0x007FFFFF
    flt = sign << 24 | exp << 23 | mantissa
    res = struct.unpack(">f", struct.pack(">L", flt))[0]
    return res


# Amiga constants

Amiga_INT_MAX = 2147483647
Amiga_INT_MIN = -2147483648

Amiga_DBL_POS_MAX = regs_to_double(0x7FEFFFFF, 0xFFFFFFFF)
Amiga_DBL_NEG_MAX = regs_to_double(0xFFEFFFFF, 0xFFFFFFFF)
Amiga_DBL_NAN1 = regs_to_double(0x7FF10000, 0x00000000)

Amiga_FLT_POS_MAX = reg_to_float(0x7F7FFFFF)
Amiga_FLT_NEG_MAX = reg_to_float(0xFF7FFFFF)
