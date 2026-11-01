########
icontool
########

*command-line tool for reading and modifying Amiga Workbench ``.info`` icon files*

************
Introduction
************

The ``icontool`` is a small command line utility for inspecting and modifying
Amiga Workbench icon files. It can read structure fields, edit any stored value
by path, change ToolType entries, export imported PNG graphics, work on multiple
icons in a single invocation and preserve GlowIcons and NewIcons metadata.

Features
========

* inspect icon metadata, structure fields and ToolTypes
* edit any structure field using path notation
* modify ToolTypes with key based operations
* export embedded icons to PNG files
* import PNG files as icon graphics
* batch process multiple files in one command
* preserve GlowIcons and NewIcons data
* use a non-destructive workflow with a separate output file option

Installation
============

``icontool`` requires Python 3.9 or newer. No additional dependencies are
required for basic operations.

For PNG import/export support install ``pypng``::

  > pip install pypng

*****
Usage
*****

::

  icontool [options] <file.info> [file2.info ...]

Files can be given either with or without the ``.info`` extension.

Python Library
==============

Icon parsing and editing are also available through the ``amitools.icon``
package. The command line tool is a thin interface over this API.

Open an icon from a path or a byte string, inspect typed data, modify fields or
ToolTypes, and serialize it again::

  from amitools.icon import IconFile

  icon = IconFile.open("MyIcon.info")
  print(icon.disk_object.icon_type)
  print(icon.disk_object.position)
  print(icon.tool_types.get("PUBSCREEN"))

  icon.disk_object.position = (100, 200)
  icon.tool_types.set("PUBSCREEN", "Workbench")
  icon.write("Modified.info")

Use ``IconFile.from_bytes(data)`` and ``icon.to_bytes()`` to work entirely with
in-memory data. The API also provides ``get_field(path)`` and
``set_field(path, value)`` for structure fields, ``icon.images`` for image
dimensions, mutable ``drawer_data`` and ``drawer_data2`` views for drawer
icons, and ``icon.validate()`` for strict structural validation. ToolType
operations are available through ``icon.tool_types``.
Library failures raise ``IconError`` subclasses rather than printing messages.

Inspecting Icons
================

``--list`` - Display basic icon information
-------------------------------------------

::

  icontool --list MyIcon.info

This command prints a compact summary of the icon, including type, revision,
current position, canvas size, and the ToolTypes stored in the file.

Example output::

  MyIcon.info:
    type: 3 (tool)
    version: 1, revision: 0, main_icons: 2
    currentxy: 100,50
    canvas: 48x32
    has_drawerdata: False  has_defaulttool: True  has_tooltypes: True
    DONOTWAIT
    TOOLPRI=0

``--list -v`` - Verbose structure dump
--------------------------------------

::

  icontool --list -v MyIcon.info

This mode shows the full icon structure with path-like field names, which is
helpful for manual editing and debugging.

Example output::

  MyIcon.info:
  DiskObject:Magic=0xE310 (valid)
  DiskObject:Version=1
  DiskObject:Type=3 (WBTOOL)
  DiskObject:CurrentX=100
  DiskObject:CurrentY=50
  DiskObject:StackSize=4096
  DiskObject:Gadget:LeftEdge=0
  DiskObject:Gadget:TopEdge=0
  DiskObject:Gadget:Width=48
  DiskObject:Gadget:Height=32
  DiskObject:Gadget:Flags=0x5
  DiskObject:Gadget:UserData=0 (OS1.x)
  Icon:Width=48
  Icon:Height=32
  Icon:Depth=2
  IconSelect:Width=48
  IconSelect:Height=32
  IconSelect:Depth=2
  DefaultTool="SYS:Tools/IconEdit"
  ToolTypes[0]="DONOTWAIT"
  ToolTypes[1]="TOOLPRI=0"

Editing Structure Fields
========================

Use ``--edit`` with path notation to modify any field.

Examples::

  # Set icon position
  icontool --edit "DiskObject:CurrentX=200" --edit "DiskObject:CurrentY=100" MyIcon.info

  # Change stack size
  icontool --edit "DiskObject:StackSize=8192" MyIcon.info

  # Modify gadget dimensions
  icontool --edit "DiskObject:Gadget:Width=64" --edit "DiskObject:Gadget:Height=48" MyIcon.info

The fields use path-like names. Common groups are:

``DiskObject``
  main icon header

* ``DiskObject:Magic``
* ``DiskObject:Version``
* ``DiskObject:Type``
* ``DiskObject:CurrentX`` and ``DiskObject:CurrentY``
* ``DiskObject:StackSize``
* ``DiskObject:DefaultTool`` and ``DiskObject:ToolTypes``
* ``DiskObject:DrawerData`` and ``DiskObject:ToolWindow``

