from amitools.vamos.tools import tools_main, Tool


def tools_main_single_test():
    tools = [Tool("tool")]
    res = tools_main(tools, args=[])
    assert res == 0


def tools_main_multi_test():
    tools = [Tool("tool1"), Tool("tool2")]
    res = tools_main(tools, args=["tool1"])
    assert res == 0
