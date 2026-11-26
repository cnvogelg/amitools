"""Run the original AmigaOS 3.2.3 ``RequestChoice`` command (see test/cli/README.md).

``RequestChoice TITLE BODY GADGETS`` shows a requester and prints the number of
the gadget the user picked.  ``vamos`` answers the requester with its first
gadget, so the result is deterministic; ``SET=`` stores the number in a variable
instead of printing it.
"""

from cli_util import run_cli_rc, skip_if_cmd_missing

REQUESTCHOICE_SHA1 = "bf4c7f185f4c28bf84ee7872ac32b7de7423e3a5"


def cli_requestchoice_test(vrun):
    """``RequestChoice`` prints the number of the chosen gadget."""
    skip_if_cmd_missing(vrun, "RequestChoice", REQUESTCHOICE_SHA1)
    stdout, stderr = run_cli_rc(
        vrun, "RequestChoice", "TITLE", "Hi", "BODY", "Yo", "OK"
    )
    assert stdout == ["1"]
    # the requester itself is answered by vamos' intuition stub
    assert any("EasyRequest" in line for line in stderr)


def cli_requestchoice_set_test(vrun):
    """``RequestChoice ... SET=RC`` stores the result instead of printing it."""
    skip_if_cmd_missing(vrun, "RequestChoice", REQUESTCHOICE_SHA1)
    stdout, stderr = run_cli_rc(
        vrun, "RequestChoice", "TITLE", "Hi", "BODY", "Yo", "OK", "SET=RC"
    )
    assert stdout == []
    assert any("EasyRequest" in line for line in stderr)
