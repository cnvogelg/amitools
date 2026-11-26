"""Run the original AmigaOS 3.2.3 ``AmigaModel`` command (see test/cli/README.md).

``AmigaModel`` asks ``expansion.library`` which Amiga model it is running on.
``vamos`` reports the default A1000 configuration, so the command prints a
single model name; an optional ``TO`` file receives the same text.
"""

from cli_util import make_work_tree, run_cli_rc, skip_if_cmd_missing, work_vargs

AMIGAMODEL_SHA1 = "d9a0aea9361f69e5a9bcb689314457a5a79fd6e9"


def cli_amigamodel_test(vrun):
    """``AmigaModel`` prints the detected machine model."""
    skip_if_cmd_missing(vrun, "AmigaModel", AMIGAMODEL_SHA1)
    stdout, stderr = run_cli_rc(vrun, "AmigaModel")
    assert stdout == ["A1000"]
    assert stderr == []


def cli_amigamodel_to_test(vrun, tmp_path):
    """``AmigaModel <file>`` writes the model to the file instead."""
    skip_if_cmd_missing(vrun, "AmigaModel", AMIGAMODEL_SHA1)
    make_work_tree(tmp_path)
    stdout, stderr = run_cli_rc(
        vrun, "AmigaModel", "work:model.txt", vargs=work_vargs(tmp_path)
    )
    assert stdout == []
    assert stderr == []
    with open(str(tmp_path / "model.txt")) as f:
        assert f.read() == "A1000\n"
