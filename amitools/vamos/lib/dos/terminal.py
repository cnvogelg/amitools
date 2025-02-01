try:
    import termios
except ImportError:
    termios = None

try:
    import select
except ImportError:
    select = None

import io

ESC = b"\x1b"
ESC_CODE = 0x1B
CSI = b"\x9b"
BRACKET = b"\x5b"
CSI_ESC_SEQ = b"\x1b\x5b"


class CsiEscConverter:
    def convert(self, buffer):
        return buffer.replace(CSI, CSI_ESC_SEQ)


class EscCsiConverter:
    def __init__(self, obj, esc_next_timeout=0.2):
        self.obj = obj
        self.esc_next_timeout = esc_next_timeout
        try:
            self.fd = obj.fileno()
        except io.UnsupportedOperation:
            self.fd = None
        self.next_ch = None

    def read(self, size):
        assert size > 0

        # if a character from last read is available
        if self.next_ch is not None:
            next_ch = self.next_ch
            self.next_ch = None

            # only a single char read? return it
            if size == 1:
                return next_ch

            left = size - 1
        else:
            next_ch = b""
            left = size

        # now read in 'left' bytes
        try:
            read_data = self.obj.read1(left)
        except IOError:
            # Error
            return -1
        if len(read_data) == 0:
            # EOF
            return next_ch

        # add extra char to include in conversion
        if next_ch:
            read_data = next_ch + read_data

        # convert ESC -> CSI
        data = self._convert(read_data)

        # check if last char is ESC
        last_ch = data[-1]
        if last_ch != ESC_CODE:
            # No ESC -> we are done
            return data

        # we need another char to decide if '[' follows ESC
        # if we have select we wait for it a bit
        # otherwise we simply read with possibly blocking
        if select and self.fd is not None:
            rx, _, _ = select.select([self.fd], [], [], self.esc_next_timeout)
            if self.fd not in rx:
                # no char arrived. assume isolated ESC in data and return
                return data

        # read next char
        try:
            next_ch = self.obj.read1(1)
        except IOError:
            # Error
            return -1
        if len(read_data) == 0:
            # EOF
            return data

        # if we got the '[' then last data byte is also a CSI
        if next_ch == BRACKET:
            return data[:-1] + CSI

        # keep char for next read
        self.next_ch = next_ch
        return data

    def _convert(self, buffer):
        return buffer.replace(CSI_ESC_SEQ, CSI)


class Terminal:
    def __init__(self, obj, out_csi_conv=True, in_esc_conv=True):
        self.fd = obj.fileno()
        self.obj = obj

        # have termios on this platform
        if termios:
            self.tty_state = termios.tcgetattr(self.fd)

        # do CSI -> ESC '[' conversion on output
        if out_csi_conv:
            self.out_conv = CsiEscConverter()
        else:
            self.out_conv = None

        # do ESC '[' to CSI conversion
        if in_esc_conv:
            self.in_conv = EscCsiConverter(self.obj)
        else:
            self.in_conv = None

    def close(self):
        if termios:
            termios.tcsetattr(self.fd, termios.TCSAFLUSH, self.tty_state)

    def set_mode(self, cooked):
        # [iflag, oflag, cflag, lflag, ispeed, ospeed, cc]
        #  0      1      2      3
        if termios:
            state = termios.tcgetattr(self.fd)

            # input modes
            # ICRNL: do not convert CR to NL on input for raw
            flags = termios.ICRNL
            if cooked:
                state[0] |= flags
            else:
                state[0] &= ~flags

            # local modes: ECHO/ICANON/IEXTEN
            # ECHO: no local echo
            # ICANON/IEXTEN: no line-wise editing
            flags = termios.ECHO | termios.ICANON | termios.IEXTEN
            if cooked:
                state[3] |= flags
            else:
                state[3] &= ~flags

            termios.tcsetattr(self.fd, termios.TCSAFLUSH, state)
            return True
        else:
            return False

    def wait_for_char(self, timeout):
        """return True for a char available, False no char, None not supported"""
        if select:
            rx, _, _ = select.select([self.fd], [], [], timeout)
            return self.fd in rx
        else:
            return None

    def read(self, size):
        """read from terminal and do some covnersions.

        return -1 on Error, or data bytes with len = 0: EOF
        """

        # do ESC to CSI conversion
        if self.in_conv:
            return self.in_conv.read(size)
        else:
            try:
                data = self.obj.read1(size)
            except IOError:
                return -1

    def write(self, data):
        """write to terminal and do some conversions.

        return -1 on Error, 0 on EOF, and >0 written bytes
        """

        # do CSI to ESC conversion
        if self.out_conv:
            data = self.out_conv.convert(data)

        try:
            return self.obj.write(data)
        except IOError:
            return -1
