try:
    import termios
except ImportError:
    termios = None

try:
    import select
except ImportError:
    select = None


class Terminal:
    def __init__(self, fd):
        self.fd = fd
        if termios:
            self.tty_state = termios.tcgetattr(fd)

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
