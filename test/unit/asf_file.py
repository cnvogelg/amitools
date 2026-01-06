import pytest
from amitools.state import ASFFile

ASF_LIST = (
    "a500.uss",
    "a500z2ram.uss",
    "a4000.uss",
    "a4000z3ram.uss",
)


@pytest.fixture(params=ASF_LIST)
def asf_file(request):
    file_name = request.param
    return "state/" + file_name


def asf_file_test(asf_file):
    asf = ASFFile(asf_file)
    chunks = asf.chunklist()
    assert len(chunks) > 0
    # get chip ram chunk
    cram = asf.get_chunk("CRAM")
    assert cram is not None
    # load chip ram chunk
    data = asf.load_chunk("CRAM")
    if "a500" in asf_file:
        chip_size = 512 * 1024
    else:
        chip_size = 2048 * 1024
    assert len(data) == chip_size
    # get all z2 ram chunks
    datas = asf.load_all_chunks("FRAM")
    if "z2ram" in asf_file:
        assert len(datas) > 0
    else:
        assert datas is None
    # get all z3 ram chunks
    datas = asf.load_all_chunks("ZRAM")
    if "z3ram" in asf_file:
        assert len(datas) > 0
    else:
        assert datas is None
