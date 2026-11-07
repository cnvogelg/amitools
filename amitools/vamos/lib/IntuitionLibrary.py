import ctypes
from contextlib import ExitStack
from amitools.vamos.libtypes import TagList, MsgPort, Message
from amitools.vamos.lib.GraphicsLibrary import BFText, BFDraw
from amitools.vamos.libcore.impl import LibImpl
from amitools.vamos.lib.TimerDevice import TimerDevice

from amitools.vamos.lib.graphics import RastPortStruct, LayerStruct, RectangleStruct, TextAttrStruct, JAM2
from amitools.vamos.lib.intuition import WA_Left, WA_Top, WA_Width, WA_Height, WA_Title, WA_MinWidth, WA_MinHeight, WA_MaxWidth, WA_MaxHeight, WindowStruct, IDCMP_MOUSEMOVE, \
    IDCMP_MOUSEBUTTONS, IDCMP_RAWKEY, IDCMP_CLOSEWINDOW, IDCMP_NEWSIZE, IDCMP_REFRESHWINDOW, IntuiMessageStruct, MenuStruct, MenuItemStruct, IntuiTextStruct, IDCMP_MENUPICK, \
    NewWindowStruct, WA_IDCMP, ScreenStruct, NewScreenStruct, WA_CustomScreen
from amitools.vamos.log import log_intui
from amitools.vamos.machine.regs import REG_D0, REG_A0, REG_A1, REG_D1, REG_D2, REG_D3, REG_D4, REG_D5
from amitools.vamos.libstructs.exec_ import MsgPortStruct, MessageStruct

SDL_USEREVENT_TIMER = 32768 + 11

MENUNULL = 0xFFFF

MENUENABLED  = 0x0001

# MenuItem.Flags (from Intuition)
CHECKIT      = 0x0001  # Item is checkmarkable
ITEMTEXT     = 0x0002  # Item has textual label (else graphical)
COMMSEQ      = 0x0004  # Item has a command sequence
MENUTOGGLE   = 0x0008  # Toggle checks; otherwise mutually exclusive
ITEMENABLED  = 0x0010  # Item is enabled/active
CHECKED      = 0x0100
SUBMENU      = 0x0200  # Show standard submenu indicator (V47)


IECODE_UP_PREFIX = 0x80

IECODE_LBUTTON  = 0x68
IECODE_RBUTTON  = 0x69
IECODE_MBUTTON  = 0x6A

# def ts(label): print(f"{time.perf_counter():.6f} {label}")

