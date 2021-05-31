from amitools.vamos.lib.dos.CSource import CSource
from amitools.vamos.lib.dos.Item import ItemParser


def item_parser1_test():
    csrc = CSource(b"hello world\n")
    ip = ItemParser(csrc)
    maxbuf = 256
    assert ip.read_item(maxbuf) == (ItemParser.ITEM_UNQUOTED, "hello")
    assert ip.read_item(maxbuf) == (ItemParser.ITEM_UNQUOTED, "world")
    assert ip.read_item(maxbuf) == (ItemParser.ITEM_NOTHING, None)


def item_parser2_test():
    csrc = CSource(b'"hello space" "world*n"\n')
    ip = ItemParser(csrc)
    maxbuf = 256
    assert ip.read_item(maxbuf) == (ItemParser.ITEM_QUOTED, "hello space")
    assert ip.read_item(maxbuf) == (ItemParser.ITEM_QUOTED, "world\n")
    assert ip.read_item(maxbuf) == (ItemParser.ITEM_NOTHING, None)


def check_item_eol(in_str, itype, item, eol):
    csrc = CSource((in_str + "\n").encode("latin-1"))
    ip = ItemParser(csrc)
    maxbuf = 256
    assert ip.read_item(maxbuf) == (itype, item)
    assert ip.read_eol() == eol
    assert ip.read_item(maxbuf) == (ItemParser.ITEM_NOTHING, None)


def item_parser3_test():
    check_item_eol("a", ItemParser.ITEM_UNQUOTED, "a", "")
    check_item_eol("a  b", ItemParser.ITEM_UNQUOTED, "a", "  b")
    check_item_eol("a  b  ", ItemParser.ITEM_UNQUOTED, "a", "  b")
    check_item_eol('"a"  b', ItemParser.ITEM_QUOTED, "a", "  b")
    check_item_eol('"a"  b  ', ItemParser.ITEM_QUOTED, "a", "  b  ")


def item_parser_eol_bug_test():
    csrc = CSource(b"hello world")
    ip = ItemParser(csrc)
    maxbuf = 256
    assert ip.read_item(maxbuf) == (ItemParser.ITEM_UNQUOTED, "hello")
    assert ip.read_item(maxbuf) == (ItemParser.ITEM_UNQUOTED, "world")
    # with eol_bug enabled we get last char again...
    assert ip.read_item(maxbuf) == (ItemParser.ITEM_UNQUOTED, "d")
    # now again with fixed parser
    csrc = CSource(b"hello world")
    ip = ItemParser(csrc, eol_unget_bug=False)
    assert ip.read_item(maxbuf) == (ItemParser.ITEM_UNQUOTED, "hello")
    assert ip.read_item(maxbuf) == (ItemParser.ITEM_UNQUOTED, "world")
    assert ip.read_item(maxbuf) == (ItemParser.ITEM_NOTHING, None)
