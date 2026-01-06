from enum import Enum
from amitools.vamos.log import log_machine


class ExcMode(Enum):
    ignore = 0
    log = 1
    abort = 2


class CPUHWExceptionHandler:
    """handle HW exceptions"""

    # map name to exception nums
    hw_exc_map = {
        "bus": [2],
        "address": [3],
        "illegal": [4],
        "zero_div": [5],
        "chk": [6],
        "trapv": [7],
        "priv": [8],
        "trace": [9],
        "line_a": [10],
        "line_f": [11],
        "irqs": [25, 26, 27, 28, 29, 30, 31],
        "traps": [32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 46, 47],
    }

    @classmethod
    def from_cfg(cls, hw_exc_dict):
        if not hw_exc_dict or len(hw_exc_dict) == 0:
            return None
        handler = cls()
        for key, val in hw_exc_dict.items():
            hw_exc_ids = handler.hw_exc_map.get(key, [])
            mode = ExcMode[val.lower()]
            for hw_exc_id in hw_exc_ids:
                handler.set_mode(hw_exc_id, mode)
        return handler

    def __init__(self):
        self.id_table = [ExcMode.abort] * 256

    def set_mode(self, hw_exc_id, mode):
        log_machine.info(f"Define HW Exception {hw_exc_id}: {mode}")
        self.id_table[hw_exc_id] = mode

    def handle_error(self, error):
        exc_num = error.exc_num
        mode = self.id_table[exc_num]
        log_machine.info(f"Handle HW Exception {exc_num}: {mode}")
        if mode == ExcMode.ignore:
            return True
        elif mode == ExcMode.log:
            log_machine.error(f"Hit HW Exception: {error}")
            return True
        else:
            return False
