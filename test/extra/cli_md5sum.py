"""Run the original AmigaOS 3.2.3 ``MD5Sum`` command (see test/cli/README.md).

``MD5Sum <file>`` prints the MD5 checksum of a file, followed by the file name.
"""

from cli_util import make_work_tree, run_cli_rc, skip_if_cmd_missing, work_vargs

MD5SUM_SHA1 = "7a34420776012dbbc7bd655cd032def6bdab9b82"

# MD5 of the fixed "hello\nworld\n" content written by make_work_tree
IN_MD5 = "0f723ae7f9bf07744445e93ac5595156"


def cli_md5sum_file_test(vrun, tmp_path):
    """``MD5Sum <file>`` prints the file's MD5 checksum and name."""
    skip_if_cmd_missing(vrun, "MD5Sum", MD5SUM_SHA1)
    make_work_tree(tmp_path)
    stdout, stderr = run_cli_rc(
        vrun, "MD5Sum", "work:in.txt", vargs=work_vargs(tmp_path)
    )
    assert stdout == ["%s  work:in.txt" % IN_MD5]
    assert stderr == []
