from amitools.binfmt.hunk.Hunk import (
    HUNK_CODE,
    HUNK_DATA,
    HUNK_DEBUG,
    HUNK_END,
    HUNK_HEADER,
    HUNK_SYMBOL,
    hunk_names,
)
from amitools.binfmt.hunk.HunkReader import HunkReader


def make_hunk(hunk_type, **fields):
    hunk = {"type": hunk_type, "type_name": hunk_names[hunk_type]}
    hunk.update(fields)
    return hunk


def test_hunk_reader_loadseg_trailing_debug_symbols_test():
    reader = HunkReader()
    reader.hunks = [
        make_hunk(
            HUNK_HEADER,
            first_hunk=0,
            hunks=[{"size": 4, "memf": ""}, {"size": 4, "memf": ""}],
        ),
        make_hunk(HUNK_CODE),
        make_hunk(HUNK_END),
        make_hunk(HUNK_DATA),
        make_hunk(HUNK_END),
        make_hunk(HUNK_DEBUG),
        make_hunk(HUNK_SYMBOL),
        make_hunk(HUNK_END),
    ]

    assert reader.build_segments()
    assert [segment[0]["type"] for segment in reader.segments] == [
        HUNK_CODE,
        HUNK_DATA,
    ]
    assert [block["type"] for block in reader.segments[-1]] == [
        HUNK_DATA,
        HUNK_DEBUG,
        HUNK_SYMBOL,
    ]
