"""Cross-process exclusion uses named objects, not device share modes."""

import ctypes
import os
import subprocess
import sys
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from amitools.util.Win32Disk import _Win32


@pytest.mark.parametrize("error", [0, 183, 5])
def named_disk_lock_test(monkeypatch, error):
    api = _Win32.__new__(_Win32)
    api.dll = SimpleNamespace(CreateMutexW=Mock(return_value=123 if error != 5 else 0),
                              CloseHandle=Mock(return_value=1))
    monkeypatch.setattr(ctypes, "get_last_error", lambda: error, raising=False)
    monkeypatch.setattr(ctypes, "FormatError", lambda code: "denied", raising=False)
    if error:
        with pytest.raises(OSError):
            api.lock_disk(2)
        assert api.dll.CloseHandle.call_count == (1 if error == 183 else 0)
    else:
        assert api.lock_disk(2) == 123
        api.dll.CloseHandle.assert_not_called()
    api.dll.CreateMutexW.assert_called_once_with(None, False,
                                                r"Global\amitools-PhysicalDrive2")


@pytest.mark.skipif(sys.platform != "win32", reason="native Windows objects")
def native_disk_lock_process_test():
    # No physical disk is accessed. A unique number isolates concurrent tests.
    number = 1000000 + os.getpid()
    api = _Win32()
    handle = api.lock_disk(number)
    code = "from amitools.util.Win32Disk import _Win32; a=_Win32(); a.close(a.lock_disk(%d))" % number
    try:
        result = subprocess.run([sys.executable, "-c", code], capture_output=True,
                                text=True, timeout=10)
        assert result.returncode != 0
        assert "already in use" in result.stderr
    finally:
        # No thread ownership is taken, so teardown may run on another thread.
        import threading
        closer = threading.Thread(target=api.close, args=(handle,))
        closer.start()
        closer.join()
    subprocess.run([sys.executable, "-c", code], check=True, timeout=10)
