from amitools.vamos.tools import PathTool, tools_main


def tools_path_simple_test(capsys):
  tools=[PathTool()]
  res = tools_main(tools, args=['sys2ami', 'tmp'])
  assert res == 0
  captured = capsys.readouterr()
  assert captured.out.splitlines() == [
    "sys:tmp"
  ]
