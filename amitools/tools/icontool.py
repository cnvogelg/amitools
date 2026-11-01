import argparse
import os
import shutil
import sys
from typing import Optional, Tuple

from amitools.icon import IconError, IconFile


def _parse_pair(value: str, option: str) -> Tuple[int, int]:
    if "," not in value:
        raise ValueError("%s requires two comma-separated values" % option)
    first, second = value.split(",", 1)
    return int(first, 0), int(second, 0)


def _parse_field_value(value: str) -> int:
    stripped = value.strip()
    return int(stripped, 16 if stripped.lower().startswith("0x") else 10)


def _make_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Batch edit Amiga Workbench .info files: ToolTypes, icon position, "
            "structure fields, PNG import/export"
        )
    )
    parser.add_argument(
        "paths", nargs="+", help="Paths to .info files (or base names without .info)"
    )
    parser.add_argument(
        "--list", action="store_true", help="List metadata and ToolTypes"
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="With --list: dump all structure fields",
    )
    parser.add_argument("--get", metavar="KEY", help="Get a ToolType value")
    parser.add_argument("--set", metavar="KEY=VAL", help="Set or replace a ToolType")
    parser.add_argument("--set-flag", metavar="KEY", help="Set a boolean ToolType")
    parser.add_argument("--unset", metavar="KEY", help="Disable a boolean ToolType")
    parser.add_argument(
        "--delete", metavar="KEY", help="Delete all forms of a ToolType"
    )
    parser.add_argument(
        "--normalize", action="store_true", help="Remove duplicate and empty ToolTypes"
    )
    parser.add_argument(
        "--ignore-case",
        action="store_true",
        help="Match ToolType keys case-insensitively",
    )
    parser.add_argument("--pos", metavar="X,Y", help="Set icon placement")
    parser.add_argument("--winsize", metavar="W,H", help="Set drawer window size")
    parser.add_argument(
        "--edit",
        metavar="FIELD=VAL",
        action="append",
        help="Edit a structure field; may be repeated",
    )
    parser.add_argument("--export-icon", metavar="PATH", help="Export main icon to PNG")
    parser.add_argument(
        "--export-select-icon", metavar="PATH", help="Export selected icon to PNG"
    )
    parser.add_argument("--import-icon", metavar="PATH", help="Import PNG as main icon")
    parser.add_argument(
        "--import-select-icon", metavar="PATH", help="Import PNG as selected icon"
    )
    parser.add_argument(
        "--transparency",
        choices=["edge", "all", "none"],
        default="edge",
        help="PNG transparency mode",
    )
    parser.add_argument(
        "--planar", action="store_true", help="Force planar export instead of GlowIcons"
    )
    parser.add_argument(
        "-o", "--output", metavar="PATH", help="Write to a separate output file"
    )
    parser.add_argument(
        "--compact",
        action="store_true",
        help="Rebuild the file to compact its segments",
    )
    parser.add_argument(
        "--strict", action="store_true", help="Fail on suspicious lengths or bounds"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Show changes without writing the file"
    )
    parser.add_argument(
        "--backup",
        action="store_true",
        help="Create a .bak backup before an in-place write",
    )
    return parser


def _list_icon(path: str, icon: IconFile, verbose: bool) -> None:
    print("%s:" % path)
    if verbose:
        for line in icon.verbose_lines():
            print(line)
    else:
        summary = icon.summary()
        print("  type: %d (%s)" % (summary.icon_type, summary.type_name))
        print(
            "  version: %d, revision: %d, main_icons: %d"
            % (summary.version, summary.revision, summary.image_count)
        )
        print("  currentxy: %d,%d" % summary.position)
        print("  canvas: %dx%d" % summary.canvas_size)
        print(
            "  has_drawerdata: %s  has_defaulttool: %s  has_tooltypes: %s  "
            "has_toolwindow: %s"
            % (
                summary.has_drawer_data,
                summary.has_default_tool,
                summary.has_tool_types,
                summary.has_tool_window,
            )
        )
        entries = icon.tool_types.entries
        if summary.has_tool_types and entries:
            for entry in entries:
                print("  %s" % entry.raw)
        else:
            print("  (no tooltypes)")
    print()


def _get_tool_type(path: str, key: str, icon: IconFile, ignore_case: bool) -> None:
    entry = icon.tool_types.get_entry(key, ignore_case=ignore_case)
    if entry is None:
        print("%s: %s not set" % (path, key))
    else:
        value = (
            entry.value
            if entry.value is not None
            else ("false" if not entry.enabled else "true")
        )
        print("%s: %s=%s" % (path, key.strip("()"), value))


def _import_png(path: str, png_path: str, icon: IconFile, selected: bool) -> None:
    info = icon.import_png(png_path, selected=selected)
    print(
        "Mapping to %s palette, depth=%d, max_color_error=%d"
        % (info.palette, info.depth, info.max_color_error)
    )
    if info.has_transparent_pixels:
        print("Transparent pixels mapped to color 0 (background)")
    if info.max_color_error > 1000:
        print("Warning: significant color error - consider adjusting source image")
    label = "select icon" if selected else "main icon"
    print("%s: imported %s from %s" % (path, label, png_path))


def _report_operation_error(path: str, error: Exception) -> None:
    print("%s: ERROR: %s" % (path, error), file=sys.stderr)


