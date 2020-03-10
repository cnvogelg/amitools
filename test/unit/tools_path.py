import os
from amitools.vamos.tools import PathTool, tools_main


def tools_path_simple_test(capsys, tmpdir):
    tools = [PathTool()]
    cwd = os.getcwd()
    cfg_dict = {"volumes": ["cwd:" + cwd], "path": {"vols_base_dir": str(tmpdir)}}
    res = tools_main(tools, args=["sys2ami", "tmp"], cfg_dict=cfg_dict)
    assert res == 0
    captured = capsys.readouterr()
    assert captured.out.splitlines() == ["cwd:tmp"]