``DiskObject:Gadget``
  embedded gadget parameters

* ``DiskObject:Gadget:LeftEdge`` and ``TopEdge``
* ``DiskObject:Gadget:Width`` and ``Height``
* ``DiskObject:Gadget:Flags`` and ``Activation``
* ``DiskObject:Gadget:GadgetRender`` and ``SelectRender``
* ``DiskObject:Gadget:UserData``

``DrawerData:NewWindow``
  for disk or drawer icons

* ``DrawerData:NewWindow:LeftEdge``, ``TopEdge``
* ``DrawerData:NewWindow:Width``, ``Height``
* ``DrawerData:NewWindow:MinWidth``, ``MinHeight``
* ``DrawerData:NewWindow:MaxWidth``, ``MaxHeight``
* ``DrawerData:NewWindow:DetailPen``, ``BlockPen``
* ``DrawerData:NewWindow:Flags`` and ``IDCMPFlags``

``DrawerData``
  drawer icon positions

* ``DrawerData:CurrentX`` and ``DrawerData:CurrentY``

``DrawerData2``
  OS 2.x extended drawer data

* ``DrawerData2:Flags``
* ``DrawerData2:ViewModes``

``Icon`` / ``IconSelect``
  image metadata for the main and selected icon

* ``Icon:LeftEdge``, ``TopEdge``
* ``Icon:Width``, ``Height``
* ``Icon:Depth``
* ``Icon:PlanePick``, ``PlaneOnOff``
* ``IconSelect:*`` uses the same fields for the selected icon

ToolTypes Operations
====================

``--get`` - Read a ToolType value
---------------------------------

::

  icontool --get PUBSCREEN MyIcon.info
  # Output: MyIcon.info: PUBSCREEN=Workbench

  icontool --get DONOTWAIT MyIcon.info
  # Output: MyIcon.info: DONOTWAIT=true

``--set`` - Set a key=value ToolType
------------------------------------

::

  icontool --set "PUBSCREEN=MyScreen" MyIcon.info

``--set-flag`` - Enable a boolean flag
--------------------------------------

::

  icontool --set-flag DONOTWAIT MyIcon.info

``--unset`` - Disable a boolean flag without removing it
---------------------------------------------------------

This writes ``(FLAGNAME)`` to disable the flag while keeping the ToolType
entry present::

  icontool --unset DONOTWAIT MyIcon.info

``--delete`` - Remove a ToolType completely
-------------------------------------------

This removes all forms of the ToolType: ``KEY``, ``KEY=value`` and ``(KEY)``::

  icontool --delete PUBSCREEN MyIcon.info

``--ignore-case`` - Case-insensitive matching
---------------------------------------------

::

  icontool --get pubscreen --ignore-case MyIcon.info

``--normalize`` - Remove duplicates and empty ToolTypes
-------------------------------------------------------

::

  icontool --normalize MyIcon.info

This removes duplicates, with the last value winning, and drops empty entries.

Icon Position and Window Size
=============================

``--pos`` - Set the icon position
---------------------------------

::

  icontool --pos 100,200 MyIcon.info

``--winsize`` - Set the drawer window size
------------------------------------------

For disk or drawer icons only::

  icontool --winsize 640,480 MyIcon.info

PNG Export
==========

``--export-icon`` - Export the main icon
----------------------------------------

::

  icontool --export-icon icon.png MyIcon.info

``--export-select-icon`` - Export the selected icon
----------------------------------------------------

::

  icontool --export-select-icon icon_select.png MyIcon.info

Export both icons at once::

  icontool --export-icon main.png --export-select-icon select.png MyIcon.info

GlowIcons Support
-----------------

When an icon contains GlowIcons data (FORM ICON), ``icontool`` automatically
exports the higher quality GlowIcons image instead of the traditional planar
image. GlowIcons support includes:

* IMAG chunks (palette-mapped compressed images)
* ARGB chunks (OS 4 true-color images)
* proper transparency information from the icon data

To force export of the traditional planar image::

  icontool --planar --export-icon icon.png MyIcon.info

Transparency Options
--------------------

Control how transparency is handled for planar images::

  # Edge-connected transparency (default)
  icontool --transparency=edge --export-icon icon.png MyIcon.info

  # All color 0 pixels transparent
  icontool --transparency=all --export-icon icon.png MyIcon.info

  # No transparency
  icontool --transparency=none --export-icon icon.png MyIcon.info

The default edge mode keeps only color 0 pixels connected to the image border
transparent. This is useful for icons that use gray or black as inner fill
colors.

PNG Import
==========

``--import-icon`` - Import a PNG as the main icon
--------------------------------------------------

