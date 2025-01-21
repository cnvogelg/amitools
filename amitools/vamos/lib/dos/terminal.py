try:
    import termios
except ImportError:
    termios = None


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
        if termios:
            state = termios.tcgetattr(self.fd)
            # control ECHO/ICANON/IEXTEN
            flags = termios.ECHO | termios.ICANON | termios.IEXTEN
            if cooked:
                state[3] |= flags
            else:
                state[3] &= ~flags
            termios.tcsetattr(self.fd, termios.TCSAFLUSH, state)
            return True
        else:
            return False
