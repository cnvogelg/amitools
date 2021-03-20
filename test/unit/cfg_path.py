from amitools.vamos.cfg import PathParser
import argparse


def cfg_path_ini_empty_test():
    lp = PathParser()
    ini_dict = {}
    lp.parse_config(ini_dict, "ini")
    assert lp.get_cfg_dict() == {
        "volumes": None,
        "assigns": None,
        "path": {
            "command": None,
            "cwd": None,
            "vols_base_dir": "~/.vamos/volumes",
            "auto_assigns": None,
            "auto_volumes": None,
        },
    }


def cfg_path_ini_test():
    lp = PathParser()
    ini_dict = {
        "volumes": [["sys", "~/.vamos/sys"], ["work", "~/amiga/work"], ["home", "~"]],
        "assigns": [
            ["c", "sys:c,sc:c,home:c"],
            ["libs", "sys:libs"],
            ["devs", "sys:devs"],
        ],
        "path": {
            "path": "c:,work:c",
            "cwd": "~/amiga",
            "auto_volumes": ["a", "b"],
            "auto_assigns": ["c", "d"],
        },
    }
    lp.parse_config(ini_dict, "ini")
    assert lp.get_cfg_dict() == {
        "volumes": ["sys:~/.vamos/sys", "work:~/amiga/work", "home:~"],
        "assigns": ["c:sys:c+sc:c+home:c", "libs:sys:libs", "devs:sys:devs"],
        "path": {
            "command": ["c:", "work:c"],
            "cwd": "~/amiga",
            "vols_base_dir": "~/.vamos/volumes",
            "auto_volumes": ["a", "b"],
            "auto_assigns": ["c", "d"],
        },
    }


def cfg_path_args_test():
    lp = PathParser()
    ap = argparse.ArgumentParser()
    lp.setup_args(ap)
    args = ap.parse_args(
        [
            "-p",
            "c:,work:c",
            "--cwd",
            "~/amiga",
            "-a",
            "c:sys:c+sc:c,libs:sys:libs",
            "-a",
            "devs:sys:devs",
            "-V",
            "sys:~/.vamos/sys",
            "-V",
            "work:~/amiga/work,home:~",
            "-V",
            "local:",
            "--auto-volumes",
            "a,b",
            "--auto-assigns",
            "c,d",
            "--vols-base-dir",
            "/bla",
        ]
    )
    lp.parse_args(args)
    assert lp.get_cfg_dict() == {
        "volumes": ["sys:~/.vamos/sys", "work:~/amiga/work", "home:~", "local:"],
        "assigns": ["c:sys:c+sc:c", "libs:sys:libs", "devs:sys:devs"],
        "path": {
            "command": ["c:", "work:c"],
            "cwd": "~/amiga",
            "vols_base_dir": "/bla",
            "auto_volumes": ["a", "b"],
            "auto_assigns": ["c", "d"],
        },
    }


def cfg_path_ini_args_test():
    lp = PathParser()
    ini_dict = {
        "volumes": [
            ["sys", "~/.vamos/sys"],
        ],
        "assigns": [
            ["c", "sys:c"],
            ["libs", "sys:libs"],
        ],
        "path": {
            "path": "c:",
            "cwd": "~/amiga",
            "auto_volumes": ["a"],
            "auto_assigns": ["x"],
        },
    }
    lp.parse_config(ini_dict, "ini")
    ap = argparse.ArgumentParser()
    lp.setup_args(ap)
    args = ap.parse_args(
        [
            "-p",
            "work:c",
            "-p",
            "sys:t",
            "--cwd",
            "~/amiga",
            "-a",
            "c:sc:c",
            "-a",
            "c:work:c",
            "-a",
            "devs:sys:devs",
            "-V",
            "work:~/amiga/work",
            "-V",
            "home:~",
            "-V",
            "local:",
            "--vols-base-dir",
            "/bla",
            "--auto-volumes",
            "b,c",
            "--auto-assigns",
            "y,z",
        ]
    )
    lp.parse_args(args)
    assert lp.get_cfg_dict() == {
        "volumes": ["sys:~/.vamos/sys", "work:~/amiga/work", "home:~", "local:"],
        "assigns": ["c:sys:c", "libs:sys:libs", "c:sc:c", "c:work:c", "devs:sys:devs"],
        "path": {
            "command": ["c:", "work:c", "sys:t"],
            "cwd": "~/amiga",
            "vols_base_dir": "/bla",
            "auto_volumes": ["a", "b", "c"],
            "auto_assigns": ["x", "y", "z"],
        },
    }
