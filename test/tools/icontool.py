import struct

import pytest

from amitools.icon import IconFile, IconOperationError, ImageImportInfo
from amitools.tools.icontool import main


def make_icon(
    icon_type=3, tool_types=(), drawer_data=False, image_count=1
) -> bytes:
    data = bytearray(78)
    struct.pack_into(">H", data, 0, 0xE310)
    struct.pack_into(">H", data, 2, 1)
    struct.pack_into(">HH", data, 12, 16, 2)
    data[48] = icon_type
    struct.pack_into(">i", data, 58, 10)
    struct.pack_into(">i", data, 62, 20)
    struct.pack_into(">I", data, 74, 4096)
    if drawer_data:
        struct.pack_into(">I", data, 66, 1)
        drawer = bytearray(56)
        struct.pack_into(">HH", drawer, 4, 640, 480)
        struct.pack_into(">ii", drawer, 48, 30, 40)
        data.extend(drawer)
    if image_count == 2:
        struct.pack_into(">I", data, 26, 1)
    for _ in range(image_count):
        image = bytearray(24)
        struct.pack_into(">HHH", image, 4, 16, 2, 1)
        image[14] = 1
        data.extend(image)
    if tool_types:
        struct.pack_into(">I", data, 54, 1)
        data.extend(struct.pack(">I", 4 * (len(tool_types) + 1)))
        for item in tool_types:
            encoded = item.encode("latin-1")
            data.extend(struct.pack(">I", len(encoded)))
            data.extend(encoded)
    return bytes(data)


def icontool_lists_basic_and_verbose_metadata_test(tmp_path, capsys):
    icon_path = tmp_path / "ListMe.info"
    icon_path.write_bytes(make_icon(tool_types=("DONOTWAIT", "PUBSCREEN=Workbench")))

    assert main(["--list", str(icon_path)]) == 0
    basic = capsys.readouterr().out
    assert "type: 3 (tool)" in basic
    assert "currentxy: 10,20" in basic
    assert "PUBSCREEN=Workbench" in basic

    assert main(["--list", "-v", str(icon_path)]) == 0
    verbose = capsys.readouterr().out
    assert "DiskObject:StackSize=4096" in verbose
    assert 'ToolTypes[1]="PUBSCREEN=Workbench"' in verbose


def icontool_get_tooltypes_and_case_matching_test(tmp_path, capsys):
    icon_path = tmp_path / "Tool.info"
    icon_path.write_bytes(
        make_icon(tool_types=("PUBSCREEN=Workbench", "DONOTWAIT", "(QUIET)"))
    )

    assert main(["--get", "pubscreen", "--ignore-case", str(icon_path)]) == 0
    assert "pubscreen=Workbench" in capsys.readouterr().out
    assert main(["--get", "DONOTWAIT", str(icon_path)]) == 0
    assert "DONOTWAIT=true" in capsys.readouterr().out
    assert main(["--get", "QUIET", str(icon_path)]) == 0
    assert "QUIET=false" in capsys.readouterr().out
    assert main(["--get", "MISSING", str(icon_path)]) == 0
    assert "MISSING not set" in capsys.readouterr().out


def icontool_tooltype_operations_and_normalize_test(tmp_path):
    icon_path = tmp_path / "Tool.info"
    icon_path.write_bytes(
        make_icon(tool_types=("MODE=old", "OTHER=1", "MODE=new", ""))
    )

    assert main(
        [
            "--set",
            "PUBSCREEN=Workbench",
            "--set-flag",
            "DONOTWAIT",
            "--unset",
            "QUIET",
            "--delete",
            "OTHER",
            "--normalize",
            str(icon_path),
        ]
    ) == 0

    icon = IconFile.open(icon_path, strict=True)
    assert [entry.raw for entry in icon.tool_types.entries] == [
        "MODE=new",
        "PUBSCREEN=Workbench",
        "DONOTWAIT",
        "(QUIET)",
    ]


def icontool_position_field_and_drawer_options_test(tmp_path):
    path_without_extension = tmp_path / "Drawer"
    drawer_path = tmp_path / "Drawer.info"
    drawer_path.write_bytes(make_icon(icon_type=2, drawer_data=True))

    assert main(
        [
            "--pos=-5,0x20",
            "--winsize",
            "800,600",
            "--edit",
            "DiskObject:StackSize=8192",
            str(path_without_extension),
        ]
    ) == 0

    icon = IconFile.open(drawer_path, strict=True)
    assert icon.disk_object.position == (-5, 32)
    assert icon.window_size == (800, 600)
    assert icon.disk_object.stack_size == 8192


def icontool_winsize_skips_non_drawer_icons_test(tmp_path, capsys):
    icon_path = tmp_path / "Tool.info"
    original = make_icon()
    icon_path.write_bytes(original)

    assert main(["--winsize", "800,600", str(icon_path)]) == 0

    assert icon_path.read_bytes() == original
    assert "winsize ignored (no DrawerData" in capsys.readouterr().out


