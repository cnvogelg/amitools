"""SDL window, framebuffer, input and optional host-font implementation."""

import ctypes

from .base import Display, Event, Frame, Window


class SDLFrame(Frame):
    def __init__(self, display, window, width, height, texture):
        super().__init__(display, window, width, height)
        self.texture = texture

    def present(self, scale=(1, 1)):
        import sdl2

        data = self.overlay or self.rgba
        values = (ctypes.c_uint32 * (self.width * self.height))(
            *(int.from_bytes(data[i : i + 4], "big") for i in range(0, len(data), 4))
        )
        renderer = self.window.renderer
        sdl2.SDL_SetRenderTarget(renderer, None)
        if sdl2.SDL_UpdateTexture(self.texture, None, values, self.width * 4) != 0:
            raise RuntimeError("SDL texture update failed")
        width, height = ctypes.c_int(), ctypes.c_int()
        sdl2.SDL_GetWindowSize(
            self.window.handle, ctypes.byref(width), ctypes.byref(height)
        )
        src = sdl2.SDL_Rect(
            0,
            0,
            min(self.width, int(width.value / scale[0])),
            min(self.height, int(height.value / scale[1])),
        )
        dst = sdl2.SDL_Rect(0, 0, round(src.w * scale[0]), round(src.h * scale[1]))
        if sdl2.SDL_RenderCopy(renderer, self.texture, src, dst) != 0:
            raise RuntimeError("SDL frame presentation failed")
        sdl2.SDL_RenderPresent(renderer)

    def close(self):
        import sdl2

        if self.texture:
            sdl2.SDL_DestroyTexture(self.texture)
            self.texture = None