class IntuitionLibrary(LibImpl):
    def __init__(self):
        super().__init__()
        # default init stuff
        self._easy_last = None
        self.alloc = None
        self.sdl_window_id_2_window_addr_map = {}  # SDL_Window id -> Amiga window address
        self.sdl_window_id_2_sdl_window = {}
        self.sdl_window_id_2_timer = {}
        self.menu_active = False
        self.mouse_x = 0
        self.mouse_y = 0
        self.submenu_rects = []
        self.hovered_item = None
        self.hovered_item_index = []
        self.graphics_lib_addr = None
        self.graphics_lib = None
        self.default_screen = None
        self._lib_opened = False   # guard flag
        self._default_title_memory = None
        self._sdl_flags = 0
        self._screen_fonts = {}
        self._idcmp_owners = {}
        self._reply_owners = {}
        self._window_ports = {}
        
        self.rp_2_win_addr = {}
        self.refresh_pending = set()
                
    def setup_lib(self, ctx, base_addr):
        # log_dos.info("setup intuition.library")
        self.alloc = ctx.alloc

        # Register with ExecLibrary
        ctx.exec_lib.intuition_lib = self

        # no graphics calls here

    def open_lib(self, ctx, open_cnt):
        """Perform graphics-dependent initialization (only once)."""
        if self._lib_opened:
            return  # already initialized

        # stay headless without sdl2: functions that really render
        # import sdl2 themselves and fail only when actually used
        try:
            import sdl2
        except ImportError:
            log_intui.warning("pysdl2 not installed, no display available")
            return
        flags = sdl2.SDL_INIT_VIDEO | sdl2.SDL_INIT_TIMER
        if sdl2.SDL_Init(flags) != 0:
            log_intui.warning("SDL initialization failed; no display available")
            return
        with ExitStack() as rollback:
            rollback.callback(sdl2.SDL_QuitSubSystem, flags)
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
                ctx, 800, 600, 3, graphics.text_attr.addr, title.addr, 1, 0,
                graphics=graphics,
            )
            if screen is None:
                return
            self.default_screen = screen
            self._default_title_memory = title
            self.graphics_lib_addr = graphics_addr
            self.graphics_lib = graphics
            self._sdl_flags = flags
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
        flags = self._sdl_flags
        self._lib_opened = False
        self.default_screen = None
        self._default_title_memory = None
        self.graphics_lib_addr = None
        self._sdl_flags = 0
        try:
            with ExitStack() as cleanup:
                import sdl2
                cleanup.callback(sdl2.SDL_QuitSubSystem, flags)
                cleanup.callback(ctx.lib_mgr.close_lib, graphics_addr)
                cleanup.callback(ctx.alloc.free_memory, title)
                for screen in screens:
                    cleanup.callback(self._free_screen, ctx, screen)
                for window in tuple(self.sdl_window_id_2_window_addr_map.values()):
                    cleanup.callback(self._close_window_addr, ctx, window)
        finally:
            self.graphics_lib = None

    def finish_lib(self, ctx):
        # No guest can return an outstanding message after library teardown.
        for owner in tuple(self._reply_owners.values()):
            owner["closed"] = True
            for memory, _ in owner["messages"].values():
                ctx.alloc.free_memory(memory)
            owner["messages"].clear()
            self._release_idcmp_port(ctx, owner)
        self._idcmp_owners.clear()

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

    def find_sdl_window_by_amiga_addr(self, addr):
        for sdl_win, amiga_addr in self.sdl_window_id_2_window_addr_map.items():
            if amiga_addr == addr:
                return sdl_win
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

        # A removed timer can already have queued an event. Invalidate its
        # window ID before stopping it or releasing any guest resources.
        window_id = self.find_sdl_window_by_amiga_addr(window_ptr)
        sdl_win = self.sdl_window_id_2_sdl_window.pop(window_id, None)
        timer_id = self.sdl_window_id_2_timer.pop(window_id, 0)
        self.sdl_window_id_2_window_addr_map.pop(window_id, None)
        self.refresh_pending.discard(window_ptr)
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
                log_intui.info("Unlinked window 0x%08X from screen 0x%08X", window_ptr, screen_ptr)
                break
        
            prev_ptr = current_ptr
            current_ptr = next_ptr

        self._close_idcmp(ctx, window_ptr)

        # Release the port and renderer before the structures and host
        # window they belong to. Attempt all releases if one raises.
        with ExitStack() as cleanup:
            if sdl_win is not None or timer_id:
                import sdl2
            if sdl_win is not None:
                cleanup.callback(sdl2.SDL_DestroyWindow, sdl_win)
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
            if timer_id:
                sdl2.SDL_RemoveTimer(timer_id)

    def OpenWindow(self, ctx):
        if self.default_screen is None:
            ctx.cpu.w_reg(REG_D0, 0)
            return
        import sdl2

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
        
        
        flags = sdl2.SDL_WINDOW_SHOWN
        # Determine if window should be resizable
        if width > min_width or height > min_height or width < max_width or height < max_height:
            flags |= sdl2.SDL_WINDOW_RESIZABLE
      
        amiga_win_addr = self.create_window_struct(ctx, left, top, width, height, idcmp_flags, title, screen, flags)
        
        ctx.cpu.w_reg(REG_D0, amiga_win_addr)

    def OpenWindowTagList(self, ctx):
        if self.default_screen is None:
            ctx.cpu.w_reg(REG_D0, 0)
            return
        import sdl2

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

        new_window_ptr = ctx.cpu.r_reg(REG_A0)
        if new_window_ptr != 0:
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

        # Reuse Utility's typed iterator for MORE, SKIP and IGNORE tags.
        for item in TagList(ctx.mem, taglist_ptr):
            tag, data = item.get_tag(), item.get_data()

            if tag == WA_Left:
                left = data
            elif tag == WA_Top:
                top = data
            elif tag == WA_Width:
                width = data
            elif tag == WA_Height:
                height = data
            elif tag == WA_Title:
                title = ctx.mem.r_cstr(data) if data else ""
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
            elif tag == WA_CustomScreen:
                screen = data
            else:
                log_intui.warning("OpenWindowTagList: unknown tag 0x%08X with data 0x%08X", tag, data)

        
        log_intui.info("OpenWindowTagList: '%s' at (%d, %d) size (%d x %d)",
                      title, left, top, width, height)

        flags = sdl2.SDL_WINDOW_SHOWN
        if width > min_width or height > min_height or width < max_width or height < max_height:
            flags |= sdl2.SDL_WINDOW_RESIZABLE        

        # Return fake Amiga window pointer
        amiga_win_addr = self.create_window_struct(ctx, left, top, width, height, idcmp_flags, title, screen, flags)
        ctx.cpu.w_reg(REG_D0, amiga_win_addr)

    def SetMenuStrip(self, ctx):
        win_addr = ctx.cpu.r_reg(REG_A0)
        menu_addr = ctx.cpu.r_reg(REG_A1)
    
        win = WindowStruct(ctx.mem, win_addr)
        win.MenuStrip.set(menu_addr)
    
        log_intui.info("SetMenuStrip: attached menu at 0x%08X to window 0x%08X", menu_addr, win_addr)
    
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
    
        screen = self.create_screen(ctx, width, height, depth, font_ptr, title_ptr, detail_pen, block_pen)
        if screen is None:
            ctx.cpu.w_reg(REG_D0, 0)
            return
    
        # Link into screen list
        screen.NextScreen.set(self.default_screen.NextScreen.get())
        self.default_screen.NextScreen.set(screen.addr)
    
        ctx.cpu.w_reg(REG_D0, screen.addr)
        log_intui.info(f"OpenScreen: created and linked screen at 0x{screen.addr:X}")

        
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
                        font_addr = self.graphics_lib._open_font(ctx, itext.ITextFont.val)
                        if font_addr:
                            self.graphics_lib._set_font(ctx, rastport_addr, font_addr)
                    rp.cp_x.val = self._signed_word(left + itext.LeftEdge.val)
                    rp.cp_y.val = self._signed_word(top + itext.TopEdge.val + rp.TxBaseline.val)
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
        menu_ptr = ctx.cpu.r_reg(REG_A0)      # Pointer to MenuStruct
        menu_number = ctx.cpu.r_reg(REG_D0)   # Packed menu number
    
        if menu_number == MENUNULL or menu_ptr == 0:
            ctx.cpu.w_reg(REG_D0, 0)
            return
    
        # Decode menu number
        menu_index    = menu_number & 0x1F
        item_index    = (menu_number >> 5) & 0x3F
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

    def create_window_struct(self, ctx, left, top, width, height, idcmp_flags, title, screen_addr, flags):
        if not (0 < width <= 32767 and 0 < height <= 32767):
            return 0
        if self.graphics_lib is None or (not screen_addr and self.default_screen is None):
            return 0
        import sdl2
        
        log_intui.info("Opening SDL2 window: '%s' at (%d, %d) size (%d x %d)",
              title, left, top, width, height)
        # Create SDL2 window
        sdl_win = sdl2.SDL_CreateWindow(
            title.encode("utf-8"),
            sdl2.SDL_WINDOWPOS_CENTERED,  # SDL2 doesn't support exact positioning cross-platform
            sdl2.SDL_WINDOWPOS_CENTERED,
            width,
            height,
            flags
        )

        if not sdl_win:
            log_intui.error("Failed to create SDL2 window")
            return 0

        with ExitStack() as rollback:
            rollback.callback(sdl2.SDL_DestroyWindow, sdl_win)
            title_memory = self.alloc.alloc_memory(
                len(title.encode("latin-1")) + 1, label="Window title",
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
                WindowStruct.get_size(), label="Intuition window",
                except_on_failure=False,
            )
            if memory is None:
                return 0
            rollback.callback(ctx.alloc.free_memory, memory)
            ctx.mem.clear_block(memory.addr, memory.size, 0)
            win = WindowStruct(ctx.mem, memory.addr)
            win.Width.val, win.Height.val = width, height
            win.LeftEdge.val, win.TopEdge.val = left, top
            win.IDCMPFlags.val = idcmp_flags
            win.Title.set(title_memory.addr)
            win.UserPort.val = user_port.addr if user_port is not None else 0
            win.WScreen.val = screen_addr or self.default_screen.addr
            screen = ScreenStruct(ctx.mem, win.WScreen.val)
            rp_addr, layer_addr, _ = self.graphics_lib.create_window_rastport(
                ctx, sdl_win, width, height, screen.BitMap.Depth.val or 2
            )
            if not rp_addr:
                return 0
            rollback.callback(self.graphics_lib.free_RastPortStruct, ctx, rp_addr)
            win.RPort.val, win.WLayer.val = rp_addr, layer_addr
            window_id = sdl2.SDL_GetWindowID(sdl_win)
            timer_id = sdl2.SDL_AddTimer(
                50, intuiticks_timer_callback, ctypes.c_void_p(window_id)
            )
            if not timer_id:
                return 0
            rollback.callback(sdl2.SDL_RemoveTimer, timer_id)
            ctx.exec_lib.register_SDL_poll(ctx)
            # Only complete windows are visible to events and screen lists.
            win.NextWindow.val = screen.FirstWindow.val
            screen.FirstWindow.val = win.addr
            if user_port is not None:
                self._window_ports[win.addr] = user_port.addr
            self.rp_2_win_addr[rp_addr] = win.addr
            self.sdl_window_id_2_window_addr_map[window_id] = win.addr
            self.sdl_window_id_2_sdl_window[window_id] = sdl_win
            self.sdl_window_id_2_timer[window_id] = timer_id
            rollback.pop_all()
        return win.addr

    def render(self, ctx, sdl_win, mouse_x = 0, mouse_y = 0):
        import sdl2

        window_id = sdl2.SDL_GetWindowID(sdl_win)
        log_intui.info("render for window %d", window_id)
    
        try:
            window_ptr = self.sdl_window_id_2_window_addr_map[window_id]
        except KeyError:
            return
    
        window = WindowStruct(ctx.mem, window_ptr)
        rastport_addr = window.RPort.get()
        rp_graphics = self.graphics_lib.get_rp_graphics(rastport_addr)
        if not rp_graphics:
            log_intui.error("No RastPort found for window %08x", window_ptr)
            return
    
        # Get window size
        win_w = ctypes.c_int()
        win_h = ctypes.c_int()
        sdl2.SDL_GetWindowSize(sdl_win, ctypes.byref(win_w), ctypes.byref(win_h))
    
        # Get texture size
        tex_w = ctypes.c_int()
        tex_h = ctypes.c_int()
        sdl2.SDL_QueryTexture(rp_graphics.texture, None, None, ctypes.byref(tex_w), ctypes.byref(tex_h))
    
        # Clip src_rect to texture bounds
        src_rect = sdl2.SDL_Rect(0, 0, min(win_w.value, tex_w.value), min(win_h.value, tex_h.value))
        dst_rect = sdl2.SDL_Rect(0, 0, src_rect.w, src_rect.h)
    
        # Render cropped texture
        renderer = rp_graphics.renderer
        sdl2.SDL_SetRenderTarget(renderer, None)
        
        self._flush_batch(rp_graphics)
        result = sdl2.SDL_RenderCopy(renderer, rp_graphics.texture, src_rect, dst_rect)
        if result != 0:
            log_intui.error("Failed to render cropped texture for rastport address %08x", rastport_addr)
    
        # Draw menu overlay if active
        if self.menu_active:
            menu_addr = window.MenuStrip.get()
            if menu_addr:
                self.draw_menu(ctx, renderer, menu_addr, mouse_x, mouse_y)
    
    
        # # Fill with a random color each time 
        # r = random.randint(0, 255) 
        # g = random.randint(0, 255) 
        # b = random.randint(0, 255) 
        # sdl2.SDL_SetRenderDrawColor(renderer, r, g, b, 255) 
        # sdl2.SDL_RenderClear(renderer)
        
        sdl2.SDL_RenderPresent(renderer)

    def encode_selection(self, idx):
        if len(idx) == 2:
            return (idx[0] & 0x1f) | (idx[1] << 5)
        elif len(idx) == 3:
            return (idx[0] & 0x1f) | ((idx[1] << 5) & 0x3f) | (idx[2] << 11)
        return idx[0] & 0x1f

    def ingest_sdl_event(self, ctx, event):
        import sdl2

        # Quit is global and has no window ID. Other events must belong
        # to a currently live window; never redirect an unknown ID to 1.
        if event.type == sdl2.SDL_QUIT:
            for win_addr in tuple(self.sdl_window_id_2_window_addr_map.values()):
                self.queue_idcmp(ctx, win_addr, IDCMP_CLOSEWINDOW)
            return None
        window_id = getattr(getattr(event, "window", None), "windowID", 0)
        win_addr = self.sdl_window_id_2_window_addr_map.get(window_id)
        if win_addr is None:
            return None

        # ---------- MOUSE MOTION ----------
        if event.type == sdl2.SDL_MOUSEMOTION:
            mx, my = event.motion.x, event.motion.y
    
            # Menu hover redraw
            if self.menu_active:
                sdl_win = sdl2.SDL_GetWindowFromID(window_id)
                self.render(ctx, sdl_win, mx, my)

            return PendingIntuiEvent(win_addr, IDCMP_MOUSEMOVE, mx, my, 0, window_id)

        # ---------- MOUSE BUTTON DOWN ----------
        elif event.type == sdl2.SDL_MOUSEBUTTONDOWN:
            mx, my = event.button.x, event.button.y
            btn = event.button.button
    
            # IECODE mapping
            if btn == sdl2.SDL_BUTTON_LEFT:
                code = 0x68
            elif btn == sdl2.SDL_BUTTON_RIGHT:
                code = 0x69
            elif btn == sdl2.SDL_BUTTON_MIDDLE:
                code = 0x6A
            else:
                code = 0
    
            # Menu activation
            if btn == sdl2.SDL_BUTTON_RIGHT and not self.menu_active:
                self.menu_active = True
                self.hovered_item = None
                self.hovered_item_index = []
                self.submenu_rects = []
                sdl_win = sdl2.SDL_GetWindowFromID(window_id)
                self.render(ctx, sdl_win, mx, my)

            return PendingIntuiEvent(
                win_addr, IDCMP_MOUSEBUTTONS, mx, my, code, window_id
            )

        # ---------- MOUSE BUTTON UP ----------
        elif event.type == sdl2.SDL_MOUSEBUTTONUP:
            mx, my = event.button.x, event.button.y
            btn = event.button.button
    
            # IECODE mapping
            if btn == sdl2.SDL_BUTTON_LEFT:
                code = 0xE8
            elif btn == sdl2.SDL_BUTTON_RIGHT:
                code = 0xE9
            elif btn == sdl2.SDL_BUTTON_MIDDLE:
                code = 0xEA
            else:
                code = 0
    
            # MENUPICK
            if self.menu_active and self.hovered_item is not None:
                idx = self.hovered_item_index
                if len(idx) == 2:
                    selection = (idx[0] & 0x1F) | (idx[1] << 5) | (0x1f << 11)
                else:
                    selection = (idx[0] & 0x1F) | ((idx[1] << 5) & 0x3F) | (idx[2] << 11)
    
                # Apply CHECKIT/MENUTOGGLE
                self.handle_menu_selection(ctx, win_addr, self.hovered_item)
    
                # Reset menu
                self.menu_active = False
                self.hovered_item = None
                self.hovered_item_index = []
                self.submenu_rects = []
    
                sdl_win = sdl2.SDL_GetWindowFromID(window_id)
                self.render(ctx, sdl_win)
    
                # Deliver MENUPICK immediately
                self.queue_idcmp(ctx, win_addr, IDCMP_MENUPICK, mx, my, code=selection)
                return None
    
            # Normal button-up
            if self.menu_active and btn in (sdl2.SDL_BUTTON_LEFT, sdl2.SDL_BUTTON_RIGHT):
                self.menu_active = False
                self.hovered_item = None
                self.hovered_item_index = []
                self.submenu_rects = []
                sdl_win = sdl2.SDL_GetWindowFromID(window_id)
                self.render(ctx, sdl_win)

            return PendingIntuiEvent(
                win_addr, IDCMP_MOUSEBUTTONS, mx, my, code, window_id
            )

        # ---------- KEY DOWN ----------
        elif event.type == sdl2.SDL_KEYDOWN:
            keycode = event.key.keysym.sym
            return PendingIntuiEvent(win_addr, IDCMP_RAWKEY, 0, 0, keycode, window_id)

        # ---------- WINDOW EVENTS ----------
        elif event.type == sdl2.SDL_WINDOWEVENT:
            we = event.window.event
    
            if we == sdl2.SDL_WINDOWEVENT_RESIZED:
                new_w = event.window.data1
                new_h = event.window.data2
    
                win = WindowStruct(ctx.mem, win_addr)
                win.Width.set(new_w)
                win.Height.set(new_h)

                return PendingIntuiEvent(win_addr, IDCMP_NEWSIZE, 0, 0, 0, window_id)

            elif we == sdl2.SDL_WINDOWEVENT_EXPOSED:
                # Only one refresh per expose
                win = WindowStruct(ctx.mem, win_addr)
                rastport_addr = win.RPort.get()
                self.refresh(ctx, rastport_addr)
                return PendingIntuiEvent(
                    win_addr, IDCMP_REFRESHWINDOW, 0, 0, 0, window_id
                )

            elif we == sdl2.SDL_WINDOWEVENT_CLOSE:
                return PendingIntuiEvent(
                    win_addr, IDCMP_CLOSEWINDOW, 0, 0, 0, window_id
                )

        return None
    
    def drain_pending_intui_events(self, ctx, e):
        if self.sdl_window_id_2_window_addr_map.get(e.window_id) != e.win_addr:
            return
        self.queue_idcmp(ctx, e.win_addr, e.idcmp_flag, e.mouse_x, e.mouse_y, e.code)

    def queue_idcmp(self, ctx, win_addr, idcmp_flag, mouse_x=0, mouse_y=0, code=0):
        if self.find_sdl_window_by_amiga_addr(win_addr) is None:
            return
        win = WindowStruct(ctx.mem, win_addr)
        
        if (win.IDCMPFlags.get() & idcmp_flag) == 0:
            # if idcmp_flag != IDCMP_INTUITICKS:
            #     log_intui.debug("IDCMP flag %x not set for window %08x, skipping", idcmp_flag, win_addr)
            return
        
        user_port_addr = win.UserPort.get()

        if idcmp_flag != IDCMP_MOUSEMOVE:
            log_intui.debug("Queue IDCMP: %d at (%d, %d) code=%d win=%08x -> port=%08x", idcmp_flag, mouse_x, mouse_y, code, win_addr, user_port_addr)
        
        if not user_port_addr:
            return
        owner = self._idcmp_owners.get(win_addr)
        if owner is None:
            memory = ctx.alloc.alloc_memory(
                MsgPortStruct.get_size(), label="Intuition reply port",
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
            manager.ports[memory.addr].handler = (
                lambda manager, addr: self._reply_idcmp(ctx, owner, addr)
            )
            self._idcmp_owners[win_addr] = owner
            self._reply_owners[memory.addr] = owner
        memory = ctx.alloc.alloc_memory(
            IntuiMessageStruct.get_size(), label="Intuition message",
            except_on_failure=False,
        )
        if memory is None:
            return
        ctx.mem.clear_block(memory.addr, memory.size, 0)
        msg = IntuiMessageStruct(ctx.mem, memory.addr)
        msg.ExecMessage.mn_ReplyPort.set(owner["port"].addr)
        msg.ExecMessage.mn_Length.val = IntuiMessageStruct.get_size()
        msg.Class.val = idcmp_flag
        msg.MouseX.val, msg.MouseY.val = mouse_x, mouse_y
        msg.Code.val = code & 0xFFFF
        msg.IDCMPWindow.val = win_addr
        owner["messages"][memory.addr] = (memory, user_port_addr)
        try:
            ctx.exec_lib.msg_func.put_msg(MsgPort(ctx.mem, user_port_addr),
                                          Message(ctx.mem, memory.addr))
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
    
        log_intui.debug("Menu selection handled: %s", ctx.mem.r_cstr(item.ItemFill.get()))


    def render_menu_item(self, ctx, renderer, text, x, y, w, h,
                         enabled=True, hovered=False, checked=False, shortcut=None):
        import sdl2
    
        amiga_font = self.graphics_lib.topaz_font
        font = self.graphics_lib.font_registry.get(amiga_font)
        if not font:
            return
    
        # Farben
        if not enabled:
            bg_color = (96, 96, 96)
            text_color = sdl2.SDL_Color(160, 160, 160)
        else:
            bg_color = (255, 255, 255) if hovered else (32, 32, 32)
            text_color = sdl2.SDL_Color(0, 0, 0) if hovered else sdl2.SDL_Color(222, 222, 222)
    
        # Hintergrund
        sdl2.SDL_SetRenderDrawColor(renderer, *bg_color, 255)
        sdl2.SDL_RenderFillRect(renderer, sdl2.SDL_Rect(x, y, w, h))
    
        # Checkmark
        if checked:
            # Coordinates relative to the menu item box
            # Adjust offsets and lengths to taste
            start_x = x + 4
            start_y = y + 8
            mid_x   = x + 8
            mid_y   = y + 12
            end_x   = x + 14
            end_y   = y + 4
        
            sdl2.SDL_SetRenderDrawColor(renderer, 0, 0, 0, 255)
        
            # Draw the "tick" shape: short down-left stroke, then long up-right stroke
            sdl2.SDL_RenderDrawLine(renderer, start_x, start_y, mid_x, mid_y)
            sdl2.SDL_RenderDrawLine(renderer, mid_x, mid_y, end_x, end_y)
    
        # Text
        if text:
            text_surface = sdl2.sdlttf.TTF_RenderUTF8_Solid(font, text.encode("utf-8"), text_color)
            if text_surface:
                text_texture = sdl2.SDL_CreateTextureFromSurface(renderer, text_surface)
                text_rect = sdl2.SDL_Rect(x + 16, y + 2,
                                          text_surface.contents.w, text_surface.contents.h)
                sdl2.SDL_RenderCopy(renderer, text_texture, None, text_rect)
                sdl2.SDL_FreeSurface(text_surface)
                sdl2.SDL_DestroyTexture(text_texture)
    
        # Shortcut rechts
        if shortcut:
            sc_surface = sdl2.sdlttf.TTF_RenderUTF8_Solid(font, shortcut.encode("utf-8"), text_color)
            if sc_surface:
                sc_texture = sdl2.SDL_CreateTextureFromSurface(renderer, sc_surface)
                sc_rect = sdl2.SDL_Rect(x + w - sc_surface.contents.w - 4,
                                        y + 2,
                                        sc_surface.contents.w,
                                        sc_surface.contents.h)
                sdl2.SDL_RenderCopy(renderer, sc_texture, None, sc_rect)
                sdl2.SDL_FreeSurface(sc_surface)
                sdl2.SDL_DestroyTexture(sc_texture)
            
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
    
            hovered = enabled and (start_x <= self.mouse_x < start_x + w and
                                   start_y <= self.mouse_y < start_y + h)
    
            text_str_ptr = item.MenuName.get()
            text = "<unnamed>"
            if text_str_ptr:
                text = ctx.mem.r_cstr(text_str_ptr)
    
            # draw the menu item via helper
            self.render_menu_item(ctx, renderer, text,
                                  start_x, start_y, w, h,
                                  enabled=enabled,
                                  hovered=hovered,
                                  checked=checked)
    
            submenu_addr = item.FirstItem.get()
            if submenu_addr and enabled:
                self.draw_submenu(ctx, renderer, submenu_addr,
                                  start_x, start_y + h,
                                  [menu_index], force=hovered)
    
            start_x += w
            item_addr = item.NextMenu.get()
            menu_index += 1
    
    
    def draw_submenu(self, ctx, renderer, item_addr, start_x, start_y, indexes, force=False):
        if not force:
            if not any(x == start_x and y == start_y for (x, y, w, h) in self.submenu_rects):
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
    
            hovered = enabled and (start_x <= self.mouse_x < start_x + w and
                                   current_y <= self.mouse_y < current_y + h)
            if hovered:
                self.hovered_item = item
                self.hovered_item_index = indexes.copy()
                self.hovered_item_index.append(submenu_index)
    
            shortcut = None
            if flags & COMMSEQ:
                shortcut = chr(item.Command.get())
    
            # draw the submenu item via helper
            self.render_menu_item(ctx, renderer, text,
                                  start_x, current_y, w, h,
                                  enabled=enabled,
                                  hovered=hovered,
                                  checked=checked,
                                  shortcut=shortcut)
    
            current_y += h
            item_count += 1
            submenu_index += 1
            item_addr = item.NextItem.get()
    
        total_h = item_count * default_h
        r = (start_x, start_y, max_w, total_h)
        if len(self.submenu_rects) == 0 or self.submenu_rects[-1] != r:
            self.submenu_rects.append(r)

    def create_screen(self, ctx, width, height, depth, text_attr_addr, title_ptr, detail_pen, block_pen, graphics=None):
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
                ScreenStruct.get_size(), label="Intuition screen",
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
                TextAttrStruct.get_size(), label="Screen font attributes",
                except_on_failure=False,
            )
            if attr_memory is None:
                return None
            rollback.callback(self.alloc.free_memory, attr_memory)
            ctx.mem.w_block(
                attr_memory.addr, ctx.mem.r_block(text_attr_addr, TextAttrStruct.get_size())
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
                graphics, font_addr, attr_memory, name_memory
            )
            rollback.pop_all()
            return screen

    def _free_screen(self, ctx, screen):
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
        import sdl2
        win_addr = ctx.cpu.r_reg(REG_A1)
        if not win_addr:
            return
        win = WindowStruct(ctx.mem, win_addr)
        graphics = self.graphics_lib.get_rp_graphics(win.RPort.val)
        if graphics is None:
            return
        dx, dy, left, top, right, bottom = [self._signed_word(ctx.cpu.r_reg(reg))
            for reg in (REG_D0, REG_D1, REG_D2, REG_D3, REG_D4, REG_D5)]
        left, top = max(0, left), max(0, top)
        right, bottom = min(graphics.width - 1, right), min(graphics.height - 1, bottom)
        if (not dx and not dy) or left > right or top > bottom:
            return
        self._flush_batch(graphics)
        renderer = graphics.renderer
        temporary = sdl2.SDL_CreateTexture(
            renderer, sdl2.SDL_PIXELFORMAT_RGBA8888, sdl2.SDL_TEXTUREACCESS_TARGET,
            graphics.width, graphics.height,
        )
        if not temporary:
            return
        try:
            sdl2.SDL_SetRenderTarget(renderer, temporary)
            sdl2.SDL_RenderCopy(renderer, graphics.texture, None, None)
            sdl2.SDL_SetRenderTarget(renderer, graphics.texture)
            rp = RastPortStruct(ctx.mem, win.RPort.val)
            color = self.graphics_lib._pen_color(ctx, rp, rp.BgPen.val)
            sdl2.SDL_SetRenderDrawBlendMode(renderer, sdl2.SDL_BLENDMODE_NONE)
            sdl2.SDL_SetRenderDrawColor(renderer, color.r, color.g, color.b, 255)
            sdl2.SDL_RenderFillRect(renderer,
                sdl2.SDL_Rect(left, top, right-left+1, bottom-top+1))
            width, height = right-left+1-abs(dx), bottom-top+1-abs(dy)
            if width > 0 and height > 0:
                source = sdl2.SDL_Rect(left+max(dx,0), top+max(dy,0), width, height)
                target = sdl2.SDL_Rect(left+max(-dx,0), top+max(-dy,0), width, height)
                sdl2.SDL_RenderCopy(renderer, temporary, source, target)
        finally:
            sdl2.SDL_SetRenderTarget(renderer, None)
            sdl2.SDL_DestroyTexture(temporary)
        if win.WLayer.val:
            layer = LayerStruct(ctx.mem, win.WLayer.val)
            damage = layer.DamageList.val
            if damage:
                self.graphics_lib._replace_region(ctx, damage,
                    self.graphics_lib._region_rects(ctx, damage) + [(left,top,right,bottom)])
        self.refresh(ctx, win.RPort.val)
        window_id = self.find_sdl_window_by_amiga_addr(win_addr)
        self.drain_pending_intui_events(ctx, PendingIntuiEvent(
            win_addr, IDCMP_REFRESHWINDOW, 0, 0, 0, window_id))

    def check_refresh(self, ctx):
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
            window_id = self.find_sdl_window_by_amiga_addr(win_addr)
            sdl_win = self.sdl_window_id_2_sdl_window[window_id]
            self.render(ctx, sdl_win, 0, 100) # not in the menu
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
        import sdl2
        cpu = ctx.cpu
        win_addr = cpu.r_reg(REG_A0)
        complete = cpu.r_reg(REG_D0)
        win = WindowStruct(ctx.mem, win_addr)
    
        rastport_addr = win.RPort.get()
        rp_graphics = self.graphics_lib.get_rp_graphics(rastport_addr)
        batch = rp_graphics.batch
    
        renderer = rp_graphics.renderer
        texture = rp_graphics.texture
    
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


    def _execute_batch(self, renderer, batch):
        for command in batch.commands:
            if isinstance(command, BFText):
                self._execute_texts(renderer, [command])
            elif isinstance(command, BFDraw):
                self._execute_draws(renderer, [command])
            else:
                self._execute_rectfills(renderer, [command])

    def _flush_batch(self, graphics):
        if not graphics.batch.commands:
            return
        import sdl2
        renderer = graphics.renderer
        sdl2.SDL_SetRenderTarget(renderer, graphics.texture)
        try:
            clips = getattr(graphics, "clip_rects", None)
            if clips is None:
                clips = [graphics.clip_rect]
            for clip in clips:
                sdl2.SDL_RenderSetClipRect(renderer, clip)
                self._execute_batch(renderer, graphics.batch)
            graphics.batch.clear()
        finally:
            sdl2.SDL_RenderSetClipRect(renderer, None)
            sdl2.SDL_SetRenderTarget(renderer, None)

    def _execute_rectfills(self, renderer, rectfills):
        import sdl2

        for rf in rectfills:
            sdl2.SDL_SetRenderDrawBlendMode(renderer,
                sdl2.SDL_BLENDMODE_NONE if rf.draw_mode in (0,1)
                else sdl2.SDL_BLENDMODE_MOD
            )
            sdl2.SDL_SetRenderDrawColor(renderer,
                rf.color.r, rf.color.g, rf.color.b, 255
            )
            rect = sdl2.SDL_Rect(rf.x, rf.y, rf.w, rf.h)
            sdl2.SDL_RenderFillRect(renderer, rect)

    def _execute_draws(self, renderer, draws):
        import sdl2
        for d in draws:
            sdl2.SDL_SetRenderDrawBlendMode(renderer,
                sdl2.SDL_BLENDMODE_NONE if d.draw_mode in (0,1)
                else sdl2.SDL_BLENDMODE_MOD
            )
            sdl2.SDL_SetRenderDrawColor(renderer,
                d.color.r, d.color.g, d.color.b, 255
            )
            sdl2.SDL_RenderDrawLine(renderer, d.x1, d.y1, d.x2, d.y2)

    def _execute_texts(self, renderer, texts):
        import sdl2
        from sdl2 import sdlttf
        for text in texts:
            mode = text.draw_mode & 3
            foreground, background = text.fg, text.bg
            if text.draw_mode & 4:  # INVERSVID swaps the two pens.
                foreground, background = background, foreground
            if mode == 1:  # JAM2 fills the text background as well.
                surface = sdlttf.TTF_RenderUTF8_Shaded(
                    text.font, text.string.encode("utf-8"), foreground, background
                )
            else:
                surface = sdlttf.TTF_RenderUTF8_Solid(
                    text.font, text.string.encode("utf-8"), foreground
                )
            if not surface:
                continue
            with ExitStack() as cleanup:
                cleanup.callback(sdl2.SDL_FreeSurface, surface)
                texture = sdl2.SDL_CreateTextureFromSurface(renderer, surface)
                if not texture:
                    continue
                cleanup.callback(sdl2.SDL_DestroyTexture, texture)
                rect = sdl2.SDL_Rect(text.x, text.y, surface.contents.w, surface.contents.h)
                sdl2.SDL_RenderCopy(renderer, texture, None, rect)

@ctypes.CFUNCTYPE(ctypes.c_uint32, ctypes.c_uint32, ctypes.c_void_p)
def intuiticks_timer_callback(interval, param):
    import sdl2

    window_id = ctypes.cast(param, ctypes.c_void_p).value 

    event = sdl2.SDL_Event()
    event.type = SDL_USEREVENT_TIMER
    event.window.windowID = window_id  # Embed window ID here
    event.user.data1 = None
    event.user.data2 = None
    sdl2.SDL_PushEvent(ctypes.byref(event))
    return interval

class PendingIntuiEvent:
    __slots__ = ("win_addr", "idcmp_flag", "mouse_x", "mouse_y", "code", "window_id")

    def __init__(self, win_addr, idcmp_flag, mouse_x, mouse_y, code, window_id):
        self.win_addr = win_addr
        self.idcmp_flag = idcmp_flag
        self.mouse_x = mouse_x
        self.mouse_y = mouse_y
        self.code = code
        self.window_id = window_id