def icontool_batch_output_and_backup_test(tmp_path):
    first = tmp_path / "first.info"
    second = tmp_path / "second.info"
    output = tmp_path / "copy.info"
    original = make_icon()
    first.write_bytes(original)
    second.write_bytes(original)

    assert main(["--pos", "1,2", "--backup", str(first), str(second)]) == 0
    assert (tmp_path / "first.info.bak").read_bytes() == original
    assert (tmp_path / "second.info.bak").read_bytes() == original
    assert IconFile.open(first).disk_object.position == (1, 2)
    assert IconFile.open(second).disk_object.position == (1, 2)

    assert main(["--set-flag", "DONOTWAIT", "-o", str(output), str(first)]) == 0
    assert IconFile.open(first).tool_types.get("DONOTWAIT") is None
    assert IconFile.open(output, strict=True).tool_types.get("DONOTWAIT") == "true"


def icontool_dry_run_and_compact_test(tmp_path, capsys):
    icon_path = tmp_path / "Icon.info"
    original = make_icon(tool_types=("ONE=1", "TWO=2", "ONE=3"))
    icon_path.write_bytes(original)

    assert main(["--normalize", "--dry-run", str(icon_path)]) == 0
    assert icon_path.read_bytes() == original
    assert "would update" in capsys.readouterr().out

    assert main(["--normalize", str(icon_path)]) == 0
    assert [entry.raw for entry in IconFile.open(icon_path).tool_types.entries] == [
        "ONE=3",
        "TWO=2",
    ]
    assert main(["--compact", str(icon_path)]) == 0


def icontool_png_options_are_forwarded_test(tmp_path, capsys, monkeypatch):
    icon_path = tmp_path / "Icon.info"
    icon_path.write_bytes(make_icon(image_count=2))
    export_calls = []
    import_calls = []

    def export_png(_self, path, selected=False, transparency="edge", force_planar=False):
        export_calls.append((path, selected, transparency, force_planar))
        return "glowicons" if not selected else "planar"

    def import_png(_self, path, selected=False):
        import_calls.append((path, selected))
        return ImageImportInfo("WB2.0", 2, 100, True)

    monkeypatch.setattr(IconFile, "export_png", export_png)
    monkeypatch.setattr(IconFile, "import_png", import_png)

    assert main(
        [
            "--export-icon",
            "main.png",
            "--export-select-icon",
            "selected.png",
            "--import-icon",
            "replacement.png",
            "--import-select-icon",
            "replacement-selected.png",
            "--transparency",
            "all",
            "--planar",
            str(icon_path),
        ]
    ) == 0

    assert export_calls == [
        ("main.png", False, "all", True),
        ("selected.png", True, "all", True),
    ]
    assert import_calls == [("replacement.png", False), ("replacement-selected.png", True)]
    output = capsys.readouterr().out
    assert "exported from GlowIcons" in output
    assert "Mapping to WB2.0 palette" in output
    assert "Transparent pixels mapped to color 0" in output


def icontool_png_failures_set_partial_exit_code_test(
    tmp_path, capsys, monkeypatch
):
    icon_path = tmp_path / "Icon.info"
    icon_path.write_bytes(make_icon())

    def fail_export(_self, *_args, **_kwargs):
        raise IconOperationError("PNG export failed")

    monkeypatch.setattr(IconFile, "export_png", fail_export)

    assert main(["--export-icon", "main.png", str(icon_path)]) == 1
    assert "PNG export failed" in capsys.readouterr().err


def icontool_reports_input_and_operation_errors_test(tmp_path, capsys):
    valid_path = tmp_path / "Valid.info"
    invalid_path = tmp_path / "Invalid.info"
    valid_path.write_bytes(make_icon())
    invalid_path.write_bytes(b"not an icon")

    assert main(["--list", str(invalid_path), str(valid_path)]) == 2
    captured = capsys.readouterr()
    assert "ERROR: Not an Amiga icon" in captured.err
    assert "Valid.info:" in captured.out

    assert main(["--edit", "NoSuchField=1", str(valid_path)]) == 1
    assert "Unknown field path" in capsys.readouterr().err


@pytest.mark.parametrize(
    "args",
    [
        ["--set", "MISSING_EQUALS", "icon.info"],
        ["--pos", "1", "icon.info"],
        ["--winsize", "width,height", "icon.info"],
        ["--list", "-o", "out.info", "one.info", "two.info"],
        ["icon.info"],
    ],
)
def icontool_rejects_invalid_cli_arguments_test(args):
    with pytest.raises(SystemExit) as exc_info:
        main(args)
    assert exc_info.value.code == 2
