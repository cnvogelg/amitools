import os
import struct
from dataclasses import dataclass
from typing import List, Optional, Tuple, Union

from . import _format
from .errors import IconFieldError, IconFormatError, IconIOError, IconOperationError


PathLike = Union[str, os.PathLike]


@dataclass(frozen=True)
class ValidationIssue:
    severity: str
    message: str
    offset: Optional[int] = None


@dataclass(frozen=True)
class IconSummary:
    icon_type: int
    type_name: str
    version: int
    revision: int
    image_count: int
    position: Tuple[int, int]
    canvas_size: Tuple[int, int]
    has_drawer_data: bool
    has_default_tool: bool
    has_tool_types: bool
    has_tool_window: bool


@dataclass(frozen=True)
class ToolType:
    key: str
    value: Optional[str]
    enabled: bool
    raw: str

    @property
    def is_flag(self) -> bool:
        return self.value is None


@dataclass(frozen=True)
class IconImage:
    index: int
    width: int
    height: int
    depth: int


@dataclass(frozen=True)
class ImageImportInfo:
    palette: str
    depth: int
    max_color_error: int
    has_transparent_pixels: bool


class DiskObject:
    def __init__(self, owner: "IconFile"):
        self._owner = owner

    @property
    def icon_type(self) -> int:
        return self._owner._parsed.icon_type

    @property
    def type_name(self) -> str:
        return _format.icon_type_name(self.icon_type)

    @property
    def version(self) -> int:
        return self._owner._parsed.version

    @property
    def revision(self) -> int:
        return self._owner._parsed.revision

    @property
    def position(self) -> Tuple[int, int]:
        data = self._owner._parsed.data
        return (
            _format.be_i32(data, _format.OFF_CURRENTX),
            _format.be_i32(data, _format.OFF_CURRENTY),
        )

    @position.setter
    def position(self, value: Tuple[int, int]) -> None:
        self._owner.set_position(*value)

    @property
    def stack_size(self) -> int:
        return self._owner.get_field("DiskObject:StackSize")

    @stack_size.setter
    def stack_size(self, value: int) -> None:
        self._owner.set_field("DiskObject:StackSize", value)

    @property
    def canvas_size(self) -> Tuple[int, int]:
        data = self._owner._parsed.data
        return (
            _format.be_u16(data, _format.OFF_MAIN_CANVAS_W),
            _format.be_u16(data, _format.OFF_MAIN_CANVAS_H),
        )


class DrawerData:
    def __init__(self, owner: "IconFile"):
        self._owner = owner

    @property
    def window_size(self) -> Optional[Tuple[int, int]]:
        return self._owner.window_size

    @window_size.setter
    def window_size(self, value: Tuple[int, int]) -> None:
        self._owner.set_window_size(*value)

    @property
    def position(self) -> Tuple[int, int]:
        return (
            self._owner.get_field("DrawerData:CurrentX"),
            self._owner.get_field("DrawerData:CurrentY"),
        )

    @position.setter
    def position(self, value: Tuple[int, int]) -> None:
        self._owner.set_field("DrawerData:CurrentX", value[0])
        self._owner.set_field("DrawerData:CurrentY", value[1])


class DrawerData2:
    def __init__(self, owner: "IconFile"):
        self._owner = owner

    @property
    def flags(self) -> int:
        return self._owner.get_field("DrawerData2:Flags")

    @flags.setter
    def flags(self, value: int) -> None:
        self._owner.set_field("DrawerData2:Flags", value)

    @property
    def view_modes(self) -> int:
        return self._owner.get_field("DrawerData2:ViewModes")

    @view_modes.setter
    def view_modes(self, value: int) -> None:
        self._owner.set_field("DrawerData2:ViewModes", value)


