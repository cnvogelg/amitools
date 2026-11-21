from amitools.vamos.display import get_display
from amitools.vamos.display.base import Rect
from contextlib import ExitStack
from amitools.vamos.libtypes import TagList, MsgPort, Message, List, Node
from amitools.vamos.lib.GraphicsLibrary import BFText, BFDraw, BFTemplate
from amitools.vamos.lib.graphics_support import BitmapBlit
from amitools.vamos.libcore.impl import LibImpl
from amitools.vamos.lib.TimerDevice import TimerDevice
from amitools.vamos.lib.boopsi import Boopsi

from amitools.vamos.lib.graphics import (
    RastPortStruct,
    LayerStruct,
    RectangleStruct,
    TextAttrStruct,
    JAM2,
)
from amitools.vamos.lib.intuition import (
    WA_Left,
    WA_Top,
    WA_Width,
    WA_Height,
    WA_InnerWidth,
    WA_InnerHeight,
    WA_Flags,
    WA_PubScreenName,
    SA_Dummy,
    PubScreenNodeStruct,
    WA_Title,
    WA_MinWidth,
    WA_MinHeight,
    WA_MaxWidth,
    WA_MaxHeight,
    WindowStruct,
    IDCMP_MOUSEMOVE,
    IDCMP_MOUSEBUTTONS,
    IDCMP_RAWKEY,
    IDCMP_VANILLAKEY,
    IDCMP_CLOSEWINDOW,
    IDCMP_NEWSIZE,
    IDCMP_REFRESHWINDOW,
    IntuiMessageStruct,
    MenuStruct,
    MenuItemStruct,
    IntuiTextStruct,
    IDCMP_MENUPICK,
    NewWindowStruct,
    WA_IDCMP,
    ScreenStruct,
    NewScreenStruct,
    WA_CustomScreen,
)
from amitools.vamos.log import log_intui
from amitools.vamos.machine.regs import (
    REG_D0,
    REG_A0,
    REG_A1,
    REG_D1,
    REG_D2,
    REG_D3,
    REG_D4,
    REG_D5,
)
from amitools.vamos.libstructs.exec_ import MsgPortStruct, MessageStruct, ListStruct

MENUNULL = 0xFFFF

MENUENABLED = 0x0001

# MenuItem.Flags (from Intuition)
CHECKIT = 0x0001  # Item is checkmarkable
ITEMTEXT = 0x0002  # Item has textual label (else graphical)
COMMSEQ = 0x0004  # Item has a command sequence
MENUTOGGLE = 0x0008  # Toggle checks; otherwise mutually exclusive
ITEMENABLED = 0x0010  # Item is enabled/active
CHECKED = 0x0100
SUBMENU = 0x0200  # Show standard submenu indicator (V47)

IECODE_UP_PREFIX = 0x80

IECODE_LBUTTON = 0x68
IECODE_RBUTTON = 0x69
IECODE_MBUTTON = 0x6A

# def ts(label): print(f"{time.perf_counter():.6f} {label}")


