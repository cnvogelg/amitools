from amitools.tools.hunktool import main


def hunktool_main_success_exit_code_test():
    assert main(["validate", "README.md"]) == 0
