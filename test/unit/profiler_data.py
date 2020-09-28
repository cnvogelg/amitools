from amitools.vamos.profiler import ProfDataFile


def profiler_data_load_save_test(tmpdir):
    path = str(tmpdir.join("prof.json"))
    df = ProfDataFile()
    data = {"bar": 12, "baz": "hello"}
    df.set_prof_data("foo", data)
    df.save_json_file(path)
    # read in again
    df2 = ProfDataFile()
    df2.load_json_file(path)
    assert df2.get_prof_data("foo") == data