class IntuitionLibrary(LibImpl):
    def __init__(self):
        super().__init__()
        # default init stuff
        self._easy_last = None
        self.alloc = None
        self._boopsi = None
        self.window_addresses = {}  # Host window ID -> Amiga window address
        self.host_windows = {}
        self.menu_active = False
        self.mouse_x = 0
        self.mouse_y = 0
        self.submenu_rects = []
        self.hovered_item = None
        self.hovered_item_index = []
        self.graphics_lib_addr = None
        self.graphics_lib = None
        self.default_screen = None
        self._lib_opened = False  # guard flag
        self._default_title_memory = None
        self._screen_fonts = {}
        self._idcmp_owners = {}
        self._reply_owners = {}
        self._window_ports = {}

        self.rp_2_win_addr = {}
        self.refresh_pending = set()
        self._pending_window_sizes = {}
        self.display_scale = (1, 1)
        self.display_aspect = "square"
        self._window_scales = {}
        self._pub_list_memory = None
        self._pub_screen_locks = 0
        self._draw_infos = {}

    def setup_lib(self, ctx, base_addr):
        # log_dos.info("setup intuition.library")
        self.alloc = ctx.alloc
        self.display = get_display(ctx)
        self._scheduler = getattr(ctx, "scheduler", None)
        self._pump_callback = lambda: self._pump_display(ctx)
        self._idle_callback = lambda: self._pump_display(ctx, wait=True)
        self._display_registered = False
        self._boopsi_ctx = ctx
        self.display_scale = getattr(ctx, "display_scale", (1, 1))
        self.display_aspect = getattr(ctx, "display_aspect", "square")

        # Register with ExecLibrary
        ctx.exec_lib.intuition_lib = self

        # no graphics calls here

    def open_lib(self, ctx, open_cnt):
        """Perform graphics-dependent initialization (only once)."""
        if self._lib_opened:
            return  # already initialized

        if not self.display.open():
            log_intui.warning("No host display available")
            return
        with ExitStack() as rollback:
            rollback.callback(self.display.close)
            graphics_addr = ctx.lib_mgr.open_lib("graphics.library")
            if not graphics_addr:
                return
            rollback.callback(ctx.lib_mgr.close_lib, graphics_addr)
            graphics = ctx.exec_lib.graphics_lib
            if graphics is None or graphics.text_attr is None:
                return
            title = ctx.alloc.alloc_memory(
                len("Workbench") + 1,
                label="Intuition default title",
                except_on_failure=False,
            )
            if title is None:
                return
            rollback.callback(ctx.alloc.free_memory, title)
            ctx.mem.w_cstr(title.addr, "Workbench")
            screen = self.create_screen(
                ctx,
                640,
                256,
                3,
                graphics.text_attr.addr,
                title.addr,
                1,
                0,
                graphics=graphics,
            )
            if screen is None:
                return
            self.default_screen = screen
            self._default_title_memory = title
            self.graphics_lib_addr = graphics_addr
            self.graphics_lib = graphics
            self._lib_opened = True
            rollback.pop_all()

    def close_lib(self, ctx, open_cnt):
        if open_cnt != 0 or not self._lib_opened:
            return
        screens = []
        screen = self.default_screen
        while screen is not None:
            screens.append(screen)
            addr = screen.NextScreen.val
            screen = ScreenStruct(ctx.mem, addr) if addr else None
        title = self._default_title_memory
        graphics_addr = self.graphics_lib_addr
        self._lib_opened = False
        self.default_screen = None
        self._default_title_memory = None
        self.graphics_lib_addr = None
        try:
            with ExitStack() as cleanup:
                cleanup.callback(self.display.close)
                cleanup.callback(ctx.lib_mgr.close_lib, graphics_addr)
                cleanup.callback(ctx.alloc.free_memory, title)
                if self._pub_list_memory is not None:
                    cleanup.callback(ctx.alloc.free_memory, self._pub_list_memory)
                    self._pub_list_memory = None
                self._pub_screen_locks = 0
                for screen in screens:
                    cleanup.callback(self._free_screen, ctx, screen)
                for window in tuple(self.window_addresses.values()):
                    cleanup.callback(self._close_window_addr, ctx, window)
        finally:
            self.graphics_lib = None

    def finish_lib(self, ctx):
        if self._boopsi is not None:
            self._boopsi.cleanup()
            self._boopsi = None
        for block in self._draw_infos.values():
            ctx.alloc.free_memory(block)
        self._draw_infos.clear()
        # No guest can return an outstanding message after library teardown.
        for owner in tuple(self._reply_owners.values()):
            owner["closed"] = True
            for memory, _ in owner["messages"].values():
                ctx.alloc.free_memory(memory)
            owner["messages"].clear()
            self._release_idcmp_port(ctx, owner)
        self._idcmp_owners.clear()
        self._unregister_display()

    def _close_window_addr(self, ctx, addr):
        ctx.cpu.w_reg(REG_A0, addr)
        self.CloseWindow(ctx)

    def DisplayAlert(self, ctx):
        alert_num = ctx.cpu.r_reg(REG_D0)
        msg_ptr = ctx.cpu.r_reg(REG_A0)
        msg = ctx.mem.r_cstr(msg_ptr)
        log_intui.error(
            "-----> DisplayAlert: #%08x - '%s'@%08x <-----", alert_num, msg, msg_ptr
        )

    def AutoRequest(self, ctx):
        IntuiText = ctx.cpu.r_reg(REG_A1)
        IText = ctx.mem.r32(IntuiText + 12)  # IntuiText.ITexT
        msg = ctx.mem.r_cstr(IText)
        log_intui.error("-----> AutoRequest '%s'", msg)

    def EasyRequestArgs(self, ctx, window, easy_struct, idcmp_ptr, args):
        mem = ctx.mem
        msg = mem.r_cstr(mem.r32(easy_struct + 12))  # EasyStruct.es_TextFormat
        gad_ptr = mem.r32(easy_struct + 16)  # EasyStruct.es_GadgetFormat
        gadgets = mem.r_cstr(gad_ptr) if gad_ptr else ""
        key = (msg, gadgets)
        # No user can answer. Take the first gadget once, so that e.g. SFS
        # startup can continue, then the rightmost (0, e.g. CANCEL) while
        # the same requester repeats, so RETRY|CANCEL requesters cannot loop.
        if self._easy_last == key:
            log_intui.debug("EasyRequest '%s' [%s] repeated -> 0", msg, gadgets)
            return 0
        self._easy_last = key
        log_intui.error("-----> EasyRequest '%s' [%s] -> 1", msg, gadgets)
        return 1

    def CurrentTime(self, ctx, secs_ptr, micros_ptr):
        secs, micros = TimerDevice.get_sys_time()
        log_intui.info(
            "CurrentTime(%08x, %08x) -> secs=%d micros=%d",
            secs_ptr,
            micros_ptr,
            secs,
            micros,
        )
        ctx.mem.w32(secs_ptr, secs)
        ctx.mem.w32(micros_ptr, micros)

    def find_window_id(self, addr):
        for host_window, amiga_addr in self.window_addresses.items():
            if amiga_addr == addr:
                return host_window
        return None

    def CloseWindow(self, ctx):
        window_ptr = ctx.cpu.r_reg(REG_A0)
        log_intui.info("Closing window @%08x", window_ptr)
        if window_ptr == 0:
            return

        # Capture resources while the public structure is still alive.
        win = WindowStruct(ctx.mem, window_ptr)

        screen_ptr = win.WScreen.get()
        title_addr = win.Title.get()
        title_memory = ctx.alloc.get_memory(title_addr) if title_addr else None
        rastport_addr = win.RPort.get()
        user_port_addr = self._window_ports.pop(window_ptr, 0)

        # Invalidate the host ID before releasing guest resources so late
        # events cannot target a closed window.
        window_id = self.find_window_id(window_ptr)
        host_window = self.host_windows.pop(window_id, None)
        self.window_addresses.pop(window_id, None)
        self._window_scales.pop(window_id, None)
        self.refresh_pending.discard(window_ptr)
        self._pending_window_sizes.pop(window_ptr, None)
        self.rp_2_win_addr.pop(rastport_addr, None)

        screen = ScreenStruct(ctx.mem, screen_ptr)

        prev_ptr = 0
        current_ptr = screen.FirstWindow.get()

        while current_ptr:
            current_win = WindowStruct(ctx.mem, current_ptr)
            next_ptr = current_win.NextWindow.get()

            if current_ptr == window_ptr:
                if prev_ptr == 0:
                    screen.FirstWindow.set(next_ptr)
                else:
                    prev_win = WindowStruct(ctx.mem, prev_ptr)
                    prev_win.NextWindow.set(next_ptr)
                log_intui.info(
                    "Unlinked window 0x%08X from screen 0x%08X", window_ptr, screen_ptr
                )
                break

            prev_ptr = current_ptr
            current_ptr = next_ptr

        self._close_idcmp(ctx, window_ptr)

        # Release the port and renderer before the structures and host
        # window they belong to. Attempt all releases if one raises.
        with ExitStack() as cleanup:
            if not self.host_windows:
                cleanup.callback(self._unregister_display)
            if host_window is not None:
                cleanup.callback(self.display.close_window, host_window)
            cleanup.callback(win.free, ctx.alloc)
            if title_memory is not None:
                cleanup.callback(ctx.alloc.free_memory, title_memory)
            if rastport_addr:
                cleanup.callback(
                    self.graphics_lib.free_RastPortStruct, ctx, rastport_addr
                )
            if user_port_addr:
                user_port = MsgPortStruct(ctx.mem, user_port_addr)
                cleanup.callback(ctx.exec_lib.DeleteMsgPort, ctx, user_port)
            # Capture pending drawing even when a guest opens, draws and
            # closes without yielding to the scheduler. Cleanup still runs
            # when the backend cannot write or present its final frame.
            graphics = self.graphics_lib.get_rp_graphics(rastport_addr)
            if host_window is not None and graphics is not None:
                self._flush_batch(graphics)
                if graphics.present_pending:
                    graphics.frame.begin()
                    graphics.frame.finish()

    def OpenWindow(self, ctx):
        if self.default_screen is None:
            ctx.cpu.w_reg(REG_D0, 0)
            return

        new_window_ptr = ctx.cpu.r_reg(REG_A0)

        new_win = NewWindowStruct(ctx.mem, new_window_ptr)
        left = new_win.LeftEdge.get()
        top = new_win.TopEdge.get()
        width = new_win.Width.get()
        height = new_win.Height.get()

        idcmp_flags = new_win.IDCMPFlags.get()

        title_ptr = new_win.Title.get()
        title = ctx.mem.r_cstr(title_ptr) if title_ptr else ""

        min_width = new_win.MinWidth.get()
        min_height = new_win.MinHeight.get()
        max_width = new_win.MaxWidth.get()
        max_height = new_win.MaxHeight.get()

        screen = new_win.Screen.get()

        flags = False
        # Determine if window should be resizable
        if (
            width > min_width
            or height > min_height
            or width < max_width
            or height < max_height
        ):
            flags = True

        amiga_win_addr = self.create_window_struct(
            ctx,
            left,
            top,
            width,
            height,
            idcmp_flags,
            title,
            screen,
            flags,
            new_win.Flags.val,
        )

        ctx.cpu.w_reg(REG_D0, amiga_win_addr)

    def OpenWindowTagList(self, ctx):
        if self.default_screen is None:
            ctx.cpu.w_reg(REG_D0, 0)
            return

        taglist_ptr = ctx.cpu.r_reg(REG_A1)

        # Default values
        left = 100
        top = 100
        width = 400
        height = 300
        title = "Vamos Window"
        min_width = min_height = 0
        max_width = max_height = 0xFFFF  # Large default max

        screen = self.default_screen.addr
        idcmp_flags = 0
        amiga_flags = 0

        new_window_ptr = ctx.cpu.r_reg(REG_A0)
        if new_window_ptr != 0:
            new_win = NewWindowStruct(ctx.mem, new_window_ptr)
            left = new_win.LeftEdge.get()
            top = new_win.TopEdge.get()
            width = new_win.Width.get()
            height = new_win.Height.get()

            idcmp_flags = new_win.IDCMPFlags.get()
            amiga_flags = new_win.Flags.val

            title_ptr = new_win.Title.get()
            title = ctx.mem.r_cstr(title_ptr) if title_ptr else ""

            min_width = new_win.MinWidth.get()
            min_height = new_win.MinHeight.get()
            max_width = new_win.MaxWidth.get()
            max_height = new_win.MaxHeight.get()

            screen = new_win.Screen.get()

        # Reuse Utility's typed iterator for MORE, SKIP and IGNORE tags.
        for item in TagList(ctx.mem, taglist_ptr):
            tag, data = item.get_tag(), item.get_data()

            if tag == WA_Left:
                left = (data & 0x7FFF) - (data & 0x8000)
            elif tag == WA_Top:
                top = (data & 0x7FFF) - (data & 0x8000)
            elif tag in (WA_Width, WA_InnerWidth):
                width = data
            elif tag in (WA_Height, WA_InnerHeight):
                height = data
            elif tag == WA_Title:
                title = ctx.mem.r_cstr(data) if data else ""
            elif tag == WA_PubScreenName:
                if data and ctx.mem.r_cstr(data) != "Workbench":
                    ctx.cpu.w_reg(REG_D0, 0)
                    return
                screen = self.default_screen.addr
            elif tag == WA_MinWidth:
                min_width = data
            elif tag == WA_MinHeight:
                min_height = data
            elif tag == WA_MaxWidth:
                max_width = data
            elif tag == WA_MaxHeight:
                max_height = data
            elif tag == WA_IDCMP:
                idcmp_flags = data
            elif tag == WA_Flags:
                amiga_flags = data
            elif tag == WA_CustomScreen:
                screen = data
            else:
                log_intui.warning(
                    "OpenWindowTagList: unknown tag 0x%08X with data 0x%08X", tag, data
                )

        log_intui.info(
            "OpenWindowTagList: '%s' at (%d, %d) size (%d x %d)",
            title,
            left,
            top,
            width,
            height,
        )

        flags = False
        if (
            width > min_width
            or height > min_height
            or width < max_width
            or height < max_height
        ):
            flags = True

        # Return fake Amiga window pointer
        amiga_win_addr = self.create_window_struct(
            ctx,
            left,
            top,
            width,
            height,
            idcmp_flags,
            title,
            screen,
            flags,
            amiga_flags,
        )
        ctx.cpu.w_reg(REG_D0, amiga_win_addr)

    def SetMenuStrip(self, ctx):
        win_addr = ctx.cpu.r_reg(REG_A0)
        menu_addr = ctx.cpu.r_reg(REG_A1)

        win = WindowStruct(ctx.mem, win_addr)
        win.MenuStrip.set(menu_addr)

        log_intui.info(
            "SetMenuStrip: attached menu at 0x%08X to window 0x%08X",
            menu_addr,
            win_addr,
        )

        ctx.cpu.w_reg(REG_D0, 1)  # Success

    def ClearMenuStrip(self, ctx):
        win_addr = ctx.cpu.r_reg(REG_A0)
        win = WindowStruct(ctx.mem, win_addr)
        win.MenuStrip.set(0)
        ctx.cpu.w_reg(REG_D0, 1)  # Success

    def ModifyIDCMP(self, ctx):
        win_addr = ctx.cpu.r_reg(REG_A0)
        flags = ctx.cpu.r_reg(REG_D0)
        win = WindowStruct(ctx.mem, win_addr)
        if flags and not win.UserPort.val:
            port = ctx.exec_lib.CreateMsgPort(ctx)
            if port is None:
                ctx.cpu.w_reg(REG_D0, 0)
                return
            self._window_ports[win_addr] = port.addr
            win.UserPort.val = port.addr
        elif not flags:
            self._close_idcmp(ctx, win_addr)
            owned = self._window_ports.pop(win_addr, 0)
            if owned:
                if win.UserPort.val == owned:
                    win.UserPort.val = 0
                ctx.exec_lib.DeleteMsgPort(ctx, MsgPort(ctx.mem, owned))
        win.IDCMPFlags.val = flags
        ctx.cpu.w_reg(REG_D0, 1)

    def OpenScreen(self, ctx):
        if self.default_screen is None:
            ctx.cpu.w_reg(REG_D0, 0)
            return
        ns_ptr = ctx.cpu.r_reg(REG_A0)
        ns = NewScreenStruct(ctx.mem, ns_ptr)

        width = ns.Width.get()
        height = ns.Height.get()
        depth = ns.Depth.get()
        font_ptr = ns.Font.get()
        title_ptr = ns.DefaultTitle.get()
        detail_pen = ns.DetailPen.get()
        block_pen = ns.BlockPen.get()

        screen = self.create_screen(
            ctx, width, height, depth, font_ptr, title_ptr, detail_pen, block_pen
        )
        if screen is None:
            ctx.cpu.w_reg(REG_D0, 0)
            return

        # Link into screen list
        screen.NextScreen.set(self.default_screen.NextScreen.get())
        self.default_screen.NextScreen.set(screen.addr)

        ctx.cpu.w_reg(REG_D0, screen.addr)
        log_intui.info(f"OpenScreen: created and linked screen at 0x{screen.addr:X}")

    def OpenScreenTagList(self, ctx):
        if self.default_screen is None:
            return 0
        ptr = ctx.cpu.r_reg(REG_A0)
        values = dict(
            Width=640,
            Height=256,
            Depth=3,
            Font=0,
            DefaultTitle=0,
            DetailPen=1,
            BlockPen=0,
        )
        if ptr:
            ns = NewScreenStruct(ctx.mem, ptr)
            values.update((name, getattr(ns, name).val) for name in values)
        fields = {
            3: "Width",
            4: "Height",
            5: "Depth",
            6: "DetailPen",
            7: "BlockPen",
            8: "DefaultTitle",
            11: "Font",
        }
        for item in TagList(ctx.mem, ctx.cpu.r_reg(REG_A1)):
            field = fields.get(item.get_tag() - SA_Dummy)
            if field is not None:
                values[field] = item.get_data()
        screen = self.create_screen(
            ctx,
            values["Width"],
            values["Height"],
            values["Depth"],
            values["Font"],
            values["DefaultTitle"],
            values["DetailPen"],
            values["BlockPen"],
        )
        if screen is None:
            return 0
        screen.NextScreen.val = self.default_screen.NextScreen.val
        self.default_screen.NextScreen.val = screen.addr
        return screen.addr

    def GetDefaultPubScreen(self, ctx):
        buffer = ctx.cpu.r_reg(REG_A0)
        if buffer:
            ctx.mem.w_cstr(buffer, "Workbench" if self.default_screen else "")

    def LockPubScreen(self, ctx):
        name = ctx.cpu.r_reg(REG_A0)
        if self.default_screen is None or (
            name and ctx.mem.r_cstr(name) != "Workbench"
        ):
            return 0
        self._pub_screen_locks += 1
        return self.default_screen.addr

    def UnlockPubScreen(self, ctx):
        # The library owns the default screen for its entire open lifetime.
        if self._pub_screen_locks:
            self._pub_screen_locks -= 1

    def LockPubScreenList(self, ctx):
        if self.default_screen is None:
            return 0
        if self._pub_list_memory is None:
            memory = ctx.alloc.alloc_memory(
                ListStruct.get_size() + PubScreenNodeStruct.get_size() + 10,
                label="Intuition public screens",
                except_on_failure=False,
            )
            if memory is None:
                return 0
            public = List(ctx.mem, memory.addr)
            public.new(0)
            node = PubScreenNodeStruct(ctx.mem, memory.addr + ListStruct.get_size())
            name = node.addr + PubScreenNodeStruct.get_size()
            ctx.mem.w_cstr(name, "Workbench")
            node.psn_Node.ln_Name.aptr = name
            node.psn_Screen.val = self.default_screen.addr
            node.psn_Size.val = PubScreenNodeStruct.get_size() + 10
            public.add_tail(Node(ctx.mem, node.addr))
            self._pub_list_memory = memory
        # Only the default screen is public; the list never changes while
        # this library is open, so readers need no scheduler lock.
        return self._pub_list_memory.addr

    def UnlockPubScreenList(self, ctx):
        pass

    def CloseScreen(self, ctx):
        target = ctx.cpu.r_reg(REG_A0)
        previous = self.default_screen
        ctx.cpu.w_reg(REG_D0, 0)
        # The default public screen belongs to the library. A custom
        # screen with live windows is still in use and cannot be closed.
        if previous is None or target == previous.addr:
            return
        current = previous.NextScreen.val
        while current:
            screen = ScreenStruct(ctx.mem, current)
            if current == target:
                if screen.FirstWindow.val:
                    return
                previous.NextScreen.val = screen.NextScreen.val
                self._free_screen(ctx, screen)
                ctx.cpu.w_reg(REG_D0, 1)
                return
            previous, current = screen, screen.NextScreen.val

    @staticmethod
    def _signed_word(value):
        return ((value + 0x8000) & 0xFFFF) - 0x8000

    def PrintIText(self, ctx):
        rastport_addr = ctx.cpu.r_reg(REG_A0)
        text_addr = ctx.cpu.r_reg(REG_A1)
        left = self._signed_word(ctx.cpu.r_reg(REG_D0))
        top = self._signed_word(ctx.cpu.r_reg(REG_D1))
        rp = RastPortStruct(ctx.mem, rastport_addr)
        saved = ctx.mem.r_block(rastport_addr, rp.get_size())
        try:
            while text_addr:
                itext = IntuiTextStruct(ctx.mem, text_addr)
                next_addr = itext.NextText.val
                font_addr = 0
                try:
                    if itext.ITextFont.val:
                        font_addr = self.graphics_lib._open_font(
                            ctx, itext.ITextFont.val
                        )
                        if font_addr:
                            self.graphics_lib._set_font(ctx, rastport_addr, font_addr)
                    rp.cp_x.val = self._signed_word(left + itext.LeftEdge.val)
                    rp.cp_y.val = self._signed_word(
                        top + itext.TopEdge.val + rp.TxBaseline.val
                    )
                    rp.FgPen.val = ((itext.FrontPen.val + 128) & 255) - 128
                    rp.BgPen.val = ((itext.BackPen.val + 128) & 255) - 128
                    rp.DrawMode.val = itext.DrawMode.val
                    string_addr = itext.IText.get()
                    if string_addr:
                        count = len(ctx.mem.r_cstr(string_addr))
                        ctx.cpu.w_reg(REG_A0, string_addr)
                        ctx.cpu.w_reg(REG_A1, rastport_addr)
                        ctx.cpu.w_reg(REG_D0, count)
                        self.graphics_lib.Text(ctx)
                finally:
                    if font_addr:
                        self.graphics_lib._close_font(ctx, font_addr)
                    ctx.mem.w_block(rastport_addr, saved)
                text_addr = next_addr
        finally:
            ctx.mem.w_block(rastport_addr, saved)

    def ItemAddress(self, ctx):
        # Read input registers
        menu_ptr = ctx.cpu.r_reg(REG_A0)  # Pointer to MenuStruct
        menu_number = ctx.cpu.r_reg(REG_D0)  # Packed menu number

        if menu_number == MENUNULL or menu_ptr == 0:
            ctx.cpu.w_reg(REG_D0, 0)
            return

        # Decode menu number
        menu_index = menu_number & 0x1F
        item_index = (menu_number >> 5) & 0x3F
        subitem_index = (menu_number >> 11) & 0x1F

        # Traverse menus
        menu_addr = menu_ptr
        for _ in range(menu_index):
            menu = MenuStruct(ctx.mem, menu_addr)
            menu_addr = menu.NextMenu.get()
            if menu_addr == 0:
                ctx.cpu.w_reg(REG_D0, 0)
                return

        menu = MenuStruct(ctx.mem, menu_addr)
        item_addr = menu.FirstItem.get()
        if item_addr == 0:
            ctx.cpu.w_reg(REG_D0, 0)
            return

        # Traverse items
        for _ in range(item_index):
            item = MenuItemStruct(ctx.mem, item_addr)
            item_addr = item.NextItem.get()
            if item_addr == 0:
                ctx.cpu.w_reg(REG_D0, 0)
                return

        item = MenuItemStruct(ctx.mem, item_addr)

        # Traverse subitems if needed
        if subitem_index > 0:
            subitem_addr = item.SubItem.get()
            if subitem_addr == 0:
                ctx.cpu.w_reg(REG_D0, 0)
                return
            for _ in range(subitem_index - 1):
                subitem = MenuItemStruct(ctx.mem, subitem_addr)
                subitem_addr = subitem.NextItem.get()
                if subitem_addr == 0:
                    ctx.cpu.w_reg(REG_D0, 0)
                    return
            ctx.cpu.w_reg(REG_D0, subitem_addr)
            return

        # Return item address
        ctx.cpu.w_reg(REG_D0, item_addr)

    # ----- Helper -----

    def create_window_struct(
        self,
        ctx,
        left,
        top,
        width,
        height,
        idcmp_flags,
        title,
        screen_addr,
        flags,
        amiga_flags=0,
    ):
        if not (0 < width <= 32767 and 0 < height <= 32767):
            return 0
        if self.graphics_lib is None or (
            not screen_addr and self.default_screen is None
        ):
            return 0

        log_intui.info(
            "Opening host window: '%s' at (%d, %d) size (%d x %d)",
            title,
            left,
            top,
            width,
            height,
        )
        # Create host window
        host_width, host_height = self._display_size(width, height)
        host_window = self.display.create_window(
            title, host_width, host_height, bool(flags)
        )

        if not host_window:
            log_intui.error("Failed to create host window")
            return 0

        with ExitStack() as rollback:
            rollback.callback(self.display.close_window, host_window)
            title_memory = self.alloc.alloc_memory(
                len(title.encode("latin-1")) + 1,
                label="Window title",
                except_on_failure=False,
            )
            if title_memory is None:
                return 0
            rollback.callback(self.alloc.free_memory, title_memory)
            ctx.mem.w_cstr(title_memory.addr, title)
            user_port = None
            if idcmp_flags:
                user_port = ctx.exec_lib.CreateMsgPort(ctx)
                if user_port is None:
                    return 0
                rollback.callback(ctx.exec_lib.DeleteMsgPort, ctx, user_port)
            memory = ctx.alloc.alloc_memory(
                WindowStruct.get_size(),
                label="Intuition window",
                except_on_failure=False,
            )
            if memory is None:
                return 0
            rollback.callback(ctx.alloc.free_memory, memory)
            ctx.mem.clear_block(memory.addr, memory.size, 0)
            win = WindowStruct(ctx.mem, memory.addr)
            win.Width.val, win.Height.val = width, height
            win.Flags.val = amiga_flags
            win.MinWidth.val = win.MinHeight.val = 1
            win.MaxWidth.val = win.MaxHeight.val = 0xFFFF
            # Native toolkits use these fields even for non-GimmeZeroZero
            # windows. The backend owns the host decorations, so the client has no
            # emulated borders and its inner size equals the raster size.
            win.GZZWidth.val, win.GZZHeight.val = width, height
            win.LeftEdge.val, win.TopEdge.val = left, top
            win.IDCMPFlags.val = idcmp_flags
            win.Title.set(title_memory.addr)
            win.UserPort.val = user_port.addr if user_port is not None else 0
            win.WScreen.val = screen_addr or self.default_screen.addr
            screen = ScreenStruct(ctx.mem, win.WScreen.val)
            rp_addr, layer_addr, _ = self.graphics_lib.create_window_rastport(
                ctx, host_window, width, height, screen.BitMap.Depth.val or 2
            )
            if not rp_addr:
                return 0
            rollback.callback(self.graphics_lib.free_RastPortStruct, ctx, rp_addr)
            win.RPort.val, win.WLayer.val = rp_addr, layer_addr
            layer = LayerStruct(ctx.mem, layer_addr)
            layer.Window.val = win.addr
            layer.LayerInfo.val = screen.LayerInfo.addr
            layer.bounds.MinX.val, layer.bounds.MinY.val = left, top
            layer.bounds.MaxX.val = left + width - 1
            layer.bounds.MaxY.val = top + height - 1
            backing = self.graphics_lib.rp_graphics_map.get(rp_addr)
            if backing is not None:
                backing.palette = self.graphics_lib.screen_palettes.get(
                    screen.ViewPort.addr, self.graphics_lib.palette
                )
            window_id = host_window.id
            # Only complete windows are visible to events and screen lists.
            win.NextWindow.val = screen.FirstWindow.val
            screen.FirstWindow.val = win.addr
            if user_port is not None:
                self._window_ports[win.addr] = user_port.addr
            self.rp_2_win_addr[rp_addr] = win.addr
            self.window_addresses[window_id] = win.addr
            self.host_windows[window_id] = host_window
            self._window_scales[window_id] = (host_width / width, host_height / height)
            self._register_display()
            self.refresh(ctx, rp_addr)
            rollback.pop_all()
        return win.addr

    def render(self, ctx, window, mouse_x=0, mouse_y=0):
        window_ptr = self.window_addresses.get(window.id)
        if window_ptr is None:
            return
        win = WindowStruct(ctx.mem, window_ptr)
        graphics = self.graphics_lib.get_rp_graphics(win.RPort.val)
        if graphics is None:
            return
        self._flush_batch(graphics)
        graphics.frame.begin()
        if self.menu_active and win.MenuStrip.val:
            self.draw_menu(ctx, graphics.frame, win.MenuStrip.val, mouse_x, mouse_y)
        graphics.frame.present(self._window_scales.get(window.id, self.display_scale))
        graphics.present_pending = False

    def _register_display(self):
        if self._scheduler is not None and not self._display_registered:
            self._scheduler.add_after_schedule_callback(self._pump_callback)
            self._scheduler.add_idle_callback(self._idle_callback)
            self._display_registered = True

    def _unregister_display(self):
        if self._display_registered:
            self._scheduler.remove_after_schedule_callback(self._pump_callback)
            self._scheduler.remove_idle_callback(self._idle_callback)
            self._display_registered = False

    def _pump_display(self, ctx, wait=False):
        if not self.host_windows:
            return False
        self.check_refresh(ctx)
        for event in self.display.poll(wait_ms=20 if wait else 0):
            pending = self.ingest_event(ctx, event)
            if pending is not None:
                self.drain_pending_intui_events(ctx, pending)
        return self.display.interactive and bool(self.host_windows)

    def encode_selection(self, idx):
        if len(idx) == 2:
            return (idx[0] & 0x1F) | (idx[1] << 5)
        elif len(idx) == 3:
            return (idx[0] & 0x1F) | ((idx[1] << 5) & 0x3F) | (idx[2] << 11)
        return idx[0] & 0x1F

    def _display_size(self, width, height):
        host_width = width * self.display_scale[0]
        host_height = (
            round(host_width * 3 / 4)
            if self.display_aspect == "4:3"
            else height * self.display_scale[1]
        )
        return host_width, host_height

    def _guest_mouse(self, x, y, window_id=None):
        scale = self._window_scales.get(window_id, self.display_scale)
        return int(x // scale[0]), int(y // scale[1])

    def ingest_event(self, ctx, event):

        # Quit is global and has no window ID. Other events must belong
        # to a currently live window; never redirect an unknown ID to 1.
        if event.kind == "quit":
            for win_addr in tuple(self.window_addresses.values()):
                self.queue_idcmp(ctx, win_addr, IDCMP_CLOSEWINDOW)
            return None
        window_id = event.window_id
        win_addr = self.window_addresses.get(window_id)
        if win_addr is None:
            return None

        # ---------- MOUSE MOTION ----------
        if event.kind == "motion":
            mx, my = self._guest_mouse(event.x, event.y, window_id)

            # Menu hover redraw
            if self.menu_active:
                host_window = self.host_windows[window_id]
                self.render(ctx, host_window, mx, my)

            if not self._reports_mouse(ctx, win_addr):
                return None
            return PendingIntuiEvent(win_addr, IDCMP_MOUSEMOVE, mx, my, 0, window_id)

        # ---------- MOUSE BUTTON DOWN ----------
        elif event.kind == "button_down":
            mx, my = self._guest_mouse(event.x, event.y, window_id)
            btn = event.button

            # IECODE mapping
            if btn == 1:
                code = 0x68
            elif btn == 3:
                code = 0x69
            elif btn == 2:
                code = 0x6A
            else:
                code = 0

            # Menu activation
            if btn == 3 and not self.menu_active:
                self.menu_active = True
                self.hovered_item = None
                self.hovered_item_index = []
                self.submenu_rects = []
                host_window = self.host_windows[window_id]
                self.render(ctx, host_window, mx, my)

            return PendingIntuiEvent(
                win_addr, IDCMP_MOUSEBUTTONS, mx, my, code, window_id
            )

        # ---------- MOUSE BUTTON UP ----------
        elif event.kind == "button_up":
            mx, my = self._guest_mouse(event.x, event.y, window_id)
            btn = event.button

            # IECODE mapping
            if btn == 1:
                code = 0xE8
            elif btn == 3:
                code = 0xE9
            elif btn == 2:
                code = 0xEA
            else:
                code = 0

            # MENUPICK
            if self.menu_active and self.hovered_item is not None:
                idx = self.hovered_item_index
                if len(idx) == 2:
                    selection = (idx[0] & 0x1F) | (idx[1] << 5) | (0x1F << 11)
                else:
                    selection = (
                        (idx[0] & 0x1F) | ((idx[1] << 5) & 0x3F) | (idx[2] << 11)
                    )

                # Apply CHECKIT/MENUTOGGLE
                self.handle_menu_selection(ctx, win_addr, self.hovered_item)

                # Reset menu
                self.menu_active = False
                self.hovered_item = None
                self.hovered_item_index = []
                self.submenu_rects = []

                host_window = self.host_windows[window_id]
                self.render(ctx, host_window)

                # Deliver MENUPICK immediately
                self.queue_idcmp(ctx, win_addr, IDCMP_MENUPICK, mx, my, code=selection)
                return None

            # Normal button-up
            if self.menu_active and btn in (
                1,
                3,
            ):
                self.menu_active = False
                self.hovered_item = None
                self.hovered_item_index = []
                self.submenu_rects = []
                host_window = self.host_windows[window_id]
                self.render(ctx, host_window)

            return PendingIntuiEvent(
                win_addr, IDCMP_MOUSEBUTTONS, mx, my, code, window_id
            )

        # ---------- KEYBOARD ----------
        elif event.kind == "key":
            win = WindowStruct(ctx.mem, win_addr)
            key = (
                event.text_key
                if win.IDCMPFlags.val & IDCMP_VANILLAKEY
                else event.raw_key
            )
            if key is not None:
                vanilla, code, qualifier = key
                return PendingIntuiEvent(
                    win_addr,
                    IDCMP_VANILLAKEY if vanilla else IDCMP_RAWKEY,
                    win.MouseX.val,
                    win.MouseY.val,
                    code,
                    window_id,
                    qualifier,
                )

        elif event.kind == "resize":
            scale = self._window_scales.get(window_id, self.display_scale)
            width, height = (
                max(1, int(event.x / scale[0])),
                max(1, int(event.y / scale[1])),
            )
            if self._resize_window(ctx, win_addr, width, height):
                return PendingIntuiEvent(win_addr, IDCMP_NEWSIZE, 0, 0, 0, window_id)
        elif event.kind == "expose":
            win = WindowStruct(ctx.mem, win_addr)
            self.refresh(ctx, win.RPort.val)
            return PendingIntuiEvent(win_addr, IDCMP_REFRESHWINDOW, 0, 0, 0, window_id)
        elif event.kind == "close":
            return PendingIntuiEvent(win_addr, IDCMP_CLOSEWINDOW, 0, 0, 0, window_id)
        return None

    def drain_pending_intui_events(self, ctx, e):
        if self.window_addresses.get(e.window_id) != e.win_addr:
            return
        self.queue_idcmp(
            ctx, e.win_addr, e.idcmp_flag, e.mouse_x, e.mouse_y, e.code, e.qualifier
        )

    def ReportMouse(self, ctx, flag, window):
        win = WindowStruct(ctx.mem, window)
        if flag:
            win.Flags.val |= 0x200  # WFLG_REPORTMOUSE
        else:
            win.Flags.val &= ~0x200

    def _reports_mouse(self, ctx, window):
        return bool(WindowStruct(ctx.mem, window).Flags.val & 0x200)

    def queue_idcmp(
        self, ctx, win_addr, idcmp_flag, mouse_x=0, mouse_y=0, code=0, qualifier=0
    ):
        if self.find_window_id(win_addr) is None:
            return
        win = WindowStruct(ctx.mem, win_addr)
        if idcmp_flag in (IDCMP_MOUSEMOVE, IDCMP_MOUSEBUTTONS):
            win.MouseX.val, win.MouseY.val = mouse_x, mouse_y

        if (win.IDCMPFlags.get() & idcmp_flag) == 0:
            # if idcmp_flag != IDCMP_INTUITICKS:
            #     log_intui.debug("IDCMP flag %x not set for window %08x, skipping", idcmp_flag, win_addr)
            return

        user_port_addr = win.UserPort.get()

        if idcmp_flag != IDCMP_MOUSEMOVE:
            log_intui.debug(
                "Queue IDCMP: %d at (%d, %d) code=%d win=%08x -> port=%08x",
                idcmp_flag,
                mouse_x,
                mouse_y,
                code,
                win_addr,
                user_port_addr,
            )

        if not user_port_addr:
            return
        owner = self._idcmp_owners.get(win_addr)
        if owner is None:
            memory = ctx.alloc.alloc_memory(
                MsgPortStruct.get_size(),
                label="Intuition reply port",
                except_on_failure=False,
            )
            if memory is None:
                return
            port = MsgPort(ctx.mem, memory.addr)
            port.new(sig_bit=0)
            port.flags.val = 2  # PA_IGNORE; replies are handled synchronously.
            owner = {"port": memory, "messages": {}, "closed": False}
            manager = ctx.exec_lib.msg_func.port_mgr
            manager.register_port(memory.addr)
            manager.ports[memory.addr].handler = lambda manager, addr: (
                self._reply_idcmp(ctx, owner, addr)
            )
            self._idcmp_owners[win_addr] = owner
            self._reply_owners[memory.addr] = owner
        # RAWKEY IAddress points to two previous code/qualifier pairs.
        # Keep the empty history alive until ReplyMsg, just like the message.
        rawkey_extra = 4 if idcmp_flag == IDCMP_RAWKEY else 0
        memory = ctx.alloc.alloc_memory(
            IntuiMessageStruct.get_size() + rawkey_extra,
            label="Intuition message",
            except_on_failure=False,
        )
        if memory is None:
            return
        ctx.mem.clear_block(memory.addr, memory.size, 0)
        msg = IntuiMessageStruct(ctx.mem, memory.addr)
        msg.ExecMessage.mn_ReplyPort.set(owner["port"].addr)
        msg.ExecMessage.mn_Length.val = IntuiMessageStruct.get_size()
        if rawkey_extra:
            msg.IAddress.val = memory.addr + IntuiMessageStruct.get_size()
        msg.Class.val = idcmp_flag
        msg.MouseX.val, msg.MouseY.val = mouse_x, mouse_y
        msg.Code.val = code & 0xFFFF
        msg.Qualifier.val = qualifier
        msg.IDCMPWindow.val = win_addr
        owner["messages"][memory.addr] = (memory, user_port_addr)
        try:
            ctx.exec_lib.msg_func.put_msg(
                MsgPort(ctx.mem, user_port_addr), Message(ctx.mem, memory.addr)
            )
        except Exception:
            owner["messages"].pop(memory.addr)
            ctx.alloc.free_memory(memory)
            raise

    def _release_idcmp_port(self, ctx, owner):
        if owner["closed"] and not owner["messages"]:
            manager = ctx.exec_lib.msg_func.port_mgr
            self._reply_owners.pop(owner["port"].addr, None)
            manager.unregister_port(owner["port"].addr)
            ctx.alloc.free_memory(owner["port"])

    def _reply_idcmp(self, ctx, owner, addr):
        value = owner["messages"].pop(addr, None)
        if value is not None:
            ctx.alloc.free_memory(value[0])
        self._release_idcmp_port(ctx, owner)

    def _close_idcmp(self, ctx, win_addr):
        owner = self._idcmp_owners.pop(win_addr, None)
        if owner is None:
            return
        owner["closed"] = True
        manager = ctx.exec_lib.msg_func.port_mgr
        for addr, (memory, port_addr) in tuple(owner["messages"].items()):
            queued = False
            port = manager.ports.get(port_addr)
            if port is not None and port.queue is not None:
                if addr in port.queue:
                    port.queue.remove(addr)
                    queued = True
            else:
                msg = Message(ctx.mem, addr)
                queued = msg.node.remove()
            if queued:
                owner["messages"].pop(addr)
                ctx.alloc.free_memory(memory)
        # Delivered messages remain valid until their owner calls ReplyMsg.
        self._release_idcmp_port(ctx, owner)

    def draw_menu(self, ctx, renderer, top_menu_addr, mouse_x=0, mouse_y=0):
        self.mouse_x = mouse_x
        self.mouse_y = mouse_y

        self.update_submenu_visibility(self.mouse_x, self.mouse_y)
        self.draw_menus(ctx, renderer, top_menu_addr)

    def update_submenu_visibility(self, mouse_x, mouse_y):
        while self.submenu_rects:
            x, y, w, h = self.submenu_rects[-1]
            if x <= mouse_x < x + w and y <= mouse_y < y + h:
                break
            self.submenu_rects.pop()

    def handle_menu_selection(self, ctx, win_addr, item):
        """
        Apply Amiga Intuition semantics:
        - MENUTOGGLE: toggle checkmark on/off
        - CHECKIT: mutually exclusive group, only one stays checked
        - Otherwise: just set CHECKED
        """
        flags = item.Flags.get()

        if flags & MENUTOGGLE:
            # toggle
            if flags & CHECKED:
                item.Flags.set(flags & ~CHECKED)
            else:
                item.Flags.set(flags | CHECKED)

        elif flags & CHECKIT and len(self.hovered_item_index) > 1:
            # only apply mutual exclusion for submenu items (not top menu)
            menu_addr = win_addr.MenuStrip.get()
            indexes = self.hovered_item_index.copy()

            # descend into the menu tree following indexes[:-1] to reach parent submenu
            current_addr = menu_addr
            for idx in indexes[:-1]:
                # first level: MenuStruct
                menu = MenuStruct(ctx.mem, current_addr)
                sub_addr = menu.FirstItem.get()
                for _ in range(idx):
                    sub_item = MenuItemStruct(ctx.mem, sub_addr)
                    sub_addr = sub_item.NextItem.get()
                current_addr = sub_addr

            # now current_addr points to first sibling in the group
            sibling_addr = current_addr
            while sibling_addr:
                sibling = MenuItemStruct(ctx.mem, sibling_addr)
                sflags = sibling.Flags.get()
                if sflags & CHECKIT:
                    sibling.Flags.set(sflags & ~CHECKED)
                sibling_addr = sibling.NextItem.get()

            # check this one
            item.Flags.set(flags | CHECKED)

        log_intui.debug(
            "Menu selection handled: %s", ctx.mem.r_cstr(item.ItemFill.get())
        )

    def render_menu_item(
        self,
        ctx,
        frame,
        text,
        x,
        y,
        w,
        h,
        enabled=True,
        hovered=False,
        checked=False,
        shortcut=None,
    ):
        font = self.graphics_lib.font_registry.get(self.graphics_lib.topaz_font)
        if font is not None:
            frame.menu_item(font, text, x, y, w, h, enabled, hovered, checked, shortcut)

    def draw_menus(self, ctx, renderer, top_menu_addr):
        item_addr = top_menu_addr
        start_x = 0
        start_y = 0
        default_w = 150
        default_h = 20

        self.hovered_item = None
        menu_index = 0

        while item_addr:
            item = MenuStruct(ctx.mem, item_addr)
            w = item.Width.get() or default_w
            h = item.Height.get() or default_h

            flags = item.Flags.get()
            enabled = bool(flags & MENUENABLED)
            checked = False

            hovered = enabled and (
                start_x <= self.mouse_x < start_x + w
                and start_y <= self.mouse_y < start_y + h
            )

            text_str_ptr = item.MenuName.get()
            text = "<unnamed>"
            if text_str_ptr:
                text = ctx.mem.r_cstr(text_str_ptr)

            # draw the menu item via helper
            self.render_menu_item(
                ctx,
                renderer,
                text,
                start_x,
                start_y,
                w,
                h,
                enabled=enabled,
                hovered=hovered,
                checked=checked,
            )

            submenu_addr = item.FirstItem.get()
            if submenu_addr and enabled:
                self.draw_submenu(
                    ctx,
                    renderer,
                    submenu_addr,
                    start_x,
                    start_y + h,
                    [menu_index],
                    force=hovered,
                )

            start_x += w
            item_addr = item.NextMenu.get()
            menu_index += 1

    def draw_submenu(
        self, ctx, renderer, item_addr, start_x, start_y, indexes, force=False
    ):
        if not force:
            if not any(
                x == start_x and y == start_y for (x, y, w, h) in self.submenu_rects
            ):
                return

        current_y = start_y
        default_h = 20
        default_w = 150
        max_w = default_w
        item_count = 0
        submenu_index = 0

        while item_addr:
            item = MenuItemStruct(ctx.mem, item_addr)
            w = item.Width.get() or default_w
            h = item.Height.get() or default_h
            max_w = max(max_w, w)

            flags = item.Flags.get()
            enabled = bool(flags & ITEMENABLED)
            checked = bool(flags & CHECKED)

            text_ptr = item.ItemFill.get()
            text = "<unnamed>"
            if text_ptr:
                intui_text = IntuiTextStruct(ctx.mem, text_ptr)
                text_str_ptr = intui_text.IText.get()
                if text_str_ptr:
                    text = ctx.mem.r_cstr(text_str_ptr)

            hovered = enabled and (
                start_x <= self.mouse_x < start_x + w
                and current_y <= self.mouse_y < current_y + h
            )
            if hovered:
                self.hovered_item = item
                self.hovered_item_index = indexes.copy()
                self.hovered_item_index.append(submenu_index)

            shortcut = None
            if flags & COMMSEQ:
                shortcut = chr(item.Command.get())

            # draw the submenu item via helper
            self.render_menu_item(
                ctx,
                renderer,
                text,
                start_x,
                current_y,
                w,
                h,
                enabled=enabled,
                hovered=hovered,
                checked=checked,
                shortcut=shortcut,
            )

            current_y += h
            item_count += 1
            submenu_index += 1
            item_addr = item.NextItem.get()

        total_h = item_count * default_h
        r = (start_x, start_y, max_w, total_h)
        if len(self.submenu_rects) == 0 or self.submenu_rects[-1] != r:
            self.submenu_rects.append(r)

    def create_screen(
        self,
        ctx,
        width,
        height,
        depth,
        text_attr_addr,
        title_ptr,
        detail_pen,
        block_pen,
        graphics=None,
    ):
        if graphics is None:
            graphics = self.graphics_lib
        if width <= 0 or not 1 <= depth <= 8:
            return None
        if height <= 0:
            height = 200
        if graphics is None:
            return None
        if not text_attr_addr:
            text_attr_addr = graphics.text_attr.addr
        with ExitStack() as rollback:
            memory = self.alloc.alloc_memory(
                ScreenStruct.get_size(),
                label="Intuition screen",
                except_on_failure=False,
            )
            if memory is None:
                return None
            rollback.callback(self.alloc.free_memory, memory)
            screen = ScreenStruct(ctx.mem, memory.addr)
            ctx.mem.clear_block(memory.addr, memory.size, 0)
            screen.Width.set(width)
            screen.Height.set(height)

            screen.Title.set(title_ptr)
            screen.DefaultTitle.set(title_ptr)

            screen.DetailPen.set(detail_pen)
            screen.BlockPen.set(block_pen)

            screen.BarHeight.set(9)
            screen.BarVBorder.set(1)
            screen.BarHBorder.set(1)
            screen.MenuVBorder.set(1)
            screen.MenuHBorder.set(1)
            screen.WBorTop.set(10)
            screen.WBorLeft.set(4)
            screen.WBorRight.set(4)
            screen.WBorBottom.set(4)

            color_map = graphics.GetColorMap(ctx, 1 << depth)
            if not color_map:
                return None
            rollback.callback(graphics.FreeColorMap, ctx, color_map)
            screen.ViewPort.ColorMap.val = color_map
            screen.ViewPort.DWidth.val = width
            screen.ViewPort.DHeight.val = height
            ctx.mem.w32(color_map + 20, screen.ViewPort.addr)
            if graphics.palette is not None:
                for n in range(1 << depth):
                    color = graphics.palette[n]
                    rgb = (
                        (color.r, color.g, color.b)
                        if hasattr(color, "r")
                        else color[:3]
                    )
                    graphics.SetRGB32CM(
                        ctx, color_map, n, *(c * 0x01010101 for c in rgb)
                    )

            # BitMap
            bm = screen.BitMap
            bytes_per_row = (width + 15) // 16 * 2
            bm.BytesPerRow.set(bytes_per_row)
            bm.Rows.set(height)
            bm.Depth.set(depth)
            bm.Flags.set(0)
            bm.pad.set(0)

            for i in range(depth):
                plane_size = bytes_per_row * height
                plane_ptr = self.alloc.alloc_mem(plane_size, except_on_fail=False)
                if not plane_ptr:
                    return None
                rollback.callback(self.alloc.free_mem, plane_ptr, plane_size)
                bm.Planes[i].set(plane_ptr)
            for i in range(depth, 8):
                bm.Planes[i].set(0)

            # The screen exposes TextAttr, while its RastPort needs an
            # opened TextFont. Keep both alive independently of caller
            # descriptors and mutable public RastPort fields.
            attr_memory = self.alloc.alloc_memory(
                TextAttrStruct.get_size(),
                label="Screen font attributes",
                except_on_failure=False,
            )
            if attr_memory is None:
                return None
            rollback.callback(self.alloc.free_memory, attr_memory)
            ctx.mem.w_block(
                attr_memory.addr,
                ctx.mem.r_block(text_attr_addr, TextAttrStruct.get_size()),
            )
            attr = TextAttrStruct(ctx.mem, attr_memory.addr)
            name_memory = None
            if attr.ta_Name.val:
                name = ctx.mem.r_cstr(attr.ta_Name.val)
                name_memory = self.alloc.alloc_memory(
                    len(name) + 1, label="Screen font name", except_on_failure=False
                )
                if name_memory is None:
                    return None
                rollback.callback(self.alloc.free_memory, name_memory)
                ctx.mem.w_cstr(name_memory.addr, name)
                attr.ta_Name.val = name_memory.addr
            font_addr = graphics._open_font(ctx, attr_memory.addr)
            if not font_addr:
                return None
            rollback.callback(graphics._close_font, ctx, font_addr)
            screen.Font.val = attr_memory.addr

            # RastPort
            rp = screen.RastPort
            rp.Layer.set(0)
            rp.BitMap.set(screen.BitMap.get_addr())
            rp.FgPen.set(detail_pen)
            rp.BgPen.set(block_pen)
            rp.DrawMode.set(JAM2)
            rp.cp_x.set(0)
            rp.cp_y.set(0)
            rp.Mask.set(0xFF)
            rp.LinePtrn.set(0xFFFF)
            graphics._set_font(ctx, rp.get_addr(), font_addr)
            rp.TxSpacing.val = 0

            self._screen_fonts[screen.get_addr()] = (
                graphics,
                font_addr,
                attr_memory,
                name_memory,
            )
            if graphics.palette is not None:
                graphics.screen_palettes[screen.ViewPort.addr] = graphics.palette.copy()
                graphics._color_palettes[color_map] = graphics.screen_palettes[
                    screen.ViewPort.addr
                ]
            rollback.pop_all()
            return screen

    def _free_screen(self, ctx, screen):
        self.graphics_lib.screen_palettes.pop(screen.ViewPort.addr, None)
        color_map = screen.ViewPort.ColorMap.val
        self.graphics_lib._color_palettes.pop(color_map, None)
        self.graphics_lib.FreeColorMap(ctx, color_map)
        bm = screen.BitMap
        plane_size = bm.BytesPerRow.val * bm.Rows.val
        planes = [bm.Planes[i].val for i in range(bm.Depth.val)]
        owned_font = self._screen_fonts.pop(screen.get_addr(), None)
        with ExitStack() as cleanup:
            cleanup.callback(screen.free, ctx.alloc)
            if owned_font is not None:
                graphics, font_addr, attr_memory, name_memory = owned_font
                cleanup.callback(ctx.alloc.free_memory, attr_memory)
                if name_memory is not None:
                    cleanup.callback(ctx.alloc.free_memory, name_memory)
                cleanup.callback(graphics._close_font, ctx, font_addr)
            for plane in planes:
                if plane:
                    cleanup.callback(ctx.alloc.free_mem, plane, plane_size)

    def ScrollWindowRaster(self, ctx):

        win_addr = ctx.cpu.r_reg(REG_A1)
        if not win_addr:
            return
        win = WindowStruct(ctx.mem, win_addr)
        graphics = self.graphics_lib.get_rp_graphics(win.RPort.val)
        if graphics is None:
            return
        dx, dy, left, top, right, bottom = [
            self._signed_word(ctx.cpu.r_reg(reg))
            for reg in (REG_D0, REG_D1, REG_D2, REG_D3, REG_D4, REG_D5)
        ]
        left, top = max(0, left), max(0, top)
        right, bottom = min(graphics.width - 1, right), min(graphics.height - 1, bottom)
        if (not dx and not dy) or left > right or top > bottom:
            return
        self._flush_batch(graphics)
        rp = RastPortStruct(ctx.mem, win.RPort.val)
        state = self.graphics_lib._raster_state(ctx, rp)
        if state is None:
            return
        graphics.surface.scroll(state, left, top, right, bottom, dx, dy)
        self._upload_surface(graphics)
        if win.WLayer.val:
            layer = LayerStruct(ctx.mem, win.WLayer.val)
            damage = layer.DamageList.val
            if damage:
                self.graphics_lib._replace_region(
                    ctx,
                    damage,
                    self.graphics_lib._region_rects(ctx, damage)
                    + [(left, top, right, bottom)],
                )
        self.refresh(ctx, win.RPort.val)
        window_id = self.find_window_id(win_addr)
        self.drain_pending_intui_events(
            ctx, PendingIntuiEvent(win_addr, IDCMP_REFRESHWINDOW, 0, 0, 0, window_id)
        )

    def WindowLimits(self, ctx, window, widthMin, heightMin, widthMax, heightMax):
        if self.find_window_id(window) is None:
            return 0
        win = WindowStruct(ctx.mem, window)
        success = 1
        for field, value, current, minimum in (
            (win.MinWidth, widthMin, win.Width.val, True),
            (win.MinHeight, heightMin, win.Height.val, True),
            (win.MaxWidth, widthMax, win.Width.val, False),
            (win.MaxHeight, heightMax, win.Height.val, False),
        ):
            value &= 0xFFFF
            if value:
                if (minimum and not 0 < value <= current) or (
                    not minimum and value < current
                ):
                    success = 0
                else:
                    field.val = value
        return success

    def SizeWindow(self, ctx, window, dx, dy):
        if self.find_window_id(window) is None:
            return
        win = WindowStruct(ctx.mem, window)
        width, height = self._pending_window_sizes.get(
            window, (win.Width.val, win.Height.val)
        )
        width += self._signed_word(dx)
        height += self._signed_word(dy)
        if win.Flags.val & 1:  # WFLG_SIZEGADGET
            width = max(win.MinWidth.val, min(width, win.MaxWidth.val))
            height = max(win.MinHeight.val, min(height, win.MaxHeight.val))
        if 0 < width <= 32767 and 0 < height <= 32767:
            self._pending_window_sizes[window] = (width, height)

    def _resize_window(self, ctx, window, width, height):
        win = WindowStruct(ctx.mem, window)
        if (win.Width.val, win.Height.val) == (width, height):
            return False
        if not self.graphics_lib.resize_window_rastport(
            ctx, win.RPort.val, width, height
        ):
            return False
        win.Width.val, win.Height.val = width, height
        win.GZZWidth.val = width - win.BorderLeft.val - win.BorderRight.val
        win.GZZHeight.val = height - win.BorderTop.val - win.BorderBottom.val
        self.refresh(ctx, win.RPort.val)
        return True

    def check_refresh(self, ctx):
        pending, self._pending_window_sizes = self._pending_window_sizes, {}
        for window, (width, height) in pending.items():
            window_id = self.find_window_id(window)
            if window_id is not None and self._resize_window(
                ctx, window, width, height
            ):
                scale = self._window_scales.get(window_id, self.display_scale)
                self.display.resize_window(
                    self.host_windows[window_id],
                    round(width * scale[0]),
                    round(height * scale[1]),
                )
                self.queue_idcmp(ctx, window, IDCMP_NEWSIZE)
                self.queue_idcmp(ctx, window, IDCMP_REFRESHWINDOW)
        # Applications draw in response to input without Begin/EndRefresh.
        # Present queued drawing once per scheduler pump, without generating
        # another IDCMP_REFRESHWINDOW (which would ask the guest to redraw).
        if self.graphics_lib is not None:
            for rp_addr, backing in self.graphics_lib.rp_graphics_map.items():
                if (
                    backing.batch.commands
                    or getattr(backing, "present_pending", False)
                    or getattr(getattr(backing, "surface", None), "dirty", False)
                ):
                    win_addr = self.rp_2_win_addr.get(rp_addr)
                    if win_addr is not None:
                        self.refresh_pending.add(win_addr)
        for win_addr in self.refresh_pending:
            self._perform_refresh(ctx, win_addr)

        self.refresh_pending.clear()

    def refresh(self, ctx, rastport_addr):
        win_addr = self.rp_2_win_addr[rastport_addr]

        if win_addr not in self.refresh_pending:
            log_intui.info("add refresh for %x", win_addr)
            # Mark as pending
            self.refresh_pending.add(win_addr)

    def _perform_refresh(self, ctx, win_addr):
        try:
            window_id = self.find_window_id(win_addr)
            host_window = self.host_windows[window_id]
            self.render(ctx, host_window, 0, 100)  # not in the menu
        except KeyError:
            pass

    # --- intuition.library: BeginRefresh ---
    def BeginRefresh(self, ctx):
        cpu = ctx.cpu
        win_addr = cpu.r_reg(REG_A0)
        win = WindowStruct(ctx.mem, win_addr)

        rastport_addr = win.RPort.get()
        rp_graphics = self.graphics_lib.get_rp_graphics(rastport_addr)
        self._flush_batch(rp_graphics)

        # Set clipping once
        clip_rects = self.graphics_lib._get_damage_clip_rects_for_rp(ctx, rastport_addr)
        rp_graphics.clip_rects = clip_rects

        rc = 0
        cpu.w_reg(REG_D0, rc)

    # --- intuition.library: EndRefresh ---
    def EndRefresh(self, ctx):

        cpu = ctx.cpu
        win_addr = cpu.r_reg(REG_A0)
        complete = cpu.r_reg(REG_D0)
        win = WindowStruct(ctx.mem, win_addr)

        rastport_addr = win.RPort.get()
        rp_graphics = self.graphics_lib.get_rp_graphics(rastport_addr)
        batch = rp_graphics.batch

        self._flush_batch(rp_graphics)
        rp_graphics.clip_rects = None

        # Invalidate once
        self.refresh(ctx, rastport_addr)

        if complete != 0:
            # Get the layer
            layer_addr = win.WLayer.get()
            if layer_addr != 0:
                layer = LayerStruct(ctx.mem, layer_addr)
                region_addr = layer.DamageList.get()
                if region_addr != 0:
                    # Tell graphics_lib to drop any damage tracking for this region
                    self.graphics_lib._clear_region(ctx, region_addr)

        # Return success
        cpu.w_reg(REG_D0, 0)

    # --- intuition.library: SetWindowPointerA ---
    def SetWindowPointerA(self, ctx):
        cpu = ctx.cpu
        win_addr = cpu.r_reg(REG_A0)
        taglist_addr = cpu.r_reg(REG_A1)

        rc = 0
        cpu.w_reg(REG_D0, rc)

    # --- intuition.library: ClearPointer ---
    def ClearPointer(self, ctx):
        cpu = ctx.cpu
        win_addr = cpu.r_reg(REG_A0)

        rc = 0
        cpu.w_reg(REG_D0, rc)

    def _upload_surface(self, graphics):
        palette = getattr(graphics, "palette", self.graphics_lib.palette)
        graphics.frame.upload(graphics.surface.pixels, palette)
        graphics.surface.dirty = False
        graphics.present_pending = True

    def _execute_indexed(self, graphics, command, clip):

        surface, state = graphics.surface, command.state
        if isinstance(command, BFDraw):
            surface.line(state, command.x1, command.y1, command.x2, command.y2, clip)
        elif isinstance(command, BitmapBlit):
            surface.bitmap_blit(
                state,
                command.x,
                command.y,
                command.w,
                command.h,
                command.pixels,
                command.mask,
                clip,
            )
        elif isinstance(command, BFTemplate):
            surface.template(
                state, command.x, command.y, command.w, command.h, command.pixels, clip
            )
        elif not isinstance(command, BFText):
            surface.fill(state, command.x, command.y, command.w, command.h, clip)
        else:
            width, height, pixels = self.display.font_mask(command.font, command.string)
            surface.template(state, command.x, command.y, width, height, pixels, clip)

    def _flush_batch(self, graphics):
        if not graphics.batch.commands:
            if getattr(getattr(graphics, "surface", None), "dirty", False):
                self._upload_surface(graphics)
            return
        clips = graphics.clip_rects
        if clips is None:
            clips = [graphics.clip_rect]
        user_clips = getattr(graphics, "user_clip_rects", None)
        if user_clips is not None:
            combined = []
            for clip in clips:
                for user in user_clips:
                    if clip is None:
                        combined.append(user)
                    else:
                        x, y = max(clip.x, user.x), max(clip.y, user.y)
                        right = min(clip.x + clip.w, user.x + user.w)
                        bottom = min(clip.y + clip.h, user.y + user.h)
                        if right > x and bottom > y:
                            combined.append(Rect(x, y, right - x, bottom - y))
            clips = combined
        commands = graphics.batch.commands
        # All normal drawing commands carry guest raster state. Invalid,
        # bitmap-less RastPorts cannot be drawn into a host framebuffer.
        if all(command.state is not None for command in commands):
            graphics.surface.load(commands[0].state)
            for clip in clips:
                for command in commands:
                    self._execute_indexed(graphics, command, clip)
            try:
                self._upload_surface(graphics)
            finally:
                # Guest pixels already changed; never replay XOR after failure.
                graphics.batch.clear()
        else:
            graphics.batch.clear()

    def GetScreenDrawInfo(self, ctx, screen):
        if not screen:
            return 0
        sc = ScreenStruct(ctx.mem, screen)
        block = ctx.alloc.alloc_memory(
            76, label="Screen DrawInfo", except_on_failure=False
        )
        if block is None:
            return 0
        addr = block.addr
        self._draw_infos[addr] = block
        ctx.mem.w16(addr, 3)
        ctx.mem.w16(addr + 2, 13)
        ctx.mem.w32(addr + 4, addr + 50)
        ctx.mem.w32(addr + 8, sc.RastPort.Font.val)
        ctx.mem.w16(addr + 12, sc.BitMap.Depth.val)
        ctx.mem.w16(addr + 14, 22)
        ctx.mem.w16(addr + 16, 44)
        ctx.mem.w32(addr + 18, 1)
        ctx.mem.w32(addr + 30, screen)
        for index, pen in enumerate((1, 0, 1, 2, 1, 3, 2, 0, 3, 1, 0, 1, 2)):
            ctx.mem.w16(addr + 50 + 2 * index, pen)
        return addr

    def FreeScreenDrawInfo(self, ctx, screen, info):
        block = self._draw_infos.pop(info, None)
        if block:
            ctx.alloc.free_memory(block)

    @property
    def boopsi(self):
        if self._boopsi is None:
            self._boopsi = Boopsi(self._boopsi_ctx)
        return self._boopsi

    def MakeClass(self, ctx, class_id, super_id, super_ptr, size, flags):
        name = ctx.mem.r_cstr(class_id) if class_id else None
        if not super_ptr:
            if not super_id:
                return 0
            super_name = ctx.mem.r_cstr(super_id)
            super_ptr = self.boopsi.public.get(super_name, 0)
        if not super_ptr:
            return 0
        return self.boopsi.make_class(name, super_ptr, size)

    def AddClass(self, ctx, cls):
        self.boopsi.add_class(cls)

    def RemoveClass(self, ctx, cls):
        self.boopsi.remove_class(cls)

    def FreeClass(self, ctx, cls):
        return self.boopsi.free_class(cls)

    def NewObjectA(self, ctx, cls, class_id, tags):
        if not cls and class_id:
            cls = self.boopsi.public.get(ctx.mem.r_cstr(class_id), 0)
        return self.boopsi.new_object(cls, tags)

    def DisposeObject(self, ctx, obj):
        self.boopsi.method(obj, 0x102)

    def SetAttrsA(self, ctx, obj, tags):
        return self.boopsi.method(obj, 0x103, tags, 0)

    def GetAttr(self, ctx, attr, obj, storage):
        return self.boopsi.method(obj, 0x104, attr, storage)

    def SetGadgetAttrsA(self, ctx, obj, window, requester, tags):
        if not window:
            return self.boopsi.method(obj, 0x103, tags, 0)
        if requester:
            return 0  # Requester-relative gadget domains are not supported.
        win = WindowStruct(ctx.mem, window)
        info = ctx.alloc.alloc_memory(
            58, label="BOOPSI GadgetInfo", except_on_failure=False
        )
        if info is None:
            return 0
        draw = 0
        try:
            draw = self.GetScreenDrawInfo(ctx, win.WScreen.val)
            if not draw:
                return 0
            for offset, value in (
                (0, win.WScreen.val),
                (4, window),
                (12, win.RPort.val),
                (16, win.WLayer.val),
                (30, draw),
            ):
                ctx.mem.w32(info.addr + offset, value)
            ctx.mem.w16(info.addr + 24, win.Width.val & 0xFFFF)
            ctx.mem.w16(info.addr + 26, win.Height.val & 0xFFFF)
            ctx.mem.w8(info.addr + 28, win.DetailPen.val)
            ctx.mem.w8(info.addr + 29, win.BlockPen.val)
            return self.boopsi.method(obj, 0x103, tags, info.addr)
        finally:
            if draw:
                self.FreeScreenDrawInfo(ctx, win.WScreen.val, draw)
            ctx.alloc.free_memory(info)

    def NextObject(self, ctx, state):
        node = ctx.mem.r32(state)
        if not node or not ctx.mem.r32(node):
            return 0
        ctx.mem.w32(state, ctx.mem.r32(node))
        return node + 12


class PendingIntuiEvent:
    __slots__ = (
        "win_addr",
        "idcmp_flag",
        "mouse_x",
        "mouse_y",
        "code",
        "window_id",
        "qualifier",
    )

    def __init__(
        self, win_addr, idcmp_flag, mouse_x, mouse_y, code, window_id, qualifier=0
    ):
        self.win_addr = win_addr
        self.idcmp_flag = idcmp_flag
        self.mouse_x = mouse_x
        self.mouse_y = mouse_y
        self.code = code
        self.window_id = window_id
        self.qualifier = qualifier
