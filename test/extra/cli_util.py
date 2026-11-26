"""Shared helpers for the ``test/extra/cli_*.py`` command tests.

The commands are the original AmigaOS 3.2.3 CLI programs extracted into
``test/cli/C`` (see ``test/cli/README.md``).  They are copyrighted and never
committed, so every test skips cleanly when its command is absent.

A command is a normal Amiga binary, so it is run directly in ``proc`` mode::

    vamos -c test.vamosrc -Vcli:cli -p cli:C -- cli:C/<name> [args...]

``run_cli`` keeps the in-process ``vrun`` default; ``timeout`` only applies to
subprocess runs (``--run-subproc``).
"""

import os
import re

CLI_DIR = "cli"
CLI_VOL = "cli"
CLI_VOL_ARG = "-V{}:{}".format(CLI_VOL, CLI_DIR)
CLI_PATH_ARG = "-p"
CLI_PATH = "{}:C".format(CLI_VOL)

# wall clock limit for a single command; a genuine hang should fail the test
# instead of blocking CI.  Only enforced for subprocess runs.
CLI_TIMEOUT = 60


def add_cli_volume(vrun):
    """expose ``test/cli`` as the ``cli:`` volume (at most once).

    ``add_volume_or_skip`` appends to the shared ``vamos_args`` and skips when
    the whole folder is missing; keep it idempotent for the module-scoped
    ``vrun`` fixture.
    """
    if CLI_VOL_ARG not in vrun.vamos_args:
        vrun.add_volume_or_skip(CLI_VOL, CLI_DIR)


def skip_if_cmd_missing(vrun, name, sha1=None):
    """skip the test unless ``cli:C/<name>`` exists (and matches ``sha1``)."""
    add_cli_volume(vrun)
    vrun.skip_if_prog_not_available(os.path.join(CLI_DIR, "C", name), sha1)


def ensure_cmd_executable(name):
    """add the execute bit to ``cli:C/<name>`` if the fixture has none.

    AmigaDOS only runs a hostfs file whose host mode has the execute bit set
    (the shell checks ``fib_Protection`` before ``LoadSeg``).  ``extract-cli.py``
    marks the extracted commands executable, but a fixture restored from the
    encrypted blob without the bit would otherwise make the shell refuse the
    command, so the ``Shell-Seg`` session test enforces it here.
    """
    path = os.path.join(CLI_DIR, "C", name)
    if os.path.exists(path):
        mode = os.stat(path).st_mode
        if not mode & 0o111:
            os.chmod(path, mode | 0o111)


def run_cli(vrun, name, *args, stdin=None, vargs=(), timeout=CLI_TIMEOUT):
    """run ``cli:C/<name>`` with ``args`` and return ``(rc, stdout, stderr)``.

    ``vargs`` are extra vamos options (for example a scratch ``-Vwork:...``);
    the command drawer is always put on the search path.  The run is
    in-process, so ``timeout`` is ignored unless ``--run-subproc`` is set.
    """
    add_cli_volume(vrun)
    prog = "{}:C/{}".format(CLI_VOL, name)
    # the trailing "--" keeps command arguments such as "-w" (Protect) or
    # "FROM"/"TO" out of vamos' own option parser
    all_vargs = [CLI_PATH_ARG, CLI_PATH] + list(vargs) + ["--"]
    return vrun.run_prog(prog, *args, stdin=stdin, vargs=all_vargs, timeout=timeout)


def run_cli_rc(vrun, name, *args, expect_rc=0, **kw):
    """like ``run_cli`` but assert the return code; return ``(stdout, stderr)``."""
    rc, stdout, stderr = run_cli(vrun, name, *args, **kw)
    assert rc == expect_rc, "cli:%s rc=%s want %s (stdout=%r stderr=%r)" % (
        name,
        rc,
        expect_rc,
        stdout,
        stderr,
    )
    return stdout, stderr


# the standard scratch tree used by the file commands.  The sizes are fixed so
# the commands' summaries ("N files - N bytes - ...") are deterministic.
WORK_FILES = {
    "in.txt": "hello\nworld\n",
    "a.txt": "banana\napple\ncherry\n",
    "b.txt": "dog\ncat\n",
    "del.txt": "delete me\n",
    "ren.txt": "rename me\n",
    "nested.txt": "nested\n",
    "sub/deep.txt": "deep\n",
}


def make_work_tree(work_dir):
    """populate a scratch host directory with the standard CLI test tree."""
    for rel, data in WORK_FILES.items():
        path = os.path.join(str(work_dir), rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            f.write(data)
    return work_dir


def work_vargs(work_dir):
    """vamos options exposing ``work_dir`` as the ``work:`` volume."""
    return ["-Vwork:" + str(work_dir)]


def assert_lines(stdout, patterns):
    """assert each stdout line matches the corresponding pattern.

    A ``str`` pattern must be equal; a compiled regex must ``fullmatch``.
    """
    assert len(stdout) == len(patterns), "got %d lines, want %d:\n%s" % (
        len(stdout),
        len(patterns),
        "\n".join(repr(line) for line in stdout),
    )
    for i, (line, pat) in enumerate(zip(stdout, patterns)):
        if isinstance(pat, re.Pattern):
            assert pat.fullmatch(line), "line %d %r does not match %r" % (
                i,
                line,
                pat.pattern,
            )
        else:
            assert line == pat, "line %d %r != %r" % (i, line, pat)
