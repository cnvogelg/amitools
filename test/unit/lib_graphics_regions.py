from types import SimpleNamespace
import random

import pytest

from amitools.vamos.label import LabelManager
from amitools.vamos.lib.GraphicsLibrary import GraphicsLibrary
from amitools.vamos.lib.graphics import RegionStruct, RegionRectangleStruct, RectangleStruct
from amitools.vamos.machine.mock import MockMemory
from amitools.vamos.mem import MemoryAlloc


@pytest.fixture(params=[False, True], ids=['unlabelled', 'labelled'])
def ctx(request):
    ctx = SimpleNamespace(mem=MockMemory())
    ctx.labels = LabelManager() if request.param else None
    ctx.alloc = MemoryAlloc(ctx.mem, label_mgr=ctx.labels)
    ctx.gfx = GraphicsLibrary()
    ctx.gfx.alloc = ctx.alloc
    ctx.regions = [ctx.gfx._new_region(ctx) for _ in range(2)]
    ctx.rect = RectangleStruct.alloc(ctx.alloc)
    yield ctx
    for addr in ctx.regions:
        ctx.gfx._dispose_region(ctx, addr)
    ctx.rect.free()
    assert ctx.alloc.is_all_free()
    assert not ctx.alloc.mem_objs
    if ctx.labels:
        assert not ctx.labels.get_all_labels()


def pixels(rects):
    return {(x, y) for a, b, c, d in rects for x in range(a, c + 1)
            for y in range(b, d + 1)}


def check(ctx, addr, expected):
    region = RegionStruct(ctx.mem, addr)
    prev = 0
    actual = []
    node_addr = region.RegionRectangle.val
    while node_addr:
        node = RegionRectangleStruct(ctx.mem, node_addr)
        assert node.Prev.val == prev
        a, b, c, d = ctx.gfx._bounds(node.bounds)
        assert a >= 0 and b >= 0
        actual.append((a + region.bounds.MinX.val, b + region.bounds.MinY.val,
                       c + region.bounds.MinX.val, d + region.bounds.MinY.val))
        prev, node_addr = node_addr, node.Next.val
    assert pixels(actual) == expected
    # Nodes must not cover a pixel more than once.
    assert sum((c-a+1)*(d-b+1) for a,b,c,d in actual) == len(expected)
    if expected:
        assert ctx.gfx._bounds(region.bounds) == (
            min(x for x,y in expected), min(y for x,y in expected),
            max(x for x,y in expected), max(y for x,y in expected))
    else:
        assert not region.RegionRectangle.val


@pytest.mark.parametrize('operation', ['or', 'and'])
def graphics_regions_geometry_test(ctx, operation):
    left = [(-12, 10, -4, 15), (-8, 12, 2, 17), (2, 17, 3, 18)]
    right = [(-10, 13, -6, 20), (0, 0, 4, 13)]
    for addr, rects in zip(ctx.regions, (left, right)):
        for rect in rects:
            ctx.gfx._write_bounds(ctx.rect, rect)
            assert ctx.gfx._or_rect_region(ctx, addr, ctx.rect.addr)
        check(ctx, addr, pixels(rects))
    source = ctx.mem.r_block(ctx.regions[0], RegionStruct.get_size())
    method = getattr(ctx.gfx, '_' + operation + '_region_region')
    assert method(ctx, *ctx.regions)
    expected = pixels(left) | pixels(right) if operation == 'or' else pixels(left) & pixels(right)
    check(ctx, ctx.regions[1], expected)
    assert ctx.mem.r_block(ctx.regions[0], RegionStruct.get_size()) == source
    assert method(ctx, ctx.regions[1], ctx.regions[1])
    check(ctx, ctx.regions[1], expected)


def graphics_regions_random_union_test(ctx):
    rng = random.Random(1234)
    expected = set()
    for _ in range(30):
        a, b = rng.randrange(-15, 15), rng.randrange(-15, 15)
        rect = (a, b, a + rng.randrange(8), b + rng.randrange(8))
        ctx.gfx._write_bounds(ctx.rect, rect)
        assert ctx.gfx._or_rect_region(ctx, ctx.regions[0], ctx.rect.addr)
        expected |= pixels([rect])
        check(ctx, ctx.regions[0], expected)


@pytest.mark.parametrize('operation', ['or', 'and'])
def graphics_regions_oom_preserves_destination_test(ctx, monkeypatch, operation):
    assert ctx.gfx._replace_region(ctx, ctx.regions[0], [(11, 11, 30, 30)])
    assert ctx.gfx._replace_region(ctx, ctx.regions[1], [(10, 10, 15, 15), (20, 20, 25, 25)])
    before = ctx.alloc.get_free_bytes(), set(ctx.alloc.mem_objs)
    allocate = ctx.alloc.alloc_memory
    calls = []
    def fail(size, **kwargs):
        if kwargs.get('label') == 'Region rectangle':
            calls.append(size)
            if len(calls) == 2:
                return None
        return allocate(size, **kwargs)
    monkeypatch.setattr(ctx.alloc, 'alloc_memory', fail)
    assert not getattr(ctx.gfx, '_' + operation + '_region_region')(ctx, *ctx.regions)
    assert (ctx.alloc.get_free_bytes(), set(ctx.alloc.mem_objs)) == before
    check(ctx, ctx.regions[1], pixels([(10, 10, 15, 15), (20, 20, 25, 25)]))


def graphics_regions_empty_intersection_test(ctx):
    assert ctx.gfx._replace_region(ctx, ctx.regions[1], [(10, 10, 15, 15)])
    assert ctx.gfx._and_region_region(ctx, *ctx.regions)
    check(ctx, ctx.regions[1], set())
