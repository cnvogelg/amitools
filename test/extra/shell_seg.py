"""Run original AmigaOS shells under ``vamos -x``.

Two sources of Shell-Seg binaries are used:

* ``volumes/wb/l/Shell-Seg`` (AmigaOS 3.1.4) drives the ``wb:`` fixture tests
  below, which also exercise ``RunCommand``/``run`` argument passing.
* ``test/shell-seg`` holds one seg per shell version (see its README);
  ``shell_seg_variant_endcli_test`` runs each of them through the ``shell``
  mode (``-x --shell-bin seg:<name>``).

The ``test/shell-seg`` binaries are copyrighted AmigaOS files extracted
locally with ``test/shell-seg/extract-shell-seg.py``, so every variant test
skips when its seg is missing.
"""

import os

import pytest

SHELL_SEG_DIR = "shell-seg"
SHELL_SEG_VOL = "seg"
SHELL_SEG_VOL_ARG = "-V{}:{}".format(SHELL_SEG_VOL, SHELL_SEG_DIR)

PROMPT_ENDING = "\x0f0.SYS:> PROCESS 0 ENDING"

# the return code the shell reports for its own "endcli" handling, per seg.
# None means the seg does not yet run to completion in vamos, so its run is
# pinned as xfail until that is fixed.
SHELL_SEG_ENDCLI_RETCODE = {
    # a genuine BCPL program (its first long-word is a BCPL GV init offset):
    # it needs the dos.library BCPL Global Vector plus the BCPL call/return
    # trampolines, none of which vamos implements yet.
    "Shell-Seg-1.3": None,
    # 37.69/39.13/40.2/45.7+ are C programs with a BCPL-compatible entry
    # stub at seg+8; the stub returns through A6 (the BCPL return address),
    # which ShellProcess now points at the machine exit trap.
    "Shell-Seg-37.69": 46,
    "Shell-Seg-39.13": 46,
    "Shell-Seg-40.2": 44,
    "Shell-Seg-45.7": 188,
    "Shell-Seg-46.10": 212,
    "Shell-Seg-47.47": 136,
    "Shell-Seg-47.48": 132,
}


def check_shell_seg(vrun):
    sha1 = "8609de3b11da6b5d40d375a8d383fa2513316b28"
    vrun.add_volume_or_skip("wb", "volumes/wb")
    vrun.skip_if_prog_not_available("volumes/wb/l/Shell-Seg", sha1)


def shell_seg_endcli_test(vrun):
    check_shell_seg(vrun)
    stdin = "endcli\n"
    retcode, stdout, stderr = vrun.run_prog(
        "wb:l/Shell-Seg", vargs=["-x", "--shell-bin", "wb:l/Shell-Seg"], stdin=stdin
    )
    assert stdout == ["\x0f0.SYS:> PROCESS 0 ENDING"]
    assert stderr == []
    assert retcode == 212


def shell_seg_proc_args_test(vrun, vamos):
    check_shell_seg(vrun)
    vamos.make_prog("proc_args")
    cmd_name = vamos.get_prog_bin_name("proc_args")
    stdin = cmd_name + "\nendcli\n"
    retcode, stdout, stderr = vrun.run_prog(
        "wb:l/Shell-Seg", vargs=["-x", "--shell-bin", "wb:l/Shell-Seg"], stdin=stdin
    )
    # RunCommand() sets pr_Arguments to the rest of the command line, so
    # GetArgStr() returns the shell's argument string.  vc mangles it (see
    # suite/proc_args.py).
    arg_str = "" if vamos.flavor == "vc" else "\\n"
    assert stdout == [
        '\x0f0.SYS:> a0:"' + arg_str + '"',
        'in:"\\n"',
        "\x0f0.SYS:> PROCESS 0 ENDING",
    ]
    assert stderr == []
    assert retcode == 212


def shell_seg_run_proc_args_test(vrun, vamos):
    check_shell_seg(vrun)
    vamos.make_prog("proc_args")
    cmd_name = vamos.get_prog_bin_name("proc_args")
    stdin = "run " + cmd_name + "\nendcli\n"
    retcode, stdout, stderr = vrun.run_prog(
        "wb:l/Shell-Seg", vargs=["-x", "--shell-bin", "wb:l/Shell-Seg"], stdin=stdin
    )
    assert stdout == ["\x0f0.SYS:> \x0f0.SYS:> PROCESS 0 ENDING"]
    assert stderr == []
    assert retcode == 212


# ----- the seg variants collected in test/shell-seg -----


def _add_shell_seg_volume(vrun):
    """expose test/shell-seg as the ``seg:`` volume (at most once)"""
    if SHELL_SEG_VOL_ARG not in vrun.vamos_args:
        vrun.add_volume_or_skip(SHELL_SEG_VOL, SHELL_SEG_DIR)


def _run_shell_seg(vrun, name, stdin):
    _add_shell_seg_volume(vrun)
    vrun.skip_if_prog_not_available(os.path.join(SHELL_SEG_DIR, name))
    seg = "{}:{}".format(SHELL_SEG_VOL, name)
    # the positional is ignored by the shell mode; the seg is named by
    # --shell-bin so the run goes through ShellProcess, not the binary path
    return vrun.run_prog(seg, vargs=["-x", "--shell-bin", seg], stdin=stdin)


def _shell_seg_param(name):
    if SHELL_SEG_ENDCLI_RETCODE[name] is None:
        return pytest.param(
            name,
            marks=pytest.mark.xfail(
                reason="seg needs the BCPL runtime binder, which is not "
                "implemented (see test/shell-seg/README.md)",
            ),
        )
    return pytest.param(name)


@pytest.mark.parametrize(
    "name", [_shell_seg_param(n) for n in sorted(SHELL_SEG_ENDCLI_RETCODE)]
)
def shell_seg_variant_endcli_test(vrun, name):
    retcode, stdout, stderr = _run_shell_seg(vrun, name, "endcli\n")
    assert stdout == [PROMPT_ENDING]
    assert stderr == []
    assert retcode == SHELL_SEG_ENDCLI_RETCODE[name]
