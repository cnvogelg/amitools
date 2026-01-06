import ctypes

from amitools.vamos.lib.graphics import RastPortStruct, LayerStruct, RectangleStruct
from amitools.vamos.lib.intuition import WA_Left, WA_Top, WA_Width, WA_Height, WA_Title, WA_MinWidth, WA_MinHeight, WA_MaxWidth, WA_MaxHeight, WindowStruct, IDCMP_MOUSEMOVE, \
    IDCMP_MOUSEBUTTONS, IDCMP_RAWKEY, IDCMP_CLOSEWINDOW, IDCMP_NEWSIZE, IDCMP_REFRESHWINDOW, IntuiMessageStruct, MenuStruct, MenuItemStruct, IntuiTextStruct, IDCMP_MENUPICK, \
    NewWindowStruct, WA_IDCMP, ScreenStruct, NewScreenStruct, WA_CustomScreen
from amitools.vamos.libcore import LibImpl
from amitools.vamos.log import log_intui
from amitools.vamos.machine.regs import REG_D0, REG_A0, REG_A1, REG_D1, REG_D2, REG_D3, REG_D4, REG_D5
import time

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
        self.alloc = None
        self.sdl_window_id_2_window_addr_map = {}  # SDL_Window id -> Amiga window address
        self.sdl_window_id_2_sdl_window = {}
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

        import sdl2
        sdl2.SDL_Init(sdl2.SDL_INIT_VIDEO | sdl2.SDL_INIT_TIMER)

        # open graphics.library
        self.graphics_lib_addr = ctx.lib_mgr.open_lib("graphics.library")
        self.graphics_lib = ctx.exec_lib.graphics_lib

        # create default screen
        self.default_screen = self.create_screen(
            ctx,
            width=800,
            height=600,
            depth=3,
            text_attr_addr=self.graphics_lib.text_attr.addr,
            title_ptr=ctx.alloc.alloc_cstr("Workbench").addr,
            detail_pen=1,
            block_pen=0
        )

        self._lib_opened = True
        
    def close_lib(self, ctx, open_cnt):
        if open_cnt == 0:
            # close default screen
            title_addr = self.default_screen.DefaultTitle.get() 
            ctx.cpu.w_reg(REG_A0, self.default_screen.addr)
            self.CloseScreen(ctx)
            self.alloc.free_cstr_by_addr(title_addr)
            
            ctx.lib_mgr.close_lib(self.graphics_lib_addr)

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

    def EasyRequestArgs(self, ctx):
        EasyStruct = ctx.cpu.r_reg(REG_A1)
        es_TextFormat = ctx.mem.r32(EasyStruct + 12)  # EasyStruct.es_TextFormat
        msg = ctx.mem.r_cstr(es_TextFormat)
        log_intui.error("-----> EasyRequest '%s'", msg)

    def find_sdl_window_by_amiga_addr(self, addr):
        for sdl_win, amiga_addr in self.sdl_window_id_2_window_addr_map.items():
            if amiga_addr == addr:
                return sdl_win
        return None

    def CloseWindow(self, ctx):
        window_ptr = ctx.cpu.r_reg(REG_A0)
        log_intui.info("Closing window @%08x", window_ptr)
    
        # Load WindowStruct
        win = WindowStruct(ctx.mem, window_ptr)
    
        screen_ptr = win.WScreen.get()
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
    
        # Free title string
        title_addr = win.Title.get()
        if title_addr:
            self.alloc.free_cstr_by_addr(title_addr)
    
        # Free RastPortStruct and BitMapStruct
        rastPortStruct_addr = win.RPort.get()
        if rastPortStruct_addr:
            self.graphics_lib.free_RastPortStruct(ctx, rastPortStruct_addr)
            self.rp_2_win_addr.pop(rastPortStruct_addr, None)
                
        # Free WindowStruct itself
        ctx.alloc.free_mem(window_ptr, WindowStruct.get_size())
    
        # Delete UserPort
        user_port_addr = win.UserPort.get()
        if user_port_addr:
            ctx.cpu.w_reg(REG_A0, user_port_addr)
            ctx.exec_lib.DeleteMsgPort(ctx)
    
        # SDL2 cleanup
        window_id = self.find_sdl_window_by_amiga_addr(window_ptr)
        if window_id > 0:
            import sdl2
    
            # Destroy SDL2 window
            sdl_win = self.sdl_window_id_2_sdl_window[window_id]
            sdl2.SDL_DestroyWindow(sdl_win)
            del self.sdl_window_id_2_sdl_window[window_id]
    

    def OpenWindow(self, ctx):
        import sdl2

        new_window_ptr = ctx.cpu.r_reg(REG_A0)

        new_win = NewWindowStruct(ctx.mem, new_window_ptr)
        left = new_win.LeftEdge.get()
        top = new_win.TopEdge.get()
        width = new_win.Width.get()
        height = new_win.Height.get()

        idcmp_flags = new_win.IDCMPFlags.get()

        title_ptr = new_win.Title.get()
        title = ctx.mem.r_cstr(title_ptr)

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
        
        screen = self.default_screen

        new_window_ptr = ctx.cpu.r_reg(REG_A0)
        if new_window_ptr != 0:
            new_win = NewWindowStruct(ctx.mem, new_window_ptr)
            left = new_win.LeftEdge.get()
            top = new_win.TopEdge.get()
            width = new_win.Width.get()
            height = new_win.Height.get()
    
            idcmp_flags = new_win.IDCMPFlags.get()

            title_ptr = new_win.Title.get()
            title = ctx.mem.r_cstr(title_ptr)
    
            min_width = new_win.MinWidth.get()
            min_height = new_win.MinHeight.get()
            max_width = new_win.MaxWidth.get()
            max_height = new_win.MaxHeight.get()
            
            screen = new_win.Screen.get()

        # Parse tag list
        while True:
            tag = ctx.mem.r32(taglist_ptr)
            data = ctx.mem.r32(taglist_ptr + 4)
            taglist_ptr += 8

            if tag == 0:  # TAG_END
                break

            if tag == WA_Left:
                left = data
            elif tag == WA_Top:
                top = data
            elif tag == WA_Width:
                width = data
            elif tag == WA_Height:
                height = data
            elif tag == WA_Title:
                title = ctx.mem.r_cstr(data)
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
        amiga_win_addr = self.create_window_struct(ctx, left, top, width, height, idcmp_flags, title, screen.addr, flags)
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
        idcmp_flags = ctx.cpu.r_reg(REG_D0)

        win = WindowStruct(ctx.mem, win_addr)
        current_flags = win.IDCMPFlags.get()
        win.IDCMPFlags.set(idcmp_flags)

        log_intui.info("ModifyIDCMP: window 0x%08X, new IDCMP flags: 0x%08X", win_addr, current_flags)

        ctx.cpu.w_reg(REG_D0, current_flags)  # Return old flags

    def OpenScreen(self, ctx):
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
    
        # Link into screen list
        screen.NextScreen.set(self.default_screen.NextScreen.get())
        self.default_screen.NextScreen.set(screen.addr)
    
        ctx.cpu.w_reg(REG_D0, screen.addr)
        log_intui.info(f"OpenScreen: created and linked screen at 0x{screen.addr:X}")

        
    def CloseScreen(self, ctx):
        target_ptr = ctx.cpu.r_reg(REG_A0)
    
        prev = None
        current_ptr = self.default_screen.addr
    
        while current_ptr:
            current = ScreenStruct(ctx.mem, current_ptr)
            if current_ptr == target_ptr:
                # Unlink from list
                if prev != None:
                    prev.NextScreen.set(current.NextScreen.get())
    
                # Free bitmap planes
                bm = current.BitMap
                bytes_per_row = bm.BytesPerRow.get()
                rows = bm.Rows.get()
                depth = bm.Depth.get()
    
                for i in range(depth):
                    plane_addr = bm.Planes[i].get()
                    if plane_addr:
                        self.alloc.free_mem(plane_addr, bytes_per_row * rows)
        
                # Free screen struct
                self.alloc.free_mem(current_ptr, current.get_size())
                log_intui.info(f"CloseScreen: screen at 0x{current_ptr:X} removed and freed")
                return
    
            prev = current
            current_ptr = current.NextScreen.get()
    
        log_intui.warning(f"CloseScreen: screen at 0x{target_ptr:X} not found in list")

    def PrintIText(self, ctx):
        rastport_addr = ctx.cpu.r_reg(REG_A0)
        rp = RastPortStruct(ctx.mem, rastport_addr)
    
        left = ctx.cpu.r_reg(REG_D0)
        top = ctx.cpu.r_reg(REG_D1)
    
        intui_text_ptr = ctx.cpu.r_reg(REG_A1)
    
        while intui_text_ptr:
            itext = IntuiTextStruct(ctx.mem, intui_text_ptr)
    
            # Sign-extend LeftEdge and TopEdge
            x = itext.LeftEdge.get()
            y = itext.TopEdge.get()
            if x & 0x8000:
                x -= 0x10000
            if y & 0x8000:
                y -= 0x10000
    
            # Move pen to (x, y)
            rp.cp_x.set(x + left)
            rp.cp_y.set(y + top)
    
            # Set pens
            rp.FgPen.set(itext.FrontPen.get())
            rp.BgPen.set(itext.BackPen.get())
    
            # Set draw mode
            rp.DrawMode.set(itext.DrawMode.get())
    
            # Set up registers for Text()
            ctx.cpu.w_reg(REG_A1, rastport_addr)
            ctx.cpu.w_reg(REG_A0, itext.IText.get())
    
            # Call Text() directly
            log_intui.debug("Printing IntuiText at (%d, %d): '%s'", x + left, y + top, ctx.mem.r_cstr(itext.IText.get()))
            self.graphics_lib.Text(ctx)
            
            # Move to next IntuiTextStruct
            intui_text_ptr = itext.NextText.get()

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

        # Allocate title string in Amiga memory
        title_ptr = self.alloc.alloc_cstr(title)
    
        user_port = ctx.exec_lib.CreateMsgPort(ctx)
    
        # Create WindowStruct instance
        win = WindowStruct.alloc(ctx.alloc)
        ctx.mem.clear_block(win.addr, win.get_size(), 0)
        
        win.Width.set(width)
        win.Height.set(height)
        win.IDCMPFlags.set(idcmp_flags)
        win.Title.set(title_ptr.addr)
        win.LeftEdge.set(left)
        win.TopEdge.set(top)
        win.UserPort.set(user_port)
        
        win.WScreen.set(screen_addr or self.default_screen.addr)
        # Link window into screen's window list
        screen = ScreenStruct(ctx.mem, win.WScreen.get())
        win.NextWindow.set(screen.FirstWindow.get())
        screen.FirstWindow.set(win.addr)
        
        log_intui.debug("WindowStruct created at 0x%08X: %s", win.addr, win)
        
        # Allocate BitMap + Layer + RastPort with SDL2 backing
        rp_addr, layer_addr, _ = self.graphics_lib.create_window_rastport(
            ctx,
            sdl_win,
            screen.Width.get(),
            screen.Height.get()
        )
        
        self.rp_2_win_addr[rp_addr] = win.addr;
        
        # Attach to Intuition Window
        win.RPort.set(rp_addr)
        win.WLayer.set(layer_addr)
        
        window_id = sdl2.SDL_GetWindowID(sdl_win)
        self.sdl_window_id_2_window_addr_map[window_id] = win.addr
        self.sdl_window_id_2_sdl_window[window_id] = sdl_win

        # start a timer
        sdl2.SDL_AddTimer(50, intuiticks_timer_callback, ctypes.c_void_p(window_id))

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
    
        # Determine window ID
        window_id = getattr(event, "window", None)
        if window_id:
            window_id = event.window.windowID
        if not window_id:
            window_id = 1
    
        try:
            win_addr = self.sdl_window_id_2_window_addr_map[window_id]
        except KeyError:
            return None
    
        # ---------- MOUSE MOTION ----------
        if event.type == sdl2.SDL_MOUSEMOTION:
            mx, my = event.motion.x, event.motion.y
    
            # Menu hover redraw
            if self.menu_active:
                sdl_win = sdl2.SDL_GetWindowFromID(window_id)
                self.render(ctx, sdl_win, mx, my)
    
            return PendingIntuiEvent(win_addr, IDCMP_MOUSEMOVE, mx, my, 0)
    
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
    
            return PendingIntuiEvent(win_addr, IDCMP_MOUSEBUTTONS, mx, my, code)
    
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
    
            return PendingIntuiEvent(win_addr, IDCMP_MOUSEBUTTONS, mx, my, code)
    
        # ---------- KEY DOWN ----------
        elif event.type == sdl2.SDL_KEYDOWN:
            keycode = event.key.keysym.sym
            return PendingIntuiEvent(win_addr, IDCMP_RAWKEY, 0, 0, keycode)
    
        # ---------- SDL QUIT ----------
        elif event.type == sdl2.SDL_QUIT:
            return PendingIntuiEvent(win_addr, IDCMP_CLOSEWINDOW, 0, 0, 0)
    
        # ---------- WINDOW EVENTS ----------
        elif event.type == sdl2.SDL_WINDOWEVENT:
            we = event.window.event
    
            if we == sdl2.SDL_WINDOWEVENT_RESIZED:
                new_w = event.window.data1
                new_h = event.window.data2
    
                win = WindowStruct(ctx.mem, win_addr)
                win.Width.set(new_w)
                win.Height.set(new_h)
    
                return PendingIntuiEvent(win_addr, IDCMP_NEWSIZE, 0, 0, 0)
    
            elif we == sdl2.SDL_WINDOWEVENT_EXPOSED:
                # Only one refresh per expose
                win = WindowStruct(ctx.mem, win_addr)
                rastport_addr = win.RPort.get()
                self.refresh(ctx, rastport_addr)
                return PendingIntuiEvent(win_addr, IDCMP_REFRESHWINDOW, 0, 0, 0)
    
            elif we == sdl2.SDL_WINDOWEVENT_CLOSE:
                return PendingIntuiEvent(win_addr, IDCMP_CLOSEWINDOW, 0, 0, 0)
        
        return None
    
    def drain_pending_intui_events(self, ctx, e):
        self.queue_idcmp(
            ctx,
            e.win_addr,
            e.idcmp_flag,
            e.mouse_x,
            e.mouse_y,
            e.code
        )

    def queue_idcmp(self, ctx, win_addr, idcmp_flag, mouse_x=0, mouse_y=0, code=0):
        win = WindowStruct(ctx.mem, win_addr)
        
        if (win.IDCMPFlags.get() & idcmp_flag) == 0:
            # if idcmp_flag != IDCMP_INTUITICKS:
            #     log_intui.debug("IDCMP flag %x not set for window %08x, skipping", idcmp_flag, win_addr)
            return
        
        user_port_addr = win.UserPort.get()

        if idcmp_flag != IDCMP_MOUSEMOVE:
            log_intui.debug("Queue IDCMP: %d at (%d, %d) code=%d win=%08x -> port=%08x", idcmp_flag, mouse_x, mouse_y, code, win_addr, user_port_addr)
        
        # Allocate and fill IntuiMessage
        msg_addr = ctx.alloc.alloc_struct(IntuiMessageStruct)
        msg = IntuiMessageStruct(ctx.mem, msg_addr.addr)
        msg.ExecMessage.mn_ReplyPort.set(0XFFEDCB)
        msg.Class.set(idcmp_flag)        
        msg.MouseX.set(mouse_x)
        msg.MouseY.set(mouse_y)
        msg.Code.set(code & 0xffff)  # Ensure code is a UWORD
        msg.IDCMPWindow.set(win_addr)

        # Post to message list
        ctx.exec_lib._put_msg_core(ctx, user_port_addr, msg.addr)

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

    def create_screen(self, ctx, width, height, depth, text_attr_addr, title_ptr, detail_pen, block_pen):
        screen = ScreenStruct.alloc(self.alloc)
        ctx.mem.clear_block(screen.addr, screen.get_size(), 0)
    
        if height <= 0:
            height = 200
    
        screen.Width.set(width)
        screen.Height.set(height)
    
        screen.Font.set(text_attr_addr if text_attr_addr else self.graphics_lib.text_attr.addr)
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
            plane_ptr = self.alloc.alloc_mem(plane_size)
            bm.Planes[i].set(plane_ptr)
        for i in range(depth, 8):
            bm.Planes[i].set(0)
    
        # RastPort
        rp = screen.RastPort
        rp.Layer.set(0)
        rp.BitMap.set(screen.BitMap.get_addr())
        rp.FgPen.set(detail_pen)
        rp.BgPen.set(block_pen)
        rp.DrawMode.set(2)
        rp.cp_x.set(0)
        rp.cp_y.set(0)
        rp.Mask.set(0xFF)
        rp.LinePtrn.set(0xFFFF)
        rp.Font.set(screen.Font.get())    
    
        return screen

    def ScrollWindowRaster(self, ctx):
        """
        Intuition's ScrollWindowRaster()
        A1 = struct Window*
        D0 = dx
        D1 = dy
        D2 = xmin
        D3 = ymin
        D4 = xmax
        D5 = ymax
    
        Dummy implementation:
        - does NOT scroll pixels
        - marks the window as damaged
        - triggers IDCMP_REFRESHWINDOW
        """
    
        win_addr = ctx.cpu.r_reg(REG_A1)
        if win_addr == 0:
            return
    
        win = WindowStruct(ctx.mem, win_addr)
    
        # Get the layer
        layer_addr = win.WLayer.get()
        if layer_addr == 0:
            return
    
        layer = LayerStruct(ctx.mem, layer_addr)
    
        # --- Create a temporary rectangle for the damaged area ---
        rect = RectangleStruct.alloc(ctx.alloc)
        rect.MinX.set(0x7fff & ctx.cpu.r_reg(REG_D2))
        rect.MinY.set(0x7fff & ctx.cpu.r_reg(REG_D3))
        rect.MaxX.set(0x7fff & ctx.cpu.r_reg(REG_D4))
        rect.MaxY.set(0x7fff & ctx.cpu.r_reg(REG_D5))
    
        # --- Add to DamageList ---
        dl_addr = layer.DamageList.get()
        if dl_addr:
            self.graphics_lib._or_rect_region(ctx, dl_addr, rect.addr)
    
        # Free temporary rectangle
        ctx.alloc.free_mem(rect.addr, RectangleStruct.get_size())
    
        if win_addr not in self.refresh_pending:
            rastport_addr = win.RPort.get()
            self.refresh(ctx, rastport_addr)
            event = PendingIntuiEvent(win_addr, IDCMP_REFRESHWINDOW, 0, 0, 0)
            self.drain_pending_intui_events(ctx, event)
    
        # Intuition's ScrollWindowRaster() returns void
        return

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
        rp_graphics.batch.clear()

    # Set clipping once
        clip_rect = self.graphics_lib._get_damage_clip_rect_for_rp(ctx, rastport_addr)
        rp_graphics.clip_rect = clip_rect
        
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
    
        # Set target once
        sdl2.SDL_SetRenderTarget(renderer, texture)
    
        # Set clip once
        if rp_graphics.clip_rect is not None:
            sdl2.SDL_RenderSetClipRect(renderer, rp_graphics.clip_rect)
    
        # Execute batched primitives
        self._execute_rectfills(renderer, batch.rectfills)
        self._execute_draws(renderer, batch.draws)
        self._execute_texts(renderer, batch.texts)
    
        # Reset
        sdl2.SDL_RenderSetClipRect(renderer, None)
        sdl2.SDL_SetRenderTarget(renderer, None)
    
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
        import sdl2, sdl2.sdlttf as sdlttf
        for t in texts:
            # TODO: glyph cache here
            surface = sdlttf.TTF_RenderUTF8_Solid(t.font, t.string.encode(), t.fg)
            texture = sdl2.SDL_CreateTextureFromSurface(renderer, surface)
    
            rect = sdl2.SDL_Rect(t.x, t.y, surface.contents.w, surface.contents.h)
            sdl2.SDL_RenderCopy(renderer, texture, None, rect)
    
            sdl2.SDL_DestroyTexture(texture)
            sdl2.SDL_FreeSurface(surface)

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
    __slots__ = ("win_addr", "idcmp_flag", "mouse_x", "mouse_y", "code")

    def __init__(self, win_addr, idcmp_flag, mouse_x, mouse_y, code):
        self.win_addr = win_addr
        self.idcmp_flag = idcmp_flag
        self.mouse_x = mouse_x
        self.mouse_y = mouse_y
        self.code = code
