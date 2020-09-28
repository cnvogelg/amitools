import pytest

from amitools.vamos.lib.DosLibrary import DosLibrary
from amitools.vamos.lib.ExecLibrary import ExecLibrary
from amitools.vamos.libcore import LibRegistry


def get_reg():
    lr = LibRegistry()
    lr.add_lib_impl("dos.library", DosLibrary)
    lr.add_lib_impl("exec.library", ExecLibrary)
    return lr


def lib_reg_find_cls_test():
    lr = get_reg()
    assert lr.get_lib_impl("dos.library") is DosLibrary
    assert lr.get_lib_impl("exec.library") is ExecLibrary


def lib_reg_has_name_test():
    lr = get_reg()
    assert lr.has_name("dos.library")
    assert lr.has_name("exec.library")


def lib_reg_get_all_cls_test():
    lr = get_reg()
    all_impls = lr.get_all_impls()
    assert DosLibrary in all_impls
    assert ExecLibrary in all_impls


def lib_reg_get_all_names_test():
    lr = get_reg()
    all_names = lr.get_all_names()
    assert "dos.library" in all_names
    assert "exec.library" in all_names
