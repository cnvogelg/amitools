import os

import pytest

from amitools.fs.ADFSVolume import ADFSVolume
from amitools.fs.FSError import FSError, INVALID_COMMENT
from amitools.fs.FSString import FSString
from amitools.fs.Imager import Imager
from amitools.fs.Repacker import Repacker
from amitools.fs.blkdev.ADFBlockDevice import ADFBlockDevice
import amitools.fs.DosType as DosType
from amitools.tools.xdftool import main as xdftool_main

DOS_TYPES = [DosType.DOS0 + n for n in range(8)]
LONGNAME_DOS_TYPES = [DosType.DOS6, DosType.DOS7]


def dos_id(dos_type):
    return "DOS%d" % (dos_type - DosType.DOS0)


def create_volume(path, dos_type):
    blkdev = ADFBlockDevice(str(path))
    blkdev.create()
    volume = ADFSVolume(blkdev)
    volume.create(FSString("Test"), dos_type=dos_type)
    return blkdev, volume


def open_volume(path):
    blkdev = ADFBlockDevice(str(path))
    blkdev.open()
    volume = ADFSVolume(blkdev)
    volume.open()
    return blkdev, volume


def close_volume(blkdev, volume):
    volume.close()
    blkdev.close()


def get_comment(volume, path):
    return volume.get_path_name(FSString(path)).get_meta_info().get_comment()


PACK_TS = "01.01.2020 00:00:00.00"


def make_pack_tree(tmp_path, xdfmeta=None, uaem=None):
    """a tree with a.txt and sub/b.txt to pack, with the comments given by
    path in its .xdfmeta file and in .uaem files"""
    tree = tmp_path / "tree"
    (tree / "sub").mkdir(parents=True)
    (tree / "a.txt").write_bytes(b"data")
    (tree / "sub" / "b.txt").write_bytes(b"data")
    if xdfmeta is not None:
        lines = ["Test:DOS0,%s,%s,%s" % (PACK_TS, PACK_TS, PACK_TS)]
        for path, comment in xdfmeta.items():
            lines.append("%s:rwed,%s,%s" % (path, PACK_TS, comment))
        (tmp_path / "tree.xdfmeta").write_bytes(("\n".join(lines) + "\n").encode())
    for path, comment in (uaem or {}).items():
        line = "----rwed 2020-01-01 00:00:00.00 %s\n" % comment
        (tree / (path + ".uaem")).write_bytes(line.encode())
    return tree


@pytest.mark.parametrize(
    "meta, path, comment",
    [
        ("xdfmeta", "a.txt", "x" * 80),
        ("uaem", "a.txt", "x" * 80),
        ("xdfmeta", "sub/b.txt", "x" * 80),
        ("uaem", "sub/b.txt", "x" * 80),
        ("xdfmeta", "sub", "x" * 80),
        ("uaem", "sub", "x" * 80),
        # .uaem files are UTF-8, .xdfmeta files in the platform's encoding
        ("uaem", "a.txt", "5 €"),
    ],
    ids=[
        "xdfmeta",
        "uaem",
        "xdfmeta_sub",
        "uaem_sub",
        "xdfmeta_dir",
        "uaem_dir",
        "uaem_not_latin1",
    ],
)
def fs_pack_comment_too_long_test(tmp_path, meta, path, comment, capsys):
    # A comment the image cannot hold, over 79 bytes or not Latin-1, in the
    # metadata of a file or directory of a tree to pack, stops xdftool pack
    # before it creates the image.
    comments = {path: comment}
    if meta == "xdfmeta":
        tree = make_pack_tree(tmp_path, xdfmeta=comments)
    else:
        tree = make_pack_tree(tmp_path, uaem=comments)
    image = tmp_path / "test.adf"
    capsys.readouterr()
    assert xdftool_main([str(image), "pack", str(tree)]) == 3
    assert "Invalid comment" in capsys.readouterr().out
    assert not image.exists()


@pytest.mark.parametrize("meta", ["no_entry", "uaem_wins"])
def fs_pack_unused_meta_test(tmp_path, meta):
    # Only comments that xdftool pack writes are checked: not one in the
    # .xdfmeta file for a path that is not in the tree, nor one there for a
    # file whose .uaem file pack takes instead.
    if meta == "no_entry":
        tree = make_pack_tree(tmp_path, xdfmeta={"gone.txt": "x" * 80})
        want = ""
    else:
        tree = make_pack_tree(
            tmp_path, xdfmeta={"a.txt": "x" * 80}, uaem={"a.txt": "short"}
        )
        want = "short"
    image = tmp_path / "test.adf"
    assert xdftool_main([str(image), "pack", str(tree)]) == 0
    blkdev, volume = open_volume(image)
    assert get_comment(volume, "a.txt") == FSString(want)
    assert volume.read_file(FSString("sub/b.txt")) == b"data"
    close_volume(blkdev, volume)


