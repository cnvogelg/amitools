#####################
amitools.icon Library
#####################

*Python library for reading and modifying Amiga Workbench ``.info`` icon files*

************
Introduction
************

The ``amitools.icon`` package provides a Python API for parsing, inspecting,
modifying, and writing Amiga Workbench icon files. It exposes the icon's
DiskObject fields, image metadata, drawer data, and ToolTypes without requiring
callers to use the ``icontool`` command-line interface.

The main entry point is :class:`IconFile`. It can read an icon
from a filesystem path or in-memory bytes, expose typed views of common
structures, and serialize changes back to bytes or a file. The library raises
typed exceptions instead of printing errors or choosing command-line exit
codes.

The :doc:`command-line guide <../tools/icontool>` describes the ``icontool``
program, which uses this library.

************
Installation
************

Install ``amitools`` from PyPI::

  python -m pip install amitools

PNG import and export use the optional ``pypng`` package. Install it to enable
those operations::

  python -m pip install pypng

************
Quick start
************

Open an icon, inspect it, make changes, and write the result to a new file::

  from amitools.icon import IconFile

  icon = IconFile.open("MyIcon.info")
  print(icon.disk_object.type_name)
  print(icon.disk_object.position)
  print(icon.tool_types.get("PUBSCREEN"))

  icon.disk_object.position = (100, 200)
  icon.tool_types.set("PUBSCREEN", "Workbench")
  icon.write("Modified.info")

To keep the data in memory, use :meth:`IconFile.from_bytes` and
:meth:`IconFile.to_bytes` instead of opening or writing a path.

**********
API guide
**********

Opening and saving
==================

.. py:class:: IconFile

   Represents one parsed icon file. Import it from ``amitools.icon``.

   .. py:classmethod:: open(path, strict=False)

      Read an icon from a path and return an ``IconFile``. The path is retained
      on the instance, so calling :meth:`IconFile.write` without a path writes
      back to that file.

      Set ``strict=True`` to request strict parsing and validation of the input.

   .. py:classmethod:: from_bytes(data, strict=False)

      Parse an in-memory byte string and return an ``IconFile``. The instance
      has no associated path; provide one when calling :meth:`IconFile.write`.

   .. py:method:: to_bytes(compact=False)

      Serialize the current icon and return its bytes. Set ``compact=True`` to
      rebuild the file using the compact serialization mode.

   .. py:method:: write(path=None, compact=False)

      Serialize and write the icon. If ``path`` is omitted, write to the path
      used by :meth:`IconFile.open`; an icon created with
      :meth:`IconFile.from_bytes` requires an explicit path. After a successful
      write, the instance's path and original bytes are updated.

   .. py:method:: summary()

      Return an :class:`IconSummary` of the icon's metadata and presence flags.

   .. py:method:: get_field(path)

      Return the integer value of a structure field identified by its path.

   .. py:method:: set_field(path, value)

      Set the integer value of a structure field identified by its path.

   .. py:method:: set_position(x, y)

      Set the icon's current position.

   .. py:method:: set_window_size(width, height)

      Set the drawer window size. Raise :class:`IconOperationError` if the icon
      has no DrawerData.

   .. py:method:: validate()

      Return an empty list when the serialized data is valid, or a list of
      :class:`ValidationIssue` values otherwise.

   .. py:method:: export_png(path, selected=False, transparency="edge", force_planar=False)

      Export the main or selected image as a PNG file.

   .. py:method:: import_png(path, selected=False)

      Import a PNG into the main or selected image and return
      :class:`ImageImportInfo`.

   .. py:attribute:: path

      The path associated with the icon, or ``None`` if it was created from
      bytes and has not been written to a path.

   .. py:attribute:: disk_object

      A :class:`DiskObject` view of the main icon header.

   .. py:attribute:: tool_types

      A :class:`ToolTypes` view of the icon's ToolTypes.

   .. py:attribute:: images

      A tuple of :class:`IconImage` values, one for each main and selected
      image.

   .. py:attribute:: default_tool

      The default tool string, or ``None`` when absent.

   .. py:attribute:: has_glowicons

      Whether the icon contains GlowIcons data.

   .. py:attribute:: drawer_data

      A :class:`DrawerData` view for drawer icons, or ``None`` when absent.

   .. py:attribute:: drawer_data2

      A :class:`DrawerData2` view for extended drawer data, or ``None`` when
      absent.

   .. py:attribute:: window_size

      The drawer window size as an ``(width, height)`` tuple, or ``None`` when
      unavailable.

   .. py:attribute:: drawer_data_bytes

      The raw DrawerData bytes, or ``None`` when absent.

   .. py:attribute:: original_bytes

      The original serialized data. This value is updated after a successful
      :meth:`write`.

   .. py:attribute:: is_modified

      ``True`` when the current serialized data differs from the original
      bytes.

Inspecting icon data
====================

The following properties are available on :class:`IconFile`:

``disk_object``
  A :class:`DiskObject` view of the main icon header. Its ``icon_type``,
  ``type_name``, ``version``, ``revision``, and ``canvas_size`` properties
  describe the icon. ``position`` is an ``(x, y)`` tuple and can also be set.
  ``stack_size`` can be read or set.

``summary()``
  Return an :class:`IconSummary` with the icon type and name, version and
  revision, image count, position, canvas size, and presence flags for drawer
  data, the default tool, ToolTypes, and the tool window.

``images``
  A tuple of :class:`IconImage` values, one per main and selected image. Each
  value has ``index``, ``width``, ``height``, and ``depth`` attributes.