class SDLDisplay(Display):
    interactive = True

    def __init__(self):
        super().__init__()
        self.opened = False
        self.fonts_opened = False

    def open(self):
        if self.opened:
            return True
        try:
            import sdl2
        except ImportError:
            return False
        flags = sdl2.SDL_INIT_VIDEO | sdl2.SDL_INIT_TIMER
        self.opened = sdl2.SDL_Init(flags) == 0
        return self.opened

    def close(self):
        super().close()
        if self.opened:
            import sdl2

            sdl2.SDL_QuitSubSystem(sdl2.SDL_INIT_VIDEO | sdl2.SDL_INIT_TIMER)
            self.opened = False

    def create_window(self, title, width, height, resizable=False):
        import sdl2

        flags = sdl2.SDL_WINDOW_SHOWN
        if resizable:
            flags |= sdl2.SDL_WINDOW_RESIZABLE
        handle = sdl2.SDL_CreateWindow(
            title.encode("utf-8"),
            sdl2.SDL_WINDOWPOS_CENTERED,
            sdl2.SDL_WINDOWPOS_CENTERED,
            width,
            height,
            flags,
        )
        if not handle:
            return None
        window = Window(sdl2.SDL_GetWindowID(handle), title, width, height, resizable)
        window.handle, window.renderer = handle, None
        self.windows[window.id] = window
        return window

    def create_frame(self, window, width, height):
        import sdl2

        if not window.renderer:
            window.renderer = sdl2.SDL_CreateRenderer(
                window.handle,
                -1,
                sdl2.SDL_RENDERER_ACCELERATED | sdl2.SDL_RENDERER_PRESENTVSYNC,
            )
            if not window.renderer:
                window.renderer = sdl2.SDL_CreateRenderer(window.handle, -1, 0)
            if not window.renderer:
                return None
        texture = sdl2.SDL_CreateTexture(
            window.renderer,
            sdl2.SDL_PIXELFORMAT_RGBA8888,
            sdl2.SDL_TEXTUREACCESS_TARGET,
            width,
            height,
        )
        if not texture:
            return None
        return SDLFrame(self, window, width, height, texture)

    def close_window(self, window):
        import sdl2

        if self.windows.pop(window.id, None) is not None:
            if window.renderer:
                sdl2.SDL_DestroyRenderer(window.renderer)
            sdl2.SDL_DestroyWindow(window.handle)

    def resize_window(self, window, width, height):
        import sdl2

        super().resize_window(window, width, height)
        sdl2.SDL_SetWindowSize(window.handle, width, height)

    @staticmethod
    def convert_event(event):
        import sdl2

        from .sdl_input import translate_key

        kind = event.type
        if kind == sdl2.SDL_QUIT:
            return Event("quit")
        wid = event.window.windowID
        if kind == sdl2.SDL_MOUSEMOTION:
            return Event("motion", wid, event.motion.x, event.motion.y)
        if kind in (sdl2.SDL_MOUSEBUTTONDOWN, sdl2.SDL_MOUSEBUTTONUP):
            return Event(
                "button_down" if kind == sdl2.SDL_MOUSEBUTTONDOWN else "button_up",
                wid,
                event.button.x,
                event.button.y,
                event.button.button,
            )
        if kind in (sdl2.SDL_KEYDOWN, sdl2.SDL_KEYUP):
            args = {
                "released": kind == sdl2.SDL_KEYUP,
                "repeat": bool(event.key.repeat),
            }
            return Event(
                "key",
                wid,
                raw_key=translate_key(event.key.keysym, **args),
                text_key=translate_key(event.key.keysym, vanilla=True, **args),
            )
        if kind == sdl2.SDL_WINDOWEVENT:
            kinds = {
                sdl2.SDL_WINDOWEVENT_RESIZED: "resize",
                sdl2.SDL_WINDOWEVENT_EXPOSED: "expose",
                sdl2.SDL_WINDOWEVENT_CLOSE: "close",
            }
            name = kinds.get(event.window.event)
            if name:
                return Event(name, wid, event.window.data1, event.window.data2)
        return None

    def poll(self, wait_ms=0, limit=64):
        import sdl2

        event = sdl2.SDL_Event()
        result = []
        for n in range(limit):
            got = (
                sdl2.SDL_WaitEventTimeout(event, wait_ms)
                if n == 0 and wait_ms
                else sdl2.SDL_PollEvent(event)
            )
            if not got:
                break
            translated = self.convert_event(event)
            if translated:
                result.append(translated)
        return result

    def request_fields(self, title, fields):
        from .sdl_requester import request_fields

        return request_fields(title, fields)

    def open_fonts(self):
        try:
            from sdl2 import sdlttf
        except ImportError:
            return False
        self.fonts_opened = sdlttf.TTF_Init() == 0
        return self.fonts_opened

    def close_fonts(self):
        if self.fonts_opened:
            from sdl2 import sdlttf

            sdlttf.TTF_Quit()
            self.fonts_opened = False

    def open_font(self, path, height, style):
        if not self.fonts_opened:
            return None
        from sdl2 import sdlttf

        from ..lib.graphics_font import BitmapFont
        from .sdl_font import open_pixel_font, read_font_strike

        flags = (
            (sdlttf.TTF_STYLE_UNDERLINE if style & 1 else 0)
            | (sdlttf.TTF_STYLE_BOLD if style & 2 else 0)
            | (sdlttf.TTF_STYLE_ITALIC if style & 4 else 0)
        )
        font = open_pixel_font(path, height, flags)
        if not font:
            return None
        try:
            size = sdlttf.TTF_FontHeight(font)
            strike = read_font_strike(font, size)
            if strike is None:
                return None
            metrics = self.text_size(font, "M")
            if metrics is None:
                return None
            width, _ = metrics
            return BitmapFont(width, size, sdlttf.TTF_FontAscent(font), strike)
        finally:
            sdlttf.TTF_CloseFont(font)

    def text_size(self, font, text):
        from ..lib.graphics_font import BitmapFont

        if isinstance(font, BitmapFont):
            return super().text_size(font, text)
        from sdl2 import sdlttf

        w, h = ctypes.c_int(), ctypes.c_int()
        if (
            sdlttf.TTF_SizeUTF8(
                font, text.encode("utf-8"), ctypes.byref(w), ctypes.byref(h)
            )
            != 0
        ):
            return None
        return w.value, h.value
