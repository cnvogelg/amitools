import sys
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from amitools.vamos.lib.GraphicsLibrary import RPBatch, BFText, BFDraw, BFRectFill
from amitools.vamos.lib.IntuitionLibrary import IntuitionLibrary


@pytest.fixture
def renderer(monkeypatch):
    result = SimpleNamespace(calls=[], fail=False)
    result.surface = SimpleNamespace(contents=SimpleNamespace(w=20, h=8))
    result.ttf = SimpleNamespace(
        TTF_RenderUTF8_Solid=Mock(return_value=result.surface),
        TTF_RenderUTF8_Shaded=Mock(return_value=result.surface),
    )
    result.sdl = SimpleNamespace(
        sdlttf=result.ttf,
        SDL_SetRenderTarget=Mock(), SDL_RenderSetClipRect=Mock(),
        SDL_CreateTextureFromSurface=Mock(return_value=12),
        SDL_DestroyTexture=Mock(), SDL_FreeSurface=Mock(),
        SDL_Rect=lambda *args: args, SDL_RenderCopy=Mock(),
    )
    monkeypatch.setitem(sys.modules, 'sdl2', result.sdl)
    result.lib = IntuitionLibrary()
    result.batch = RPBatch()
    result.graphics = SimpleNamespace(batch=result.batch, renderer=3, texture=4, clip_rect=None)
    result.text = BFText(1, 2, 'A', object(), object(), object(), 1)
    result.draw = BFDraw(1, 2, 3, 4, object(), 1)
    result.fill = BFRectFill(1, 2, 3, 4, object(), 1)
    return result


def graphics_batch_preserves_call_order_test(renderer):
    r = renderer
    for command in (r.text, r.fill, r.draw, r.text):
        r.batch.add(command)
    r.lib._execute_texts = lambda renderer, commands: r.calls.extend(commands)
    r.lib._execute_draws = lambda renderer, commands: r.calls.extend(commands)
    r.lib._execute_rectfills = lambda renderer, commands: r.calls.extend(commands)
    r.lib._flush_batch(r.graphics)
    assert r.calls == [r.text, r.fill, r.draw, r.text]
    assert not r.batch.commands
    assert not r.batch.texts and not r.batch.draws and not r.batch.rectfills
    r.lib._flush_batch(r.graphics)
    assert len(r.calls) == 4
    assert r.sdl.SDL_SetRenderTarget.call_args.args == (3, None)
    assert r.sdl.SDL_RenderSetClipRect.call_args.args == (3, None)


@pytest.mark.parametrize('failure', ['surface', 'texture', 'copy', None])
def graphics_text_render_cleanup_test(renderer, failure):
    r = renderer
    if failure == 'surface':
        r.ttf.TTF_RenderUTF8_Shaded.return_value = None
    elif failure == 'texture':
        r.sdl.SDL_CreateTextureFromSurface.return_value = None
    elif failure == 'copy':
        r.sdl.SDL_RenderCopy.side_effect = RuntimeError('copy')
    if failure == 'copy':
        with pytest.raises(RuntimeError, match='copy'):
            r.lib._execute_texts(3, [r.text])
    else:
        r.lib._execute_texts(3, [r.text])
    assert r.sdl.SDL_FreeSurface.call_count == (failure != 'surface')
    assert r.sdl.SDL_DestroyTexture.call_count == (failure not in ('surface', 'texture'))


@pytest.mark.parametrize('mode', [0, 1, 4, 5])
def graphics_text_draw_mode_test(renderer, mode):
    r = renderer
    r.text.draw_mode = mode
    r.lib._execute_texts(3, [r.text])
    function = r.ttf.TTF_RenderUTF8_Shaded if mode & 1 else r.ttf.TTF_RenderUTF8_Solid
    args = function.call_args.args
    assert args[2] is (r.text.bg if mode & 4 else r.text.fg)
    if mode & 1:
        assert args[3] is (r.text.fg if mode & 4 else r.text.bg)


def graphics_batch_restores_target_after_exception_test(renderer):
    r = renderer
    r.batch.add(r.text)
    r.lib._execute_texts = Mock(side_effect=RuntimeError('render'))
    with pytest.raises(RuntimeError, match='render'):
        r.lib._flush_batch(r.graphics)
    assert r.sdl.SDL_SetRenderTarget.call_args.args == (3, None)
    assert r.sdl.SDL_RenderSetClipRect.call_args.args == (3, None)