class ToolTypes:
    def __init__(self, owner: "IconFile"):
        self._owner = owner

    @property
    def entries(self) -> Tuple[ToolType, ...]:
        result = []
        for raw in self._owner._parsed.tooltypes_raw_entries:
            text = _format.bytes_to_tt_str(raw)
            item = _format.parse_tt_item(text)
            result.append(
                ToolType(
                    key=item.key,
                    value=item.value,
                    enabled=not item.negated,
                    raw=text,
                )
            )
        return tuple(result)

    def get_entry(self, key: str, ignore_case: bool = False) -> Optional[ToolType]:
        found = None
        for entry in self.entries:
            if _format.key_eq(entry.key, _format.canon_key(key), ignore_case):
                found = entry
        return found

    def get(
        self, key: str, default: Optional[str] = None, ignore_case: bool = False
    ) -> Optional[str]:
        entry = self.get_entry(key, ignore_case=ignore_case)
        if entry is None:
            return default
        if entry.value is not None:
            return entry.value
        return "true" if entry.enabled else "false"

    def set(self, key: str, value: str, ignore_case: bool = False) -> None:
        self._apply(set_kv=(key, value), ignore_case=ignore_case)

    def set_flag(self, key: str, ignore_case: bool = False) -> None:
        self._apply(set_flag=key, ignore_case=ignore_case)

    def unset(self, key: str, ignore_case: bool = False) -> None:
        self._apply(unset_flag=key, ignore_case=ignore_case)

    def delete(self, key: str, ignore_case: bool = False) -> bool:
        existed = self.get_entry(key, ignore_case=ignore_case) is not None
        self._apply(delete=key, ignore_case=ignore_case)
        return existed

    def normalize(self, ignore_case: bool = False) -> bool:
        before = list(self._owner._parsed.tooltypes_raw_entries)
        self._apply(normalize=True, ignore_case=ignore_case)
        return before != self._owner._parsed.tooltypes_raw_entries

    def _apply(
        self,
        set_kv: Optional[Tuple[str, str]] = None,
        set_flag: Optional[str] = None,
        unset_flag: Optional[str] = None,
        delete: Optional[str] = None,
        normalize: bool = False,
        ignore_case: bool = False,
    ) -> None:
        parsed = self._owner._parsed
        if not parsed.has_tooltypes and parsed.icon_type != 3:
            raise IconOperationError("This icon cannot have ToolTypes")
        old_entries = list(parsed.tooltypes_raw_entries)
        old_has_tooltypes = parsed.has_tooltypes
        try:
            new_entries = _format.apply_tooltypes_ops(
                old_entries,
                op_set_kv=set_kv,
                op_set_flag=set_flag,
                op_unset_flag=unset_flag,
                op_del=delete,
                op_norm=normalize,
                ignore_case=ignore_case,
            )
        except (UnicodeError, ValueError) as error:
            raise IconOperationError(str(error)) from error
        parsed.tooltypes_raw_entries = new_entries
        parsed.has_tooltypes = bool(new_entries)
        if old_entries != new_entries or old_has_tooltypes != parsed.has_tooltypes:
            self._owner._tool_types_modified = True
        _format.put_be_i32(
            parsed.data,
            _format.OFF_TOOLTYPES_PRESENCE,
            1 if parsed.has_tooltypes else 0,
        )


