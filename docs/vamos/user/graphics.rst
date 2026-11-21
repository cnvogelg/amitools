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
