from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from amitools.vamos.display.base import Color, Display
from amitools.vamos.lib.GraphicsLibrary import RPBatch, BFText, BFDraw, BFRectFill
from amitools.vamos.lib.IntuitionLibrary import IntuitionLibrary
from amitools.vamos.lib.graphics_surface import RasterSurface, RasterState


@pytest.fixture
def renderer():
    result = SimpleNamespace(calls=[])
    result.lib = IntuitionLibrary()
    result.lib.display = Display()
    result.lib.graphics_lib = SimpleNamespace(
        palette={i: Color(i, i, i) for i in range(256)}
    )
    result.batch = RPBatch()
    result.graphics = SimpleNamespace(
        batch=result.batch,
        frame=Mock(),
        clip_rect=None,
        clip_rects=None,
        surface=RasterSurface(2, 1),
        present_pending=False,
    )
    result.graphics.surface.load = Mock()
    state = RasterState(None, (), 1, 3, 2, 1, 1, 65535, 0)
    result.text = BFText(0, 0, "A", object(), None, None, 1, state=state)
    result.draw = BFDraw(0, 0, 1, 0, None, 1, state)
    result.fill = BFRectFill(0, 0, 2, 1, None, 1, state)
    return result


def graphics_batch_preserves_call_order_test(renderer):
    r = renderer
    for command in (r.text, r.fill, r.draw, r.text):
        r.batch.add(command)
    r.lib._execute_indexed = lambda graphics, command, clip: r.calls.append(command)
    r.lib._flush_batch(r.graphics)
    assert r.calls == [r.text, r.fill, r.draw, r.text]
    assert not r.batch.commands
    assert not r.batch.texts and not r.batch.draws and not r.batch.rectfills
    r.lib._flush_batch(r.graphics)
    assert len(r.calls) == 4
    r.graphics.frame.upload.assert_called_once()


@pytest.mark.parametrize(
    "mode,expected", [(0, [2, 0]), (1, [2, 1]), (4, [0, 2]), (5, [1, 2])]
)
def graphics_text_draw_mode_test(renderer, mode, expected):
    r = renderer
    r.text.state.mode = mode
    r.lib.display.font_mask = lambda font, text: (2, 1, bytes([1, 0]))
    r.lib._execute_indexed(r.graphics, r.text, None)
    assert list(r.graphics.surface.pixels) == expected


def graphics_failed_upload_does_not_replay_complement_test(renderer):
    r = renderer
    r.batch.add(r.text)
    calls = []

    def paint(graphics, command, clip):
        calls.append(1)
        graphics.surface.pixels[0] ^= 1
        graphics.surface.dirty = True

    r.lib._execute_indexed = paint
    r.graphics.frame.upload.side_effect = [RuntimeError("upload"), None]
    with pytest.raises(RuntimeError, match="upload"):
        r.lib._flush_batch(r.graphics)
    assert not r.batch.commands
    assert r.graphics.surface.dirty
    r.lib._flush_batch(r.graphics)
    assert calls == [1]
    assert r.graphics.surface.pixels[0] == 1
    assert not r.graphics.surface.dirty
    assert r.graphics.present_pending
