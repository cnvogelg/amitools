def test_tags_test(vamos):
    retcode, stdout, stderr = vamos.run_prog("test_tags")
    assert retcode == 0
    assert stdout == []
    assert stderr == []