def make_repack_image(path, dos_type, comments, raw=False):
    """an image with a.txt, sub/b.txt and sub/c.txt and the comments given
    by path; with raw, written into the headers past the comment check, as
    an older tool may have written them"""
    blkdev, volume = create_volume(path, dos_type)
    volume.write_file(b"data a", FSString("a.txt"))
    volume.create_dir(FSString("sub"))
    volume.write_file(b"data b", FSString("sub/b.txt"))
    volume.write_file(b"data c", FSString("sub/c.txt"))
    for name, comment in comments.items():
        node = volume.get_path_name(FSString(name))
        if raw:
            node.block.comment = FSString(comment)
            node.block.write()
        else:
            node.change_comment(FSString(comment))
    close_volume(blkdev, volume)


@pytest.mark.parametrize("path", ["a.txt", "sub/b.txt"])
@pytest.mark.parametrize("dos_type", LONGNAME_DOS_TYPES, ids=dos_id)
def fs_repack_comment_too_long_test(tmp_path, dos_type, path, capsys):
    # A long name header keeps up to 109 bytes of comment beside a short
    # name. A comment over 79 bytes there, which the new image cannot hold,
    # stops xdftool repack before it creates the image.
    src = tmp_path / "src.adf"
    make_repack_image(src, dos_type, {path: "x" * 100}, raw=True)
    image = tmp_path / "out.adf"
    capsys.readouterr()
    assert xdftool_main([str(image), "repack", str(src)]) == 3
    assert "Invalid comment" in capsys.readouterr().out
    assert not image.exists()


@pytest.mark.parametrize("dos_type", DOS_TYPES, ids=dos_id)
def fs_repack_comments_test(tmp_path, dos_type):
    # Comments the new image can hold, up to 79 bytes, are repacked.
    src = tmp_path / "src.adf"
    comments = {"a.txt": "a" * 79, "sub": "dir", "sub/c.txt": "c"}
    make_repack_image(src, dos_type, comments)
    image = tmp_path / "out.adf"
    assert xdftool_main([str(image), "repack", str(src)]) == 0
    blkdev, volume = open_volume(image)
    for path, comment in comments.items():
        assert get_comment(volume, path) == FSString(comment)
    assert volume.read_file(FSString("sub/b.txt")) == b"data b"
    close_volume(blkdev, volume)


@pytest.mark.parametrize("comment", ["short", "x" * 80], ids=["ok", "too_long"])
def fs_pack_symlink_loop_test(tmp_path, comment, monkeypatch):
    # The comment check walks a directory once on each path: two symlinks
    # back to the top of the tree do not make it walk on and on.
    tree = make_pack_tree(tmp_path, uaem={"a.txt": comment})
    for name in ("l0", "l1"):
        try:
            os.symlink(str(tree), str(tree / name), target_is_directory=True)
        except (OSError, NotImplementedError):
            pytest.skip("cannot create directory symlinks here")
    calls = []
    listdir = os.listdir

    def counting_listdir(path):
        calls.append(path)
        assert len(calls) <= 50, "walked the symlink loop"
        return listdir(path)

    monkeypatch.setattr(os, "listdir", counting_listdir)
    imager = Imager()
    if comment == "short":
        imager.pack_begin(str(tree))
    else:
        with pytest.raises(FSError) as error:
            imager.pack_begin(str(tree))
        assert error.value.code == INVALID_COMMENT
    # the tree and sub, at most
    assert len(calls) <= 2


def fs_repack_check_flushes_test(tmp_path):
    # The comment check holds one path of the input volume at a time, as
    # repack does: a directory is flushed once it is checked.
    src = tmp_path / "src.adf"
    make_repack_image(src, DosType.DOS0, {"sub/b.txt": "b"})
    repacker = Repacker(str(src))
    assert repacker.create_in()
    repacker.check_comments()
    root = repacker.in_volume.get_root_dir()
    subs = [e for e in root.get_entries() if e.is_dir()]
    assert [e.entries for e in subs] == [None]
    # and repack reads it again
    assert [str(e.get_file_name().get_name()) for e in subs[0].get_entries()]
