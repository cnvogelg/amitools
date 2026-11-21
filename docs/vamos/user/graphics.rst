Graphics and display backends
=============================

SDL display backend
-------------------

The optional SDL backend provides host-backed Intuition windows, indexed
bitmap planes, text, lines, filled rectangles, regions, refresh clipping
and IDCMP messages. Install the Python bindings with::

    pip install 'amitools[vamos,graphics]'

SDL2 and SDL2_ttf must also be available as native libraries. PySDL2's
``PYSDL2_DLL_PATH`` can name their directories when they are outside the
system library search path. Without these optional libraries, Intuition's
nonvisual functions remain available in headless mode.

The plain 8-pixel ``topaz.font`` uses an MIT-licensed bitmap derived from
Alex Limi's TopazDouble Sans recreation. The original diskfont, license,
source reference and reproducible conversion script are bundled with the
8-pixel strike. This is a recreation, not a Commodore ROM font. Other
sizes and styles use Cousine under the SIL Open Font License. Other
TrueType fonts can be loaded from the configured ``FONTS:`` path.

Fonts expose guest-readable ``tf_CharLoc``, ``tf_CharData``, ``tf_CharSpace``
and ``tf_CharKern`` tables. Text rendering also accepts application-owned
copies of these structures. ``BltTemplate`` supports programs which draw
glyphs directly, and ``SetRGB4`` changes each screen's indexed palette.

Use ``--display-scale 2`` for a larger window with square pixels. For a
classic screen presented at a nominal 4:3 monitor aspect, use::

    vamos --display-scale 2 --display-aspect 4:3 myprog

A 640x256 screen then occupies 1280x960 host pixels. This sets the whole
window's aspect, not exact CRT timings or overscan geometry. The guest
resolution stays unchanged and mouse coordinates are translated back to
guest pixels. ``--display-scale 1x2`` permits independent integer axis
scales with the default ``--display-aspect square``; in 4:3 mode only the
horizontal scale determines the window size. The corresponding INI
settings are ``scale`` and ``aspect`` in a ``[display]`` section.

API coverage is partial. This backend supports SDL windows and the
implemented graphics vectors; applications requiring other vectors still
use vamos's normal missing-function behavior. It is not a chipset or
Workbench replacement.

The optional native regression uses SDL's dummy video driver, exercises a
68k window-library call, checks rendered pixels and guest bitmap planes,
and verifies library close and reopen. With the native libraries and
PySDL2 available, run it from the source checkout with::

    AMITOOLS_TEST_SDL=1 python -m pytest -q test/unit/lib_graphics_sdl.py

The indexed graphics backend exposes screen ColorMaps, RGB queries, nearest
shared pens, planar bitmap allocation and attributes, pixel writes, and text
extent/fitting. Color matching currently uses the fixed screen palette; a
``FailIfBad`` request conservatively requires an exact RGB match. It does not
allocate additional colors. Layer clip-region installation flushes pending
drawing before changing the clip, preserves the previous region, and intersects
the user clip with refresh clipping. Layer-info locks are serialized no-ops;
overlapping Amiga layers and general layer management remain unsupported.
Masked bitmap copy/invert blits preserve transparent pixels and the destination
write mask. Window resizing updates guest dimensions, bitmap planes and the SDL
texture, and delivers size/refresh notifications. These graphics operations
support category images and changing page sizes in
native toolkits. Native GUI libraries still need additional BOOPSI and OS
services; this backend alone does not make ZunePrefs fully operational.

Offline PNG backend
-------------------

Use the same graphics and Intuition implementation without SDL or a display
server by selecting the PNG backend::

    vamos --display-backend png --display-output captures myprog

Each window writes its latest completed frame to ``captures/window-0001.png``,
``window-0002.png``, etc. Files are replaced atomically after drawing changes,
including pending drawing when the guest closes a window. Reusing the output
directory replaces files with matching names; unrelated files remain intact.
The images contain exact guest-resolution RGBA pixels; display scale and
aspect options do not resample them. The backend uses only Python's standard
library. Bundled Topaz and guest bitmap fonts work without SDL_ttf; host
TrueType font conversion remains an SDL-backend facility.

When all guest tasks wait, the PNG backend sends one normal close-window
request per window. Programs which handle that IDCMP message can exit and
release their own resources. This is a snapshot mode, not scripted interaction
or a forced process exit: programs which ignore close requests can remain
waiting, and programs which never yield or finish need the usual runtime
limits. A capture reflects the first idle state, not necessarily completion
of an application's asynchronous startup.

Display and scheduler integration
---------------------------------

``amitools.vamos.display`` defines a small RTG-style boundary: windows,
framebuffers, palette uploads, normalized input events and font masks. Guest
raster operations and Amiga bitmap/IDCMP structures belong to graphics and
Intuition. Host windows, textures, event translation and SDL_ttf conversion
belong exclusively to the SDL backend. The PNG backend consumes the same
framebuffers. This is an internal host interface, not an emulated RTG library.

Library contexts expose ``ctx.scheduler`` and ``ctx.display``. Intuition
registers a nonblocking ``add_after_schedule_callback`` on its first window
and removes it after the last closes. The scheduler invokes callbacks at run
entry and after each task slice, outside guest execution. Multiple sources
can register, and callbacks can unregister themselves safely. Idle callbacks
may perform bounded waits and report whether their event source remains
alive. Only ``schedule()`` uses those waits; ``run_until_idle()`` always
returns without waiting for external events and retains its cycle budget.
Exec has no display polling or renderer-specific main-loop integration.