def main(argv: Optional[list] = None) -> int:
    parser = _make_parser()
    args = parser.parse_args(argv)
    has_operation = any(
        (
            args.list,
            args.get,
            args.set,
            args.set_flag,
            args.unset,
            args.delete,
            args.normalize,
            args.pos,
            args.winsize,
            args.compact,
            args.edit,
            args.export_icon,
            args.export_select_icon,
            args.import_icon,
            args.import_select_icon,
        )
    )
    if not has_operation:
        parser.error("No operation specified")
    if args.output and len(args.paths) > 1:
        parser.error("--output can only be used with a single input file")
    if args.set and "=" not in args.set:
        parser.error("--set requires KEY=VAL")

    try:
        position = _parse_pair(args.pos, "--pos") if args.pos else None
        window_size = _parse_pair(args.winsize, "--winsize") if args.winsize else None
    except ValueError as error:
        parser.error(str(error))

    set_pair = tuple(args.set.split("=", 1)) if args.set else None
    exit_code = 0
    for path in args.paths:
        icon_path = path if path.lower().endswith(".info") else path + ".info"
        try:
            icon = IconFile.open(icon_path, strict=args.strict)
        except IconError as error:
            print("%s: ERROR: %s" % (icon_path, error), file=sys.stderr)
            exit_code = 2
            continue

        if args.list:
            _list_icon(icon_path, icon, args.verbose)
        if args.get:
            _get_tool_type(icon_path, args.get, icon, args.ignore_case)

        should_write = False
        if position is not None:
            try:
                icon.set_position(*position)
                should_write = True
            except IconError as error:
                _report_operation_error(icon_path, error)
                exit_code = max(exit_code, 1)

        if window_size is not None:
            if icon.drawer_data is None:
                print(
                    "%s: NOTE: --winsize ignored (no DrawerData in this icon)"
                    % icon_path
                )
            else:
                try:
                    icon.set_window_size(*window_size)
                    should_write = True
                except IconError as error:
                    _report_operation_error(icon_path, error)
                    exit_code = max(exit_code, 1)

        for edit_spec in args.edit or ():
            try:
                if "=" not in edit_spec:
                    raise ValueError("Invalid edit spec (missing '='): %s" % edit_spec)
                field_path, value = edit_spec.split("=", 1)
                icon.set_field(field_path.strip(), _parse_field_value(value))
                should_write = True
            except (IconError, ValueError) as error:
                _report_operation_error(icon_path, error)
                exit_code = max(exit_code, 1)

        for output_path, selected in (
            (args.export_icon, False),
            (args.export_select_icon, True),
        ):
            if output_path:
                try:
                    source = icon.export_png(
                        output_path,
                        selected=selected,
                        transparency=args.transparency,
                        force_planar=args.planar,
                    )
                except IconError as error:
                    _report_operation_error(icon_path, error)
                    exit_code = max(exit_code, 1)
                    continue
                label = "select icon" if selected else "main icon"
                if source == "glowicons":
                    print("  (exported from GlowIcons FORM ICON data)")
                print("%s: exported %s to %s" % (icon_path, label, output_path))

        for input_path, selected in (
            (args.import_icon, False),
            (args.import_select_icon, True),
        ):
            if input_path:
                try:
                    _import_png(icon_path, input_path, icon, selected)
                    should_write = True
                except IconError as error:
                    _report_operation_error(icon_path, error)
                    exit_code = max(exit_code, 1)

        tool_types_requested = any(
            (set_pair, args.set_flag, args.unset, args.delete, args.normalize)
        )
        if tool_types_requested:
            try:
                before_tool_types = icon.to_bytes()
                if set_pair:
                    icon.tool_types.set(*set_pair, ignore_case=args.ignore_case)
                if args.set_flag:
                    icon.tool_types.set_flag(
                        args.set_flag, ignore_case=args.ignore_case
                    )
                if args.unset:
                    icon.tool_types.unset(args.unset, ignore_case=args.ignore_case)
                if args.delete:
                    icon.tool_types.delete(args.delete, ignore_case=args.ignore_case)
                if args.normalize:
                    icon.tool_types.normalize(ignore_case=args.ignore_case)
                if icon.to_bytes() != before_tool_types:
                    should_write = True
            except IconError as error:
                _report_operation_error(icon_path, error)
                exit_code = max(exit_code, 1)

        try:
            new_data = icon.to_bytes(compact=args.compact)
        except IconError as error:
            print("%s: ERROR: %s" % (icon_path, error), file=sys.stderr)
            exit_code = 1
            continue
        if not should_write and not args.compact:
            continue
        if new_data == icon.original_bytes and not args.output:
            continue

        output_path = args.output or icon_path
        if args.dry_run:
            if args.output:
                print("%s: would write to %s" % (icon_path, output_path))
            else:
                print("%s: would update" % icon_path)
            continue
        if args.backup and not args.output:
            backup_path = icon_path + ".bak"
            if not os.path.exists(backup_path):
                shutil.copy2(icon_path, backup_path)
        try:
            icon.write(output_path, compact=args.compact)
        except IconError as error:
            print("%s: ERROR: %s" % (icon_path, error), file=sys.stderr)
            exit_code = 1
            continue
        if args.output:
            print("%s: wrote to %s" % (icon_path, output_path))
        else:
            print("%s: updated" % icon_path)

    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
