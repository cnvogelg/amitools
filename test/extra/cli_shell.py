"""Drive the original AmigaOS 3.2.3 ``Shell-Seg`` as a stateful CLI session.

The per-command modules run one program per ``vamos`` process.  This module
instead runs the real AmigaOS shell (``Shell-Seg-47.48`` from ``test/shell-seg``)
through vamos' ``shell`` mode (``-x --shell-bin seg:...``) and feeds it a script
on stdin.  That exercises ``RunCommand``, the command search path and several
``test/cli`` commands inside one session, including the shell's own prompt and
error handling.

Two copyrighted fixtures are needed: the shell seg (``seg:``) and the commands
(``cli:``).  A hostfs file is only executable by AmigaDOS when its host mode has
the execute bit set, so the commands used below are marked executable
(``extract-cli.py`` does the same for the whole drawer).  The tests skip cleanly
when either fixture is absent.
"""

import os
import re

from cli_util import (
    CLI_PATH,
    CLI_PATH_ARG,
    CLI_TIMEOUT,
    add_cli_volume,
    ensure_cmd_executable,
    make_work_tree,
)

SHELL_SEG_DIR = "shell-seg"
SHELL_SEG_VOL = "seg"
SHELL_SEG_VOL_ARG = "-V{}:{}".format(SHELL_SEG_VOL, SHELL_SEG_DIR)
SHELL_SEG_NAME = "Shell-Seg-47.48"
SHELL_SEG_SHA1 = "2be0093a67cacf6efec1258d5bd91db4ee7f1f6f"
SHELL_SEG = "{}:{}".format(SHELL_SEG_VOL, SHELL_SEG_NAME)

# the return code the shell reports for its own "endcli" handling; the same
# value is asserted by shell_seg.py for this seg
ENDCLI_RETCODE = 132

# the shell prints the process number and current directory before each prompt
PROMPT = "\x0f0.SYS:> "
WORK_PROMPT = "\x0f0.work:> "
PROMPT_ENDING = PROMPT + "PROCESS 0 ENDING"

_LIST_HEADER = re.compile(
    re.escape(PROMPT) + r'Directory "work:" on \w+ \d{2}-\w{3}-\d{2}'
)
_LIST_SUMMARY = re.compile(
    r"\d+ files? - \d+ bytes - (?:\d+ director(?:y|ies) - )?\d+ blocks used"
)


def _add_shell_seg_volume(vrun):
    """expose ``test/shell-seg`` as the ``seg:`` volume (at most once)"""
    if SHELL_SEG_VOL_ARG not in vrun.vamos_args:
        vrun.add_volume_or_skip(SHELL_SEG_VOL, SHELL_SEG_DIR)


def _run_shell(vrun, work_dir, script, *commands):
    """run one shell session and return ``(rc, stdout, stderr)``.

    ``commands`` are the ``cli:C`` programs the script runs; they are marked
    executable so the shell's ``LoadSeg`` check passes.
    """
    add_cli_volume(vrun)
    _add_shell_seg_volume(vrun)
    vrun.skip_if_prog_not_available(
        os.path.join(SHELL_SEG_DIR, SHELL_SEG_NAME), SHELL_SEG_SHA1
    )
    for name in commands:
        ensure_cmd_executable(name)
    vargs = [
        "-x",
        "--shell-bin",
        SHELL_SEG,
        CLI_PATH_ARG,
        CLI_PATH,
        "-Vwork:" + str(work_dir),
    ]
    return vrun.run_prog(SHELL_SEG, vargs=vargs, stdin=script, timeout=CLI_TIMEOUT)


def cli_shell_copy_type_test(vrun, tmp_path):
    """A session copies a file and then types the copy back."""
    make_work_tree(tmp_path)
    retcode, stdout, stderr = _run_shell(
        vrun,
        tmp_path,
        "copy work:in.txt work:out.txt\ntype work:out.txt\nendcli\n",
        "Copy",
        "Type",
    )
    # "copy" is silent, so its prompt is followed directly by the next prompt
    assert stdout == [PROMPT + PROMPT + "hello", "world", PROMPT_ENDING]
    assert stderr == []
    assert retcode == ENDCLI_RETCODE
    assert (tmp_path / "out.txt").read_text() == "hello\nworld\n"


def cli_shell_cd_test(vrun, tmp_path):
    """``cd`` changes the current directory and the prompt, and relative
    paths are then resolved against it."""
    make_work_tree(tmp_path)
    retcode, stdout, stderr = _run_shell(
        vrun, tmp_path, "cd work:\ntype in.txt\nendcli\n", "Type"
    )
    assert stdout == [
        PROMPT + WORK_PROMPT + "hello",
        "world",
        WORK_PROMPT + "PROCESS 0 ENDING",
    ]
    assert stderr == []
    assert retcode == ENDCLI_RETCODE


def cli_shell_list_test(vrun, tmp_path):
    """A session runs the ``List`` command on the scratch volume."""
    make_work_tree(tmp_path)
    retcode, stdout, stderr = _run_shell(vrun, tmp_path, "list work:\nendcli\n", "List")
    assert _LIST_HEADER.fullmatch(stdout[0]), stdout[0]
    assert any(line.startswith("in.txt ") for line in stdout)
    assert _LIST_SUMMARY.fullmatch(stdout[-2]), stdout[-2]
    assert stdout[-1] == PROMPT_ENDING
    assert stderr == []
    assert retcode == ENDCLI_RETCODE


def cli_shell_unknown_command_test(vrun, tmp_path):
    """An unknown command is reported by the shell and the session continues."""
    retcode, stdout, stderr = _run_shell(vrun, tmp_path, "nosuchcmd\nendcli\n")
    assert stdout == [PROMPT + "nosuchcmd: Unknown command", PROMPT_ENDING]
    assert stderr == []
    assert retcode == ENDCLI_RETCODE
