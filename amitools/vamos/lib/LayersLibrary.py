from amitools.vamos.lib.graphics import LayerStruct
from amitools.vamos.libcore.impl import LibImpl


class LayersLibrary(LibImpl):
    def setup_lib(self, ctx, base_addr):
        # log_dos.info("setup dos.library")
        self.alloc = ctx.alloc

    def close_lib(self, ctx, open_cnt):
        pass

    def LockLayerInfo(self, ctx, li):
        # Guest calls are serialized by the vamos scheduler.
        pass

    def UnlockLayerInfo(self, ctx, li):
        pass

    def InstallClipRegion(self, ctx, layer, region):
        if not layer:
            return 0
        import sdl2

        value = LayerStruct(ctx.mem, layer)
        previous = value.ClipRegion.val
        graphics = ctx.exec_lib.graphics_lib
        backing = graphics.rp_graphics_map.get(value.rp.val)
        if backing is not None:
            ctx.exec_lib.intuition_lib._flush_batch(backing)
            backing.user_clip_rects = (
                [
                    sdl2.SDL_Rect(a, b, c - a + 1, d - b + 1)
                    for a, b, c, d in graphics._region_rects(ctx, region)
                ]
                if region
                else None
            )
        value.ClipRegion.val = region
        return previous