class IconFile:
    def __init__(self, parsed: _format.ParsedIcon, source: Optional[bytes] = None):
        self._parsed = parsed
        self._tool_types_modified = False
        self._source = bytes(source) if source is not None else self.to_bytes()
        self.path: Optional[str] = None
        self.disk_object = DiskObject(self)
        self.tool_types = ToolTypes(self)

    @classmethod
    def open(cls, path: PathLike, strict: bool = False) -> "IconFile":
        path_string = os.fspath(path)
        try:
            with open(path_string, "rb") as icon_file:
                data = icon_file.read()
        except OSError as error:
            raise IconIOError(str(error)) from error
        icon = cls.from_bytes(data, strict=strict)
        icon.path = path_string
        return icon

    @classmethod
    def from_bytes(cls, data: bytes, strict: bool = False) -> "IconFile":
        source = bytes(data)
        try:
            parsed = _format.parse_icon_data(source, strict=strict)
        except (ValueError, IndexError, struct.error) as error:
            raise IconFormatError(str(error)) from error
        return cls(parsed, source=source)

    @property
    def images(self) -> Tuple[IconImage, ...]:
        result = []
        for index in range(self._parsed.num_main_icons):
            try:
                _, width, height, depth, _ = _format.get_icon_image_info(
                    self._parsed.main_icons_blob, index
                )
            except (ValueError, IndexError, struct.error) as error:
                raise IconFormatError(str(error)) from error
            result.append(IconImage(index, width, height, depth))
        return tuple(result)

    @property
    def has_glowicons(self) -> bool:
        return self._parsed.glowicons is not None

    @property
    def default_tool(self) -> Optional[str]:
        raw = self._parsed.defaulttool
        if raw is None:
            return None
        try:
            length = _format.be_u32(raw, 0)
        except struct.error as error:
            raise IconFormatError("Invalid DefaultTool data") from error
        return raw[4 : 4 + length].rstrip(b"\0").decode("latin-1", errors="replace")

    @property
    def drawer_data(self) -> Optional[DrawerData]:
        if not self._parsed.has_drawerdata:
            return None
        return DrawerData(self)

    @property
    def drawer_data2(self) -> Optional[DrawerData2]:
        if not self._parsed.has_drawerdata:
            return None
        return DrawerData2(self)

    @property
    def drawer_data_bytes(self) -> Optional[bytes]:
        return self._parsed.drawerdata

    @property
    def window_size(self) -> Optional[Tuple[int, int]]:
        drawer_data = self._parsed.drawerdata
        if drawer_data is None or len(drawer_data) < _format.DRAWERDATA_LEN:
            return None
        return (
            _format.be_u16(drawer_data, _format.DD_NEWWIN_WIDTH_OFF),
            _format.be_u16(drawer_data, _format.DD_NEWWIN_HEIGHT_OFF),
        )

    @property
    def original_bytes(self) -> bytes:
        return self._source

    @property
    def is_modified(self) -> bool:
        return self.to_bytes() != self._source

    def summary(self) -> IconSummary:
        return IconSummary(
            icon_type=self.disk_object.icon_type,
            type_name=self.disk_object.type_name,
            version=self.disk_object.version,
            revision=self.disk_object.revision,
            image_count=self._parsed.num_main_icons,
            position=self.disk_object.position,
            canvas_size=self.disk_object.canvas_size,
            has_drawer_data=self._parsed.has_drawerdata,
            has_default_tool=self._parsed.has_defaulttool,
            has_tool_types=self._parsed.has_tooltypes,
            has_tool_window=self._parsed.has_toolwindow,
        )

    def get_field(self, path: str) -> int:
        field, structure, base_offset = _format.find_field_by_path(path)
        if field is None:
            raise IconFieldError("Unknown field path: %s" % path)
        buffer, offset = self._field_buffer(
            structure, field, base_offset, path, create=False
        )
        field_at_offset = _format.FieldDef(
            offset, field.size, field.signed, field.name, field.fmt
        )
        try:
            return _format.read_field(buffer, field_at_offset)
        except (IndexError, struct.error) as error:
            raise IconFieldError(
                "Field is outside the available data: %s" % path
            ) from error

    def set_field(self, path: str, value: int) -> None:
        field, structure, base_offset = _format.find_field_by_path(path)
        if field is None:
            raise IconFieldError("Unknown field path: %s" % path)
        try:
            integer = int(value)
        except (TypeError, ValueError) as error:
            raise IconFieldError("Field value must be an integer") from error
        if field.signed:
            minimum = -(1 << (field.size * 8 - 1))
            maximum = (1 << (field.size * 8 - 1)) - 1
        else:
            minimum = 0
            maximum = (1 << (field.size * 8)) - 1
        if integer < minimum or integer > maximum:
            raise IconFieldError("Value out of range for %s: %d" % (path, integer))
        buffer, offset = self._field_buffer(
            structure, field, base_offset, path, create=True
        )
        try:
            _format.write_field(buffer, offset, field.size, field.signed, integer)
        except (IndexError, struct.error, ValueError) as error:
            raise IconFieldError(str(error)) from error
        if structure in ("DrawerData", "NewWindow"):
            self._parsed.drawerdata = bytes(buffer)
        elif structure == "DrawerData2":
            self._parsed.drawerdata2 = bytes(buffer)
        elif structure in ("Icon", "IconSelect"):
            self._parsed.main_icons_blob = bytes(buffer)

    def set_position(self, x: int, y: int) -> None:
        try:
            _format.set_current_xy(self._parsed, x, y)
        except (IndexError, struct.error, ValueError) as error:
            raise IconOperationError(str(error)) from error

    def set_window_size(self, width: int, height: int) -> None:
        try:
            if not _format.set_drawer_winsize(self._parsed, width, height):
                raise IconOperationError("This icon has no DrawerData")
        except ValueError as error:
            raise IconOperationError(str(error)) from error

    def export_png(
        self,
        path: PathLike,
        selected: bool = False,
        transparency: str = "edge",
        force_planar: bool = False,
    ) -> str:
        try:
            return _format.export_icon_to_png(
                self._parsed,
                1 if selected else 0,
                os.fspath(path),
                transparency=transparency,
                force_planar=force_planar,
            )
        except (OSError, RuntimeError, ValueError) as error:
            raise IconOperationError(str(error)) from error

    def import_png(self, path: PathLike, selected: bool = False) -> ImageImportInfo:
        try:
            info = _format.import_png_to_icon(
                self._parsed, 1 if selected else 0, os.fspath(path)
            )
        except (OSError, RuntimeError, ValueError) as error:
            raise IconOperationError(str(error)) from error
        return ImageImportInfo(*info)

    def validate(self) -> List[ValidationIssue]:
        try:
            _format.parse_icon_data(self.to_bytes(), strict=True)
        except (IconFormatError, ValueError, IndexError, struct.error) as error:
            return [ValidationIssue("error", str(error))]
        return []

    def to_bytes(self, compact: bool = False) -> bytes:
        try:
            new_tooltypes = (
                self._parsed.tooltypes_raw_entries
                if self._tool_types_modified
                else None
            )
            return _format.rebuild_file(
                self._parsed, new_tooltypes=new_tooltypes, compact=compact
            )
        except (ValueError, IndexError, struct.error) as error:
            raise IconFormatError(str(error)) from error

    def write(self, path: Optional[PathLike] = None, compact: bool = False) -> None:
        target = os.fspath(path) if path is not None else self.path
        if target is None:
            raise IconIOError("No output path specified")
        data = self.to_bytes(compact=compact)
        try:
            with open(target, "wb") as icon_file:
                icon_file.write(data)
        except OSError as error:
            raise IconIOError(str(error)) from error
        self.path = target
        self._source = data
        self._tool_types_modified = False

    def verbose_lines(self) -> List[str]:
        parsed = self._parsed
        lines: List[str] = []

        def append_fields(prefix: str, buffer: bytes, fields: list) -> None:
            for field in fields:
                if field.offset + field.size <= len(buffer):
                    value = _format.read_field(buffer, field)
                    lines.append(
                        "%s:%s=%s"
                        % (prefix, field.name, _format.format_field(field, value))
                    )

        for field in _format.DISKOBJECT_FIELDS:
            value = _format.read_field(parsed.data, field)
            lines.append(
                "DiskObject:%s=%s" % (field.name, _format.format_field(field, value))
            )

        append_fields(
            "DiskObject:Gadget",
            parsed.data[_format.OFF_GADGET : _format.OFF_GADGET + _format.GADGET_LEN],
            _format.GADGET_FIELDS,
        )
        if parsed.has_drawerdata and parsed.drawerdata:
            append_fields(
                "DrawerData:NewWindow", parsed.drawerdata, _format.NEWWINDOW_FIELDS
            )
            append_fields("DrawerData", parsed.drawerdata, _format.DRAWERDATA_FIELDS)

        offset = 0
        for index in range(parsed.num_main_icons):
            if offset + 20 <= len(parsed.main_icons_blob):
                name = "Icon" if index == 0 else "IconSelect"
                append_fields(
                    name, parsed.main_icons_blob[offset:], _format.IMAGE_FIELDS
                )
                offset += _format.get_main_icon_size(
                    parsed.main_icons_blob, offset, strict=False
                )

        if parsed.has_defaulttool and parsed.defaulttool:
            lines.append('DefaultTool="%s"' % (self.default_tool or ""))
        for index, entry in enumerate(parsed.tooltypes_raw_entries):
            lines.append('ToolTypes[%d]="%s"' % (index, _format.bytes_to_tt_str(entry)))
        if parsed.drawerdata2:
            append_fields("DrawerData2", parsed.drawerdata2, _format.DRAWERDATA2_FIELDS)
        elif parsed.has_drawerdata and parsed.revision >= 1:
            lines.append("DrawerData2: (expected but not found in file)")
        return lines

    def _field_buffer(
        self,
        structure: str,
        field: _format.FieldDef,
        base_offset: int,
        path: str,
        create: bool,
    ) -> Tuple[bytearray, int]:
        parsed = self._parsed
        if structure in ("DiskObject", "Gadget"):
            return parsed.data, base_offset + field.offset
        if structure in ("DrawerData", "NewWindow"):
            if not parsed.has_drawerdata or parsed.drawerdata is None:
                raise IconFieldError("No DrawerData in this icon: %s" % path)
            return bytearray(parsed.drawerdata), field.offset
        if structure == "DrawerData2":
            if not parsed.has_drawerdata:
                raise IconFieldError("No DrawerData in this icon: %s" % path)
            if parsed.drawerdata2 is None:
                data = bytearray(_format.DRAWERDATA2_LEN)
            else:
                data = bytearray(parsed.drawerdata2)
            if len(data) < _format.DRAWERDATA2_LEN:
                data.extend(bytes(_format.DRAWERDATA2_LEN - len(data)))
            if create and parsed.revision != 1:
                parsed.revision = 1
                parsed.data[_format.OFF_ICON_REVISION + 3] = 1
            return data, field.offset
        if structure in ("Icon", "IconSelect"):
            if not parsed.main_icons_blob:
                raise IconFieldError("No icon images in this file")
            offset = 0
            if structure == "IconSelect":
                if parsed.num_main_icons < 2:
                    raise IconFieldError("No select icon in this file")
                offset = _format.get_main_icon_size(
                    parsed.main_icons_blob, 0, strict=False
                )
            return bytearray(parsed.main_icons_blob), offset + field.offset
        raise IconFieldError("Unsupported field path: %s" % path)
