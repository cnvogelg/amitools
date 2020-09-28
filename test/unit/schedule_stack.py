from amitools.vamos.schedule import Stack


def schedule_stack_default_test(mem_alloc):
    mem, alloc = mem_alloc
    st = Stack.alloc(alloc, 4096)
    assert st
    l = st.get_lower()
    u = st.get_upper()
    s = st.get_size()
    assert u - l == s
    assert mem.r32(u - 4) == s
    st.free()
    assert alloc.is_all_free()