``default_tool``
  The default tool string, or ``None`` if the icon does not contain one.

``has_glowicons``
  Whether the icon contains GlowIcons data.

``drawer_data`` and ``drawer_data2``
  Optional views for drawer icons. ``drawer_data`` exposes ``position`` and
  ``window_size``; ``drawer_data2`` exposes ``flags`` and ``view_modes``.
  These properties are ``None`` when the icon has no drawer data.

``window_size``
  The drawer window size as an ``(width, height)`` tuple, or ``None`` when it
  is unavailable. It can also be set with :meth:`IconFile.set_window_size`.

``drawer_data_bytes``
  The raw DrawerData bytes, or ``None`` when absent.

The public data classes are:

.. py:class:: DiskObject

   Typed view exposing icon type, version, revision, canvas size, stack size,
   and current position. Position and stack size can be changed through this
   view.

.. py:class:: DrawerData

   Typed view exposing a drawer icon's current position and window size.

.. py:class:: DrawerData2

   Typed view exposing the extended drawer flags and view mode.

.. py:class:: IconSummary

   Immutable summary with ``icon_type``, ``type_name``, ``version``,
   ``revision``, ``image_count``, ``position``, ``canvas_size``,
   ``has_drawer_data``, ``has_default_tool``, ``has_tool_types``, and
   ``has_tool_window`` fields.

.. py:class:: IconImage

   Immutable image metadata with ``index``, ``width``, ``height``, and
   ``depth`` fields.

Editing structure fields
========================

Use :meth:`IconFile.get_field` and :meth:`IconFile.set_field` to read or update
fields by their path. For example::

  stack_size = icon.get_field("DiskObject:StackSize")
  icon.set_field("DiskObject:StackSize", stack_size + 1024)
  icon.set_field("DiskObject:Gadget:Width", 64)

Field paths correspond to structures in the icon, including ``DiskObject``,
``DiskObject:Gadget``, ``DrawerData``, ``DrawerData:NewWindow``,
``DrawerData2``, ``Icon``, and ``IconSelect``. Fields that require data absent
from the icon raise :class:`IconFieldError`.

The convenience methods :meth:`IconFile.set_position` and
:meth:`IconFile.set_window_size` set the icon position and drawer window size
respectively. The equivalent
``disk_object.position`` and ``drawer_data.window_size`` properties can also
be used when available.

ToolTypes
=========

The :attr:`IconFile.tool_types` property returns a :class:`ToolTypes` view. Read entries
using ``entries`` or look up a key using ``get`` and ``get_entry``::

  value = icon.tool_types.get("PUBSCREEN")
  entry = icon.tool_types.get_entry("DONOTWAIT")

``get`` returns the value for a key/value entry, ``"true"`` for an enabled
flag, ``"false"`` for a disabled flag, or its ``default`` value if the key is
absent. Matching is case-sensitive unless ``ignore_case=True`` is passed.

Use ``set(key, value)`` to set a key/value entry, ``set_flag(key)`` to enable
a flag, ``unset(key)`` to disable a flag while retaining it, and
``delete(key)`` to remove an entry. ``delete`` returns whether a matching
entry existed. ``normalize()`` removes duplicate and empty entries and returns
whether the entries changed. These methods accept ``ignore_case=True`` for
case-insensitive matching.

Each item in ``entries`` is a :class:`ToolType` with ``key``, ``value``,
``enabled``, and ``raw`` attributes. ``is_flag`` is true when the entry has no
value.

.. py:class:: ToolTypes

   Mutable view for reading and updating the icon's ToolType entries.

.. py:class:: ToolType

   Immutable ToolType entry. ``key`` contains the key, ``value`` is its value
   or ``None`` for a flag, ``enabled`` indicates whether a flag is enabled, and
   ``raw`` preserves the entry's original text. ``is_flag`` is true when
   ``value`` is ``None``.

Validation and image conversion
===============================

Call :meth:`IconFile.validate` to check the serialized icon. It returns an empty list
when validation succeeds, or a list of :class:`ValidationIssue` objects when
issues are found. Each issue has ``severity``, ``message``, and an optional
byte ``offset``.

PNG conversion is available through :meth:`IconFile.export_png` and
:meth:`IconFile.import_png`
when ``pypng`` is installed. ``export_png`` supports the main or selected
image, transparency handling, and forcing planar image data. ``import_png``
imports into the main or selected image and returns :class:`ImageImportInfo`,
which reports the selected palette, bit depth, color error, and whether the
PNG had transparent pixels.

.. py:class:: ValidationIssue

   Immutable validation result with ``severity``, ``message``, and optional
   byte ``offset`` fields.

.. py:class:: ImageImportInfo

   Immutable PNG import result with ``palette``, ``depth``,
   ``max_color_error``, and ``has_transparent_pixels`` fields.

Errors
======

All library exceptions derive from :class:`IconError`:

.. py:class:: IconError

   Base class for exceptions raised by the icon library.

.. py:class:: IconFormatError

   Raised when icon data is malformed.

.. py:class:: IconIOError

   Raised when reading or writing an icon file fails.

.. py:class:: IconFieldError

   Raised when a requested structure field is unknown or unavailable.

.. py:class:: IconOperationError

   Raised when an icon operation cannot be completed.

Import the public API types and exceptions from ``amitools.icon``::

  from amitools.icon import (
      IconError,
      IconFile,
      IconFormatError,
      IconIOError,
      IconFieldError,
      IconOperationError,
  )
