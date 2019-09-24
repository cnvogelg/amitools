import struct


class RomAccess:
    def __init__(self, rom_data):
        self.rom_data = rom_data
        if type(rom_data) is bytes:
            self.writable = False
        elif type(rom_data) is bytearray:
            self.writable = True
        else:
            raise ValueError("rom_data must be bytes or bytearray")
        self.size = len(rom_data)
        self.kib = self.size // 1024

    def get_size(self):
        return self.size

    def get_size_kib(self):
        return self.kib

    def is_writable(self):
        return self.writable

    def get_data(self):
        return self.rom_data

    def make_writable(self):
        if not self.writable:
            self.writable = True
            self.rom_data = bytearray(self.rom_data)
        return self.rom_data

    def read_long(self, off):
        return struct.unpack_from(">I", self.rom_data, off)[0]

    def write_long(self, off, val):
        if not self.writable:
            raise ValueError("can't write to ROM")
        return struct.pack_into(">I", self.rom_data, off, val)

    def read_word(self, off):
        return struct.unpack_from(">H", self.rom_data, off)[0]

    def write_word(self, off, val):
        if not self.writable:
            raise ValueError("can't write to ROM")
        return struct.pack_into(">H", self.rom_data, off, val)

    def read_byte(self, off):
        return struct.unpack_from("B", self.rom_data, off)[0]

    def read_sbyte(self, off):
        return struct.unpack_from("b", self.rom_data, off)[0]
