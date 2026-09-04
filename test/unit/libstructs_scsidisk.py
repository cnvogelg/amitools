import subprocess
import sys
from pathlib import Path


def scsidisk_type_is_available_without_device_import_test():
    # Use a fresh interpreter so test collection cannot register the type.
    subprocess.run(
        [sys.executable, "-c", """
import sys
from amitools.vamos.astructs import AmigaStructTypes
from amitools.vamos.libstructs import SCSICmdStruct
assert 'amitools.vamos.lib.ScsiDevice' not in sys.modules
assert AmigaStructTypes.find_struct('SCSICmd') is SCSICmdStruct
assert SCSICmdStruct.get_byte_size() == 30
"""],
        check=True,
        cwd=Path(__file__).resolve().parents[2],
    )
