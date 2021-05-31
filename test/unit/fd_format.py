from amitools.fd import *


def fd_format_get_base_name_test():
    assert get_base_name("bla.library") == "_BlaBase"
    assert get_base_name("foo.device") == "_FooBase"


def fd_format_get_fd_name_test():
    assert get_fd_name("vamostest.library") == "vamostest_lib.fd"
    assert get_fd_name("timer.device") == "timer_lib.fd"


def fd_format_generate_fd_default_test():
    fd = generate_fd("bla.library")
    assert fd
    assert fd.get_base_name() == "_BlaBase"
    assert fd.get_max_bias() == 24
    assert fd.get_neg_size() == 30
    assert fd.get_num_indices() == 4


def fd_format_generate_fd_num_call_test():
    fd = generate_fd("bla.device", 10)
    assert fd
    assert fd.get_base_name() == "_BlaBase"
    assert fd.get_max_bias() == 60
    assert fd.get_neg_size() == 66
    assert fd.get_num_indices() == 10
    assert fd.get_func_by_index(0).get_name() == "_OpenDev"
    assert fd.get_func_by_index(9).get_name() == "FakeFunc_10"


def fd_format_read_vamostest_lib_test():
    fd = read_lib_fd("vamostest.library")
    assert fd.get_base_name() == "_VamosTestBase"
    assert fd.get_max_bias() == 66
    assert fd.get_neg_size() == 72
    assert fd.get_num_indices() == 11
    # check entries
    tab = fd.get_index_table()
    assert len(tab) == fd.get_num_indices()
    open_lib = fd.get_func_by_name("_OpenLib")
    assert fd.get_func_by_index(0) == open_lib
    assert tab[0] == open_lib
    assert open_lib.get_index() == 0
    assert open_lib.get_bias() == 6
    close_lib = fd.get_func_by_name("_CloseLib")
    assert fd.get_func_by_index(1) == close_lib
    assert tab[1] == close_lib
    assert close_lib.get_index() == 1
    assert close_lib.get_bias() == 12
    expunge_lib = fd.get_func_by_name("_ExpungeLib")
    assert fd.get_func_by_index(2) == expunge_lib
    assert tab[2] == expunge_lib
    assert expunge_lib.get_index() == 2
    assert expunge_lib.get_bias() == 18


def fd_format_read_timer_dev_test():
    fd = read_lib_fd("timer.device")
    assert fd.get_base_name() == "_TimerBase"
    assert fd.get_max_bias() == 66
    assert fd.get_neg_size() == 72
    assert fd.get_num_indices() == 11
    # check entries
    tab = fd.get_index_table()
    assert len(tab) == fd.get_num_indices()
    open_lib = fd.get_func_by_name("_OpenDev")
    assert fd.get_func_by_index(0) == open_lib
    assert tab[0] == open_lib
    assert open_lib.get_index() == 0
    assert open_lib.get_bias() == 6
    close_lib = fd.get_func_by_name("_CloseDev")
    assert fd.get_func_by_index(1) == close_lib
    assert tab[1] == close_lib
    assert close_lib.get_index() == 1
    assert close_lib.get_bias() == 12
    expunge_lib = fd.get_func_by_name("_ExpungeDev")
    assert fd.get_func_by_index(2) == expunge_lib
    assert tab[2] == expunge_lib
    assert expunge_lib.get_index() == 2
    assert expunge_lib.get_bias() == 18
