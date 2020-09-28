#!/usr/bin/env python
#
# m68k.py
#
# constants for musashi m68k CPU emulator
#

# cpu type
M68K_CPU_TYPE_INVALID = 0
M68K_CPU_TYPE_68000 = 1
M68K_CPU_TYPE_68010 = 2
M68K_CPU_TYPE_68EC020 = 3
M68K_CPU_TYPE_68020 = 4
M68K_CPU_TYPE_68030 = 5  # Supported by disassembler ONLY
M68K_CPU_TYPE_68040 = 6  # Supported by disassembler ONLY

# registers
M68K_REG_D0 = 0
M68K_REG_D1 = 1
M68K_REG_D2 = 2
M68K_REG_D3 = 3
M68K_REG_D4 = 4
M68K_REG_D5 = 5
M68K_REG_D6 = 6
M68K_REG_D7 = 7
M68K_REG_A0 = 8
M68K_REG_A1 = 9
M68K_REG_A2 = 10
M68K_REG_A3 = 11
M68K_REG_A4 = 12
M68K_REG_A5 = 13
M68K_REG_A6 = 14
M68K_REG_A7 = 15
M68K_REG_PC = 16  # Program Counter
M68K_REG_SR = 17  # Status Register
M68K_REG_SP = 18  # The current Stack Pointer (located in A7)
M68K_REG_USP = 19  # User Stack Pointer
M68K_REG_ISP = 20  # Interrupt Stack Pointer
M68K_REG_MSP = 21  # Master Stack Pointer
M68K_REG_SFC = 22  # Source Function Code
M68K_REG_DFC = 23  # Destination Function Code
M68K_REG_VBR = 24  # Vector Base Register
M68K_REG_CACR = 25  # Cache Control Register
M68K_REG_CAAR = 26  # Cache Address Register

M68K_REG_PREF_ADDR = 27  # Virtual Reg: Last prefetch address
M68K_REG_PREF_DATA = 28  # Virtual Reg: Last prefetch data

M68K_REG_PPC = 29  # Previous value in the program counter
M68K_REG_IR = 30  # Instruction register
M68K_REG_CPU_TYPE = 31  # Type of CPU being run

# aline callback
M68K_ALINE_NONE = 0
M68K_ALINE_EXCEPT = 1
M68K_ALINE_RTS = 2

# traps
TRAP_DEFAULT = 0
TRAP_ONE_SHOT = 1
TRAP_AUTO_RTS = 2
