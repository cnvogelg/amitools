"""RTG-style host display boundary; importing it never imports SDL."""


def create_display(name="sdl", output="vamos-frames"):
    if name == "png":
        from .png import PNGDisplay

        return PNGDisplay(output)
    if name == "sdl":
        from .sdl import SDLDisplay

        return SDLDisplay()
    raise ValueError("unknown display backend: " + name)


def get_display(ctx):
    display = getattr(ctx, "display", None)
    if display is None:
        display = ctx.display = create_display()
    return display
