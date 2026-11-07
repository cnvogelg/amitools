from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from lib_intuition_screen_font import Context


@pytest.mark.parametrize('labels', [False, True])
@pytest.mark.parametrize('failure', [None, 'init', 'attr', 'name', 'font', 'palette'])
def graphics_lifetime_setup_rollback_test(monkeypatch, labels, failure):
    ctx = Context(monkeypatch, labels)
    # The font fixture has a separate owner. Close it before testing the
    # actual graphics.library setup and teardown with a clean allocator.
    ctx.finish()
    graphics = ctx.graphics
    graphics.text_attr = graphics.topaz_font = None
    ctx.path_mgr = SimpleNamespace(to_sys_path=lambda *args: None)
    ttf = ctx.ttf
    ttf.TTF_Init = Mock(return_value=-1 if failure == 'init' else 0)
    ttf.TTF_Quit = Mock()
    import sys
    sdl = sys.modules['sdl2']
    sdl.SDL_Color = lambda *args: args
    if failure == 'palette':
        sdl.SDL_Color = Mock(side_effect=RuntimeError('palette'))
    allocate = ctx.alloc.alloc_memory
    label = {'attr': 'Graphics default TextAttr', 'name': 'Graphics default name',
             'font': 'Graphics TextFont'}.get(failure)
    if label:
        monkeypatch.setattr(ctx.alloc, 'alloc_memory', lambda size, **kwargs:
            None if kwargs.get('label') == label else allocate(size, **kwargs))
    if failure == 'palette':
        with pytest.raises(RuntimeError, match='palette'):
            graphics.open_lib(ctx, 1)
    else:
        graphics.open_lib(ctx, 1)
    if failure is None:
        assert graphics._lib_opened
        assert len(graphics.palette) == 256
        assert all(color[3] == 255 for color in graphics.palette.values())
        graphics.open_lib(ctx, 2)
        graphics.close_lib(ctx, 1)
        assert graphics._lib_opened
        # Public descriptor pointers are borrowed, not ownership records.
        graphics.text_attr.ta_Name.set(0xdeadbeef)
    else:
        assert not graphics._lib_opened
        assert graphics.text_attr is None
    graphics.close_lib(ctx, 0)
    graphics.close_lib(ctx, 0)
    assert ttf.TTF_Init.call_count == 1
    assert ttf.TTF_Quit.call_count == (failure != 'init')
    assert not ctx.handles
    assert not graphics.font_registry
    assert ctx.alloc.is_all_free()
    assert not ctx.alloc.mem_objs
    if ctx.labels:
        assert not ctx.labels.get_all_labels()
