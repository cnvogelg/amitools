from dataclasses import replace
from types import SimpleNamespace

import pytest

from amitools.vamos.lib.graphics_surface import RasterSurface, RasterState
from amitools.vamos.machine.mock import MockMemory


@pytest.fixture
def raster():
    mem = MockMemory()
    planes = (0x100, 0x200, 0x300)
    state = RasterState(mem, planes, 2, 7, 5, 2, 0, 0xFFFF, 0)
    return RasterSurface(8, 8), state


def planar_pixel(state, x, y):
    return sum(
        ((state.mem.r8(addr + y * state.stride + x // 8) >> (7 - x % 8)) & 1) << i
        for i, addr in enumerate(state.planes)
    )


@pytest.mark.parametrize("mode", [0, 1, 2, 4, 5, 6])
@pytest.mark.parametrize("mask", [0, 1, 3, 7])
@pytest.mark.parametrize("bit", [False, True])
def graphics_indexed_modes_and_plane_masks_test(raster, mode, mask, bit):
    surface, state = raster
    surface.paint(state, 3, 4)
    assert planar_pixel(state, 3, 4) == 5
    operation = replace(state, foreground=3, background=6, mask=mask, mode=mode)
    surface.paint(operation, 3, 4, bit)
    on = bit ^ bool(mode & 4)
    if mode & 3 == 2:
        expected = 5 ^ mask if on else 5
    elif mode & 3 == 0 and not on:
        expected = 5
    else:
        expected = (5 & ~mask) | ((3 if on else 6) & mask)
    assert surface.pixels[4 * 8 + 3] == expected
    assert planar_pixel(state, 3, 4) == expected
    assert planar_pixel(state, 2, 4) == planar_pixel(state, 4, 4) == 0


def graphics_indexed_complement_twice_restores_pixels_test(raster):
    surface, state = raster
    surface.fill(state, 0, 0, 8, 8)
    before = bytes(surface.pixels)
    complement = replace(state, mode=2)
    surface.line(complement, -2, -2, 9, 9)
    surface.line(complement, -2, -2, 9, 9)
    assert bytes(surface.pixels) == before
    assert all(planar_pixel(state, x, y) == 5 for x in range(8) for y in range(8))


def graphics_indexed_fill_clipping_and_pattern_test(raster):
    surface, state = raster
    clip = SimpleNamespace(x=2, y=2, w=2, h=2)
    surface.fill(state, -100, -100, 300, 300, clip)
    assert sum(value == 5 for value in surface.pixels) == 4
    surface.line(replace(state, mode=1, pattern=0xAAAA), 0, 0, 7, 0)
    assert list(surface.pixels[:8]) == [5, 2, 5, 2, 5, 2, 5, 2]


@pytest.mark.parametrize("dx,dy", [(2, 0), (-2, 0), (0, 2), (0, -2), (20, 0), (0, 0)])
def graphics_indexed_scroll_test(raster, dx, dy):
    surface, state = raster
    surface.fill(state, 2, 2, 3, 3)
    before = bytes(surface.pixels)
    surface.scroll(state, 0, 0, 7, 7, dx, dy)
    for y in range(8):
        for x in range(8):
            sx, sy = x + dx, y + dy
            expected = before[sy * 8 + sx] if 0 <= sx < 8 and 0 <= sy < 8 else 2
            assert surface.pixels[y * 8 + x] == planar_pixel(state, x, y) == expected


def graphics_indexed_load_guest_planes_test(raster):
    surface, state = raster
    state.mem.w8(state.planes[0] + 4 * state.stride, 0x10)
    state.mem.w8(state.planes[2] + 4 * state.stride, 0x10)
    surface.load(state)
    assert surface.pixels[4 * 8 + 3] == 5
    assert surface.dirty
    surface.paint(replace(state, mode=2, mask=3), 3, 4)
    assert planar_pixel(state, 3, 4) == surface.pixels[4 * 8 + 3] == 6
