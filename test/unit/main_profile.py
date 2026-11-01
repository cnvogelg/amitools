from amitools.vamos.main import main_profile


def main_profile_dump_without_file_test(monkeypatch):
    monkeypatch.setattr("amitools.vamos.main.main", lambda *args, **kwargs: 0)

    assert main_profile(profile_file=None, dump_profile=True) == 0
