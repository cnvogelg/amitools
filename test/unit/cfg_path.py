from amitools.vamos.cfg import PathParser
import argparse


def cfg_path_ini_test():
  lp = PathParser()
  ini_dict = {
      "volumes": {
          "sys": "~/.vamos/sys",
          "work": "~/amiga/work",
          "home": "~"
      },
      "assigns": {
          "c": "sys:c+sc:c",
          "libs": "sys:libs",
          "devs": "sys:devs"
      },
      "path": {
          "path": "c:,work:c",
          "cwd": "~/amiga"
      }
  }
  lp.parse_config(ini_dict, 'ini')
  assert lp.get_cfg_dict() == {
      "volumes": {
          "sys": "~/.vamos/sys",
          "work": "~/amiga/work",
          "home": "~"
      },
      "assigns": {
          "c": ["sys:c", "sc:c"],
          "libs": ["sys:libs"],
          "devs": ["sys:devs"]
      },
      "path": {
          "command": ["c:", "work:c"],
          "cwd": "~/amiga"
      }
  }


def cfg_path_args_test():
  lp = PathParser()
  ap = argparse.ArgumentParser()
  lp.setup_args(ap)
  args = ap.parse_args(
      ['-p', 'c:,work:c',
       '--cwd', '~/amiga',
       '-a', 'c:sys:c+sc:c,libs:sys:libs',
       '-a', 'devs:sys:devs',
       '-V', 'sys:~/.vamos/sys',
       '-V', 'work:~/amiga/work,home:~'
       ])
  lp.parse_args(args)
  assert lp.get_cfg_dict() == {
      "volumes": {
          "sys": "~/.vamos/sys",
          "work": "~/amiga/work",
          "home": "~"
      },
      "assigns": {
          "c": ["sys:c", "sc:c"],
          "libs": ["sys:libs"],
          "devs": ["sys:devs"]
      },
      "path": {
          "command": ["c:", "work:c"],
          "cwd": "~/amiga"
      }
  }


def cfg_path_ini_args_test():
  lp = PathParser()
  ini_dict = {
      "volumes": {
          "sys": "~/.vamos/sys",
      },
      "assigns": {
          "c": "sys:c",
          "libs": "sys:libs",
      },
      "path": {
          "path": "c:",
          "cwd": "~/amiga"
      }
  }
  lp.parse_config(ini_dict, 'ini')
  ap = argparse.ArgumentParser()
  lp.setup_args(ap)
  args = ap.parse_args(
      ['-p', '+work:c',
       '-p', '+sys:t',
       '--cwd', '~/amiga',
       '-a', '+c:+sc:c',
       '-a', '+c:+work:c',
       '-a', 'devs:sys:devs',
       '-V', '+work:~/amiga/work',
       '-V', '+home:~'
       ])
  lp.parse_args(args)
  assert lp.get_cfg_dict() == {
      "volumes": {
          "sys": "~/.vamos/sys",
          "work": "~/amiga/work",
          "home": "~"
      },
      "assigns": {
          "c": ["sys:c", "sc:c", "work:c"],
          "libs": ["sys:libs"],
          "devs": ["sys:devs"]
      },
      "path": {
          "command": ["c:", "work:c", "sys:t"],
          "cwd": "~/amiga"
      }
  }
