import struct

import pytest

from amitools.icon import IconFieldError, IconFile, IconFormatError


def make_icon() -> bytes:
    data = bytearray(78 + 24)
    struct.pack_into(">H", data, 0, 0xE310)
    struct.pack_into(">H", data, 2, 1)
    struct.pack_into(">HH", data, 12, 16, 2)
    data[48] = 3
    struct.pack_into(">i", data, 58, 10)
    struct.pack_into(">i", data, 62, 20)
    struct.pack_into(">I", data, 74, 4096)
    image = 78
    struct.pack_into(">HHH", data, image + 4, 16, 2, 1)
    data[image + 14] = 1
    return bytes(data)


def make_drawer_icon() -> bytes:
    basic = make_icon()
    data = bytearray(basic[:78] + bytes(56) + basic[78:])
    data[48] = 2
    struct.pack_into(">I", data, 66, 1)
    struct.pack_into(">HH", data, 78 + 4, 640, 480)
    struct.pack_into(">ii", data, 78 + 48, 30, 40)
    return bytes(data)


def icon_file_round_trip_and_summary_test():
    source = make_icon()
    icon = IconFile.from_bytes(source, strict=True)

    assert icon.to_bytes() == source
    assert icon.disk_object.position == (10, 20)
    assert icon.disk_object.stack_size == 4096
    assert icon.summary().type_name == "tool"
    assert icon.images[0].width == 16
    assert icon.images[0].height == 2
    assert icon.validate() == []


def icon_file_edits_fields_and_tooltypes_test():
    icon = IconFile.from_bytes(make_icon(), strict=True)

    icon.disk_object.position = (100, 200)
    icon.disk_object.stack_size = 8192
    icon.tool_types.set("PUBSCREEN", "Workbench")
    icon.tool_types.set_flag("DONOTWAIT")

    reopened = IconFile.from_bytes(icon.to_bytes(), strict=True)
    assert reopened.disk_object.position == (100, 200)
    assert reopened.disk_object.stack_size == 8192
    assert reopened.tool_types.get("PUBSCREEN") == "Workbench"
    assert reopened.tool_types.get("DONOTWAIT") == "true"


def icon_file_field_paths_support_image_headers_test():
    icon = IconFile.from_bytes(make_icon(), strict=True)

    icon.set_field("Icon:Width", 15)

    assert icon.get_field("Icon:Width") == 15
    assert IconFile.from_bytes(icon.to_bytes(), strict=True).images[0].width == 15
    with pytest.raises(IconFieldError):
        icon.set_field("DiskObject:StackSize", 1 << 40)


def icon_file_rejects_non_icon_data_test():
    with pytest.raises(IconFormatError):
        IconFile.from_bytes(b"not an icon")


def icon_file_writes_and_manages_tooltypes_test(tmp_path):
    source_path = tmp_path / "Source.info"
    output_path = tmp_path / "Output.info"
    source_path.write_bytes(make_icon())
    icon = IconFile.open(source_path, strict=True)

    icon.tool_types.set("MODE", "old")
    icon.tool_types.set("MODE", "new")
    icon.tool_types.set_flag("DONOTWAIT")
    icon.tool_types.unset("DONOTWAIT")
    assert icon.tool_types.get("MODE") == "new"
    assert icon.tool_types.get("DONOTWAIT") == "false"
    assert icon.tool_types.delete("MODE") is True
    assert icon.tool_types.get("MODE") is None

    icon.write(output_path)
    assert source_path.read_bytes() == make_icon()
    assert IconFile.open(output_path, strict=True).tool_types.get("DONOTWAIT") == "false"


def icon_file_drawer_data_models_test():
    icon = IconFile.from_bytes(make_drawer_icon(), strict=True)

    assert icon.drawer_data.window_size == (640, 480)
    assert icon.drawer_data.position == (30, 40)
    icon.drawer_data.window_size = (800, 600)
    icon.drawer_data.position = (50, 60)
    icon.drawer_data2.view_modes = 2

    reopened = IconFile.from_bytes(icon.to_bytes(), strict=True)
    assert reopened.drawer_data.window_size == (800, 600)
    assert reopened.drawer_data.position == (50, 60)
    assert reopened.drawer_data2.view_modes == 2