::

  icontool --import-icon newicon.png MyIcon.info

``--import-select-icon`` - Import a PNG as the selected icon
------------------------------------------------------------

::

  icontool --import-select-icon newicon_sel.png MyIcon.info

The import process does the following:

#. reads the PNG file (RGB and RGBA are supported)
#. treats transparent pixels as color 0 background
#. quantizes the icon to Workbench palette variants
#. chooses the palette with the lowest color error
#. picks the minimum required bit depth (1-4 planes)
#. updates gadget dimensions if the imported icon is larger

RGBA PNG files with transparency are fully supported. Transparent pixels become
background color 0 and semi-transparent pixels with alpha below 128 are treated
as transparent.

Output Options
==============

``-o`` / ``--output`` - Write to a separate file instead of modifying the original
-----------------------------------------------------------------------------------

::

  icontool --edit "DiskObject:StackSize=8192" -o modified.info original.info

This is the non-destructive workflow.

``--dry-run`` - Preview changes without writing them
------------------------------------------------------

::

  icontool --edit "DiskObject:CurrentX=100" --dry-run MyIcon.info

This prints a message such as ``MyIcon.info: would update`` without changing the
file.

``--backup`` - Create a backup before writing
---------------------------------------------

::

  icontool --edit "DiskObject:CurrentX=100" --backup MyIcon.info

The backup is written once per file, e.g. ``MyIcon.info.bak``.

``--compact`` - Rebuild the file structure
------------------------------------------

::

  icontool --compact MyIcon.info

This removes gaps in the ToolTypes table and rebuilds the file structure.

``--strict`` - Fail fast on suspicious data
-------------------------------------------

::

  icontool --strict --list MyIcon.info

Batch Processing
================

Process multiple files in one command::

  # Set position on all icons
  icontool --pos 50,50 *.info

  # List all icons
  icontool --list Icons/*.info

  # Normalize ToolTypes across a project
  icontool --normalize --backup Project/#?.info

Note that ``--output`` cannot be used together with multiple input files.

Examples
========

Create a tool icon workflow::

  icontool \
    --edit "DiskObject:StackSize=16384" \
    --set "PUBSCREEN=Workbench" \
    --set-flag DONOTWAIT \
    --delete TOOLPRI \
    --import-icon mytool.png \
    -o MyTool.info \
    Template.info

Inspect and fix icon positions::

  icontool --list *.info | grep currentxy
  icontool --pos 0x80000000,0x80000000 *.info

Export icons for editing::

  icontool --export-icon temp.png MyIcon.info
  # edit temp.png in an image editor
  icontool --import-icon temp.png MyIcon.info

Edit drawer view modes::

  icontool --edit "DrawerData2:ViewModes=2" MyDrawer.info
  icontool --list -v MyDrawer.info | grep DrawerData2

Compare GlowIcons and planar export::

  icontool --export-icon glow.png MyIcon.info
  icontool --planar --export-icon planar.png MyIcon.info
  icontool --planar --transparency=edge --export-icon edge.png MyIcon.info
  icontool --planar --transparency=all --export-icon all.png MyIcon.info

File Format Notes
=================

``icontool`` handles standard Amiga ``.info`` files including:

* ``DiskObject`` header (78 bytes)
* ``DrawerData`` for disk or drawer icons (56 bytes)
* ``DrawerData2`` OS 2.x extension (6 bytes: ``dd_Flags`` + ``dd_ViewModes``)
* image structures with planar bitmap data
* ``DefaultTool`` strings
* ``ToolTypes`` string arrays
* GlowIcons FORM ICON data (parsed for export and preserved on modification)
* NewIcons ToolTypes data (preserved but not parsed)

GlowIcons Format
----------------

GlowIcons (OS 3.5+) append IFF FORM ICON data after the traditional icon:

* ``FACE`` chunk: icon dimensions and flags
* ``IMAG`` chunk: palette-mapped image with RLE compression
* ``ARGB`` chunk: OS4 true-color ARGB image data

Note that the ``IMAG`` chunk stores IMAGE data before the COLORMAP data, which
is not the most intuitive ordering.

Supported icon types:

* ``WBDISK`` (1): disk or volume icon
* ``WBDRAWER`` (2): drawer or directory icon
* ``WBTOOL`` (3): executable tool
* ``WBPROJECT`` (4): project or document icon
* ``WBGARBAGE`` (5): trashcan
* ``WBDEVICE`` (6): device icon
* ``WBKICK`` (7): Kickstart disk
* ``WBAPPICON`` (8): application icon

Exit Codes
==========

* ``0`` - success
* ``1`` - partial failure (some operations failed)
* ``2`` - file read or parse error

License
=======

See the repository ``LICENSE`` file.
