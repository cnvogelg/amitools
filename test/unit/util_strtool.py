from amitools.util.strtool import to_text_string, to_binary_string, to_string


def util_strtool_to_text_test():
    assert to_text_string("hello, world!") == "'hello, world!'"
    assert to_text_string("hello\nworld!\r") == "'hello\\nworld!\\r'"
    assert to_text_string("\xa0") == "'\\xa0'"
    assert to_text_string("hello, world!", add_size=True) == "'hello, world!'(13)"


def util_strtool_to_binary_test():
    assert to_binary_string("abc") == "'a' 'b' 'c' (3)"
    assert to_binary_string("\xa0\xa1\xa2") == "a0 a1 a2 (3)"
    # ellipsis
    assert (
        to_binary_string("hello, world!") == "'h' 'e' 'l' 'l' 'o' ',' ' ' 'w' ... (13)"
    )


def util_strtool_to_str_test():
    assert to_string("hello, world!") == "'hello, world!'"
    assert to_string("\xa0\xa1\xa2") == "a0 a1 a2 (3)"
    assert to_string("hello, world!", add_size=True) == "'hello, world!'(13)"
