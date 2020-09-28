import os


def run(toolrun, tmpdir, *args):
    run_args = ["vamostool", "--vols-base-dir", str(tmpdir)]
    run_args += args
    return toolrun.run(*run_args)


def vamostool_path_ami2sys_cwd_test(toolrun, tmpdir):
    cwd = os.getcwd()
    status, out, err = run(toolrun, tmpdir, "path", "ami2sys", "")
    assert status == 0
    assert err == []
    assert out == [cwd]


def vamostool_path_ami2sys_error_test(toolrun, tmpdir):
    status, out, err = run(toolrun, tmpdir, "-Vcwd:.", "path", "ami2sys", "/")
    assert status == 1
    assert err == ["path='cwd:': can't join parent relative path"]
    assert out == []


def vamostool_path_sys2ami_cwd_test(toolrun, tmpdir):
    cwd = os.getcwd()
    status, out, err = run(toolrun, tmpdir, "-Vcwd:.", "path", "sys2ami", cwd)
    assert status == 0
    assert err == []
    assert out == ["cwd:"]


def vamostool_path_sys2ami_tmp_test(toolrun, tmpdir):
    p = str(tmpdir)
    status, out, err = run(toolrun, tmpdir, "path", "sys2ami", p)
    assert status == 0
    assert err == []
    assert out == ["root:" + p[1:]]


def vamostool_type_list_test(toolrun, tmpdir):
    status, out, err = run(toolrun, tmpdir, "type", "list")
    assert status == 0
    assert err == []
    assert "ExecLibrary" in out
