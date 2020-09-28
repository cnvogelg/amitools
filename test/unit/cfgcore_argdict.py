from amitools.vamos.cfgcore import Argument, ArgumentDict
import argparse


def config_argdict_argument_test():
    a = Argument("-x", "--the-x", action="store_true", default=False)
    ap = argparse.ArgumentParser()
    a.add(ap)
    args = ap.parse_args(["-x"])
    assert a.get_value(args)
    args = ap.parse_args([])
    assert not a.get_value(args)


def config_argdict_simple_test():
    cfg = {"a": Argument("-x", action="store_true", default=False), "b": Argument("-b")}
    ad = ArgumentDict(cfg)
    ap = argparse.ArgumentParser()
    ad.add_args(ap)
    # only set -x
    args = ap.parse_args(["-x"])
    assert ad.gen_dict(args) == {"a": True}
    # only set -b
    args = ap.parse_args(["-b", "hi"])
    assert ad.gen_dict(args) == {"a": False, "b": "hi"}


def config_argdict_order_test():
    cfg = {"a": Argument("first", order=1), "b": Argument("second", order=2)}
    ad = ArgumentDict(cfg)
    ap = argparse.ArgumentParser()
    ad.add_args(ap)
    # check order
    args = ap.parse_args(["first", "second"])
    assert ad.gen_dict(args) == {"a": "first", "b": "second"}
