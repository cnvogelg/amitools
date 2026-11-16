"""Small modal SDL text requester shared by file and font selection."""

import ctypes

from .graphics_font import load_topaz_font, render_font_surface


def request_fields(title, fields):
    try:
        import sdl2
    except ImportError:
        return None
    if sdl2.SDL_InitSubSystem(sdl2.SDL_INIT_VIDEO) != 0:
        return None
    try:
        return _request_fields(title, fields)
    finally:
        sdl2.SDL_QuitSubSystem(sdl2.SDL_INIT_VIDEO)


def _request_fields(title, fields):
    import sdl2

    if sdl2.SDL_GetCurrentVideoDriver() == b"dummy":
        return None
    window = sdl2.SDL_CreateWindow(
        title.encode("utf-8"),
        sdl2.SDL_WINDOWPOS_CENTERED,
        sdl2.SDL_WINDOWPOS_CENTERED,
        800,
        240,
        0,
    )
    if not window:
        return None
    renderer = sdl2.SDL_CreateRenderer(window, -1, sdl2.SDL_RENDERER_SOFTWARE)
    if not renderer:
        sdl2.SDL_DestroyWindow(window)
        return None
    values = [value for label, value in fields]
    selected = 0
    saved = []
    window_id = sdl2.SDL_GetWindowID(window)
    sdl2.SDL_StartTextInput()
    try:
        while True:
            sdl2.SDL_SetRenderDrawColor(renderer, 170, 170, 170, 255)
            sdl2.SDL_RenderClear(renderer)
            lines = [
                f"{'>' if i == selected else ' '} {label}: {values[i]}"
                for i, (label, _) in enumerate(fields)
            ]
            lines += ["Tab: next field    Enter: accept    Escape: cancel"]
            for i, line in enumerate(lines):
                surface = render_font_surface(
                    load_topaz_font(), line[-49:], sdl2.SDL_Color(0, 0, 0, 255)
                )
                if surface:
                    texture = sdl2.SDL_CreateTextureFromSurface(renderer, surface)
                    rect = sdl2.SDL_Rect(8, 12 + i * 40, surface.contents.w * 2, 16)
                    sdl2.SDL_RenderCopy(renderer, texture, None, rect)
                    sdl2.SDL_DestroyTexture(texture)
                    sdl2.SDL_FreeSurface(surface)
            sdl2.SDL_RenderPresent(renderer)
            event = sdl2.SDL_Event()
            if not sdl2.SDL_WaitEventTimeout(ctypes.byref(event), 50):
                continue
            if event.type == sdl2.SDL_QUIT:
                saved.append(bytes(event))
                return None
            if event.type in (
                sdl2.SDL_KEYDOWN,
                sdl2.SDL_TEXTINPUT,
                sdl2.SDL_MOUSEBUTTONDOWN,
                sdl2.SDL_WINDOWEVENT,
            ):
                if event.window.windowID != window_id:
                    saved.append(bytes(event))
                    continue
            if (
                event.type == sdl2.SDL_WINDOWEVENT
                and event.window.event == sdl2.SDL_WINDOWEVENT_CLOSE
            ):
                return None
            if event.type == sdl2.SDL_KEYDOWN:
                key = event.key.keysym.sym
                if key == sdl2.SDLK_ESCAPE:
                    return None
                if key in (sdl2.SDLK_RETURN, sdl2.SDLK_KP_ENTER):
                    return values
                if key == sdl2.SDLK_TAB:
                    selected = (selected + 1) % len(fields)
                elif key == sdl2.SDLK_BACKSPACE:
                    values[selected] = values[selected][:-1]
                elif key == sdl2.SDLK_a and event.key.keysym.mod & sdl2.KMOD_CTRL:
                    values[selected] = ""
            elif event.type == sdl2.SDL_TEXTINPUT:
                values[selected] += bytes(event.text.text).decode("utf-8")
            elif event.type == sdl2.SDL_MOUSEBUTTONDOWN:
                selected = min(max((event.button.y - 12) // 40, 0), len(fields) - 1)
            elif event.type >= sdl2.SDL_USEREVENT:
                saved.append(bytes(event))
    finally:
        sdl2.SDL_StopTextInput()
        sdl2.SDL_DestroyRenderer(renderer)
        sdl2.SDL_DestroyWindow(window)
        for raw in saved:
            event = sdl2.SDL_Event.from_buffer_copy(raw)
            sdl2.SDL_PushEvent(ctypes.byref(event))
