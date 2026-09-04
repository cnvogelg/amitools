import importlib
from types import SimpleNamespace

import pytest


@pytest.mark.parametrize("execution_fails", [False, True])
@pytest.mark.parametrize("single_return_code", [False, True])
def main_cleanup_reports_failure_and_finishes_test(
    monkeypatch, tmp_path, execution_fails, single_return_code
):
    main = importlib.import_module("amitools.vamos.main")
    execution_error = ValueError("guest execution failed")
    cleanup_error = RuntimeError("base library cleanup failed")
    calls = []

    def wrap(cls, name, error=None):
        original = getattr(cls, name)

        def run(self, *args, **kwargs):
            calls.append(name)
            result = original(self, *args, **kwargs)
            if error is not None:
                raise error
            return result

        monkeypatch.setattr(cls, name, run)

    wrap(main.SetupLibManager, "close_base_libs", cleanup_error)
    wrap(main.MainProfiler, "shutdown", RuntimeError("profiler cleanup failed"))
    wrap(main.DiskSession, "close")
    wrap(main.Machine, "cleanup")

    def run(ctx):
        if execution_fails:
            raise execution_error
        return [0]

    with pytest.raises((ValueError, RuntimeError)) as caught:
        main.main(
            cfg_files=[], args=["--vols-base-dir", str(tmp_path / "volumes")],
            mode=SimpleNamespace(run=run), single_return_code=single_return_code,
        )
    assert caught.value is (execution_error if execution_fails else cleanup_error)
    assert calls == ["close_base_libs", "shutdown", "close", "cleanup"]


def main_cleanup_reports_failure_after_early_return_test(monkeypatch, tmp_path):
    main = importlib.import_module("amitools.vamos.main")
    cleanup = main.Machine.cleanup

    def fail(self):
        cleanup(self)
        raise RuntimeError("machine cleanup failed")

    monkeypatch.setattr(main.Machine, "cleanup", fail)
    monkeypatch.setattr(main.MemoryMap, "parse_config", lambda self, cfg: False)
    with pytest.raises(RuntimeError, match="machine cleanup failed"):
        main.main(cfg_files=[], args=["--vols-base-dir", str(tmp_path / "volumes")])


def main_cleanup_is_not_hidden_by_callers_exception_test(monkeypatch, tmp_path):
    main = importlib.import_module("amitools.vamos.main")
    cleanup = main.Machine.cleanup

    def fail(self):
        cleanup(self)
        raise RuntimeError("machine cleanup failed")

    monkeypatch.setattr(main.Machine, "cleanup", fail)
    try:
        raise ValueError("already handled by caller")
    except ValueError:
        with pytest.raises(RuntimeError, match="machine cleanup failed"):
            main.main(
                cfg_files=[], args=["--vols-base-dir", str(tmp_path / "volumes")],
                mode=SimpleNamespace(run=lambda ctx: [0]),
            )