Input and patterned fills
-------------------------

``ReportMouse`` and ``WFLG_REPORTMOUSE`` control application mouse-motion
messages; menus continue to track the pointer independently. Raw-key messages
carry an owned, zero-initialized previous-key buffer through ``IAddress`` until
``ReplyMsg``. Dead-key composition and key history are not yet implemented.

Monochrome ``RastPort.AreaPtrn`` fills honor JAM1, JAM2, complement, inverse
video, plane masks and clipping. Patterns are anchored at the raster origin
and copied when drawing is queued. Multi-plane area patterns are unsupported.

Native classes and OS services
------------------------------

The library loader accepts ``.mui``, ``.mcc`` and ``.mcp`` filenames in
addition to ``.library`` and ``.device``. Class libraries use normal library
loading and configuration; their code runs on the emulated CPU. For example::

    vamos -O 'Example.mcc=mode:amiga' myprogram

There is no Python implementation of MUI widgets. The initial BOOPSI support
provides ``rootclass``, class registration and lifetime management, object
allocation/disposal, attribute messages, and object-list operations. Public
``Class``, ``Hook`` and hidden object headers use the classic 32-bit ABI, so
native ``DoMethodA`` and ``DoSuperMethodA`` can call guest dispatchers directly.
Intuition's object entry points and Utility's ``CallHookPkt`` also call guest
hooks, including nested calls back into vamos. ``SetGadgetAttrsA`` supplies
window GadgetInfo; requester-relative gadget domains and built-in gadget/image
classes are not yet implemented.

The following optional GUI-related libraries have initial implementations:

* ``asl.library`` allocates file and font requesters, copies initial strings,
  preserves selections between requests, and offers a modal SDL text selector.
  Use Tab or click a field, Backspace to edit, Enter to accept, and Escape to
  cancel. Ctrl+A clears the current field. Headless operation cancels. Screen
  mode selection, multi-selection and callback/pattern filtering are unsupported.
* ``diskfont.library`` opens classic bitmap font contents files and relocated
  font hunks from ``FONTS:``, publishes guest character tables, and enumerates
  bitmap font entries. The bundled Topaz recreation is available at 8 and 16
  pixels. Outline engines, color fonts and scaling are unsupported.
* ``iffparse.library`` reads and writes nested IFF chunks using DOS handles or
  guest stream hooks. It provides byte/record I/O, context traversal, scan/step
  parsing, stop handlers and scoped stored properties. Writing supports unknown
  sizes with backpatching and odd-byte padding. Clipboard streams, collections,
  client entry/exit handlers and general local context items are unsupported.
* ``icon.library`` loads, saves, duplicates and frees classic DiskObjects,
  including relocated planar images, drawer data, default tools and ToolTypes.
  It provides default icons, ToolType lookup and value matching. Existing
  extended icon data is preserved on file round trips; extended icon rendering
  and Workbench launch/message handling are separate, unimplemented features.
* ``datatypes.library`` creates BOOPSI picture objects from palette ILBM files
  or memory buffers, including ByteRun1 and masks. Bitmap/header/color attributes,
  frame sizing and synchronous layout without palette remapping are supported.
  Other formats, palette remapping, embedded datatype gadgets, printing and
  asynchronous layout are unsupported.

These are API subsets, not complete replacements for the corresponding AmigaOS
libraries. Other vectors retain vamos' missing-function behavior. Commodities
and ARexx functionality is deferred, and neither library is automatically
replaced with a fake implementation. Native Zune still depends on additional
layers/graphics functionality; loading its classes does not imply that
ZunePrefs is fully operational.

Run the focused tests with::

    python -m pytest -q test/unit/lib_boopsi.py test/unit/lib_os_support.py
    AMITOOLS_TEST_SDL=1 python -m pytest -q test/unit/lib_os_native.py

Classic gadgets and GadTools drawing
------------------------------------

Application-owned window gadget lists support Add/RemoveGList, single-gadget
wrappers, refresh, enable/disable, relative geometry, boolean verification and
toggle selection. DrawBorder and classic planar DrawImage render through the
shared raster backend. Basic string gadgets support append, backspace and
Return; full cursor editing, selection, validation hooks and numeric editing
are not implemented. EraseRect fills the background pen; layer backfill hooks
are not implemented.

Custom gadgets use their guest MutualExclude hook for GM_HITTEST, GM_RENDER,
GM_GOACTIVE, GM_HANDLEINPUT and GM_GOINACTIVE. Input includes gadget-relative
coordinates and a temporary InputEvent. GMR_VERIFY supplies the termination
code and gadget pointer in IDCMP_GADGETUP; GMR_REUSE passes the event onward.
The temporary GadgetInfo, method and event memory is valid only during the
hook. ObtainGIRPort supplies a private raster-state copy sharing the window
backing; ReleaseGIRPort releases it. Raster state and the interrupted CPU
context are preserved. Active
hooks receive an abort notification before removal, disabling or closure.

GadTools provides GetVisualInfoA, FreeVisualInfo and simple DrawBevelBoxA
frames, honoring GT_VisualInfo screen pens and GTBB_Recessed. It does not
create GadTools widgets. These services keep widget implementations in the
guest application or native toolkit.

This is an initial subset. Requester/screen gadgets, proportional gadgets,
BOOPSI image rendering, full highlight styles, layout/help methods, tab
cycling, input timers, tablet events, and additional GadTools APIs/frame
styles remain unsupported. Programs using those features may still render
incompletely or require additional input support.
