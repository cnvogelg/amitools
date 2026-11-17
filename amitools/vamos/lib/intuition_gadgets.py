"""Classic application-owned Intuition gadgets (no BOOPSI widget emulation)."""

from dataclasses import replace

from amitools.vamos.machine.regs import REG_A0, REG_A1, REG_D0, REG_D1

from .graphics import RastPortStruct
from .graphics_support import BitmapBlit
from .intuition import WindowStruct


def word(mem, addr):
    value = mem.r16(addr)
    return value - 65536 if value & 32768 else value


def chain(mem, address, count=65535):
    seen = set()
    while address and address not in seen and len(seen) < (count & 65535):
        seen.add(address)
        yield address
        address = mem.r32(address)


class ClassicGadgets:
    def AddGList(self, ctx, window, gadget, position, numGad, requester):
        if requester or not window:
            return 65535
        win = WindowStruct(ctx.mem, window)
        old = list(chain(ctx.mem, win.FirstGadget.val))
        added = list(chain(ctx.mem, gadget, numGad))
        if not added or any(a in old for a in added):
            return 65535
        index = min(position & 65535, len(old))
        joined = old[:index] + added + old[index:]
        win.FirstGadget.val = joined[0]
        for n, addr in enumerate(joined):
            ctx.mem.w32(addr, joined[n + 1] if n + 1 < len(joined) else 0)
        return index

    def RemoveGList(self, ctx, remPtr, gadget, numGad):
        if not remPtr:
            return 65535
        win = WindowStruct(ctx.mem, remPtr)
        old = list(chain(ctx.mem, win.FirstGadget.val))
        if gadget not in old:
            return 65535
        index = old.index(gadget)
        count = min(numGad & 65535, len(old) - index)
        if (
            getattr(self, "_active_gadget", (None, None))[1]
            in old[index : index + count]
        ):
            self._deactivate_gadget(ctx, abort=True)
        left = old[:index] + old[index + count :]
        win.FirstGadget.val = left[0] if left else 0
        for n, addr in enumerate(left):
            ctx.mem.w32(addr, left[n + 1] if n + 1 < len(left) else 0)
        return index

    def AddGadget(self, ctx, window, gadget, position):
        return self.AddGList(ctx, window, gadget, position, 1, 0)

    def RemoveGadget(self, ctx, window, gadget):
        return self.RemoveGList(ctx, window, gadget, 1)

    def _gadget_box(self, ctx, window, gadget):
        mem = ctx.mem
        flags = mem.r16(gadget + 12)
        x, y, w, h = (word(mem, gadget + n) for n in (4, 6, 8, 10))
        win = WindowStruct(mem, window)
        if flags & 8:
            y += win.Height.val - 1
        if flags & 16:
            x += win.Width.val - 1
        if flags & 32:
            w += win.Width.val
        if flags & 64:
            h += win.Height.val
        return x, y, max(0, w), max(0, h)

    def _gadget_fill(self, ctx, rp_addr, x, y, w, h, pen, mode=0):
        from .GraphicsLibrary import BFRectFill

        rp = RastPortStruct(ctx.mem, rp_addr)
        backing = self.graphics_lib.get_rp_graphics(rp_addr)
        state = self.graphics_lib._raster_state(ctx, rp)
        if backing and state is not None:
            state = replace(
                state,
                foreground=pen,
                mode=mode,
                area_pattern=(),
            )
            backing.batch.add(BFRectFill(x, y, w, h, None, mode, state))

    def DrawBorder(self, ctx, rp, border, leftOffset, topOffset):
        from .GraphicsLibrary import BFDraw

        port = RastPortStruct(ctx.mem, rp)
        backing = self.graphics_lib.get_rp_graphics(rp)
        if not backing:
            return
        leftOffset, topOffset = (
            self._signed_word(leftOffset),
            self._signed_word(topOffset),
        )
        seen = set()
        while border and border not in seen:
            seen.add(border)
            x, y = (
                leftOffset + word(ctx.mem, border),
                topOffset + word(ctx.mem, border + 2),
            )
            count, points = ctx.mem.r8(border + 7), ctx.mem.r32(border + 8)
            state = replace(
                self.graphics_lib._raster_state(ctx, port),
                foreground=ctx.mem.r8(border + 4),
                background=ctx.mem.r8(border + 5),
                mode=ctx.mem.r8(border + 6),
                pattern=65535,
            )
            for n in range(1, count):
                xy = [
                    (
                        x + word(ctx.mem, points + k * 4),
                        y + word(ctx.mem, points + k * 4 + 2),
                    )
                    for k in (n - 1, n)
                ]
                backing.batch.add(BFDraw(*xy[0], *xy[1], None, state.mode, state))
            border = ctx.mem.r32(border + 12)

    def DrawImage(self, ctx, rp, image, leftOffset, topOffset):
        backing = self.graphics_lib.get_rp_graphics(rp)
        if not backing:
            return
        mem = ctx.mem
        seen = set()
        while image and image not in seen:
            seen.add(image)
            x, y = (
                self._signed_word(leftOffset) + word(mem, image),
                self._signed_word(topOffset) + word(mem, image + 2),
            )
            w, h, depth = (mem.r16(image + n) for n in (4, 6, 8))
            if depth > 8 or w > 32767 or h > 32767 or w * h > 16 * 1024 * 1024:
                return
            data, pick, on = mem.r32(image + 10), mem.r8(image + 14), mem.r8(image + 15)
            stride = (w + 15) // 16 * 2
            pixels = bytearray(w * h)
            source = 0
            for plane in range(8):
                selected = bool(pick & (1 << plane))
                for py in range(h):
                    for px in range(w):
                        bit = (
                            bool(
                                mem.r8(
                                    data + source * stride * h + py * stride + px // 8
                                )
                                & (128 >> (px & 7))
                            )
                            if selected and source < depth and data
                            else bool(on & (1 << plane))
                        )
                        if bit:
                            pixels[py * w + px] |= 1 << plane
                if selected:
                    source += 1
            state = self.graphics_lib._raster_state(ctx, RastPortStruct(mem, rp))
            backing.batch.add(
                BitmapBlit(x, y, w, h, bytes(pixels), bytes([1]) * (w * h), state)
            )
            image = mem.r32(image + 16)

    def _draw_gadget(self, ctx, window, gadget):
        mem = ctx.mem
        win = WindowStruct(mem, window)
        rp = win.RPort.val
        x, y, w, h = self._gadget_box(ctx, window, gadget)
        flags, kind = mem.r16(gadget + 12), mem.r16(gadget + 16) & 7
        if kind == 5:
            self._custom_render(ctx, window, gadget)
            self.refresh(ctx, rp)
            return
        render = mem.r32(gadget + (22 if flags & 128 and flags & 3 == 2 else 18))
        if render:
            if flags & 4:
                self.DrawImage(ctx, rp, render, x, y)
            else:
                self.DrawBorder(ctx, rp, render, x, y)
        text = mem.r32(gadget + 26)

        if text and not flags & 0x3000:
            for register, value in (
                (REG_A0, rp),
                (REG_A1, text),
                (REG_D0, x),
                (REG_D1, y),
            ):
                ctx.cpu.w_reg(register, value & 0xFFFFFFFF)
            self.PrintIText(ctx)
        if kind == 4:
            info = mem.r32(gadget + 34)
            if info:
                buffer, maximum = mem.r32(info), mem.r16(info + 10)
                if not buffer or not maximum:
                    return
                string = bytes(mem.r_block(buffer, maximum)).split(b"\0", 1)[0]
                if len(string) == maximum:
                    return
                mem.w16(info + 16, len(string))
                self._gadget_fill(ctx, rp, x, y, w, h, 0)
                port = RastPortStruct(mem, rp)
                saved = bytes(mem.r_block(rp, port.get_size()))
                port.cp_x.val, port.cp_y.val = x, y + port.TxBaseline.val
                port.FgPen.val, port.DrawMode.val = 1, 0
                ctx.cpu.w_reg(REG_A0, buffer)
                ctx.cpu.w_reg(REG_A1, rp)
                ctx.cpu.w_reg(REG_D0, min(len(string), w // max(1, port.TxWidth.val)))
                self.graphics_lib.Text(ctx)
                mem.w_block(rp, saved)
        if flags & 128 and flags & 3 == 0:
            self._gadget_fill(ctx, rp, x, y, w, h, 0, 2)
        self.refresh(ctx, rp)

    def RefreshGList(self, ctx, gadgets, window, requester, numGad):
        if requester:
            return
        for gadget in chain(ctx.mem, gadgets, numGad):
            self._draw_gadget(ctx, window, gadget)

    def RefreshGadgets(self, ctx, gadgets, window, requester):
        self.RefreshGList(ctx, gadgets, window, requester, 65535)

    def OnGadget(self, ctx, gadget, window, requester):
        ctx.mem.w16(gadget + 12, ctx.mem.r16(gadget + 12) & ~256)
        self.RefreshGList(ctx, gadget, window, requester, 1)

    def OffGadget(self, ctx, gadget, window, requester):
        if getattr(self, "_active_gadget", (None, None)) == (window, gadget):
            self._deactivate_gadget(ctx, abort=True)
        ctx.mem.w16(gadget + 12, ctx.mem.r16(gadget + 12) | 256)
        self.RefreshGList(ctx, gadget, window, requester, 1)

    def ActivateGadget(self, ctx, gadgets, window, requester):
        if requester or not gadgets or not window or ctx.mem.r16(gadgets + 12) & 256:
            return 0
        self._deactivate_gadget(ctx, abort=True)
        self._active_gadget = (window, gadgets)
        if ctx.mem.r16(gadgets + 16) & 7 == 5:
            self._custom_input(ctx, window, gadgets, 2, None)
        return int(getattr(self, "_active_gadget", (None, None))[1] == gadgets)

    def _gadget_event(self, ctx, event, window):
        mem = ctx.mem
        win = WindowStruct(mem, window)
        if not win.FirstGadget.val:
            return False
        active_window, active = getattr(self, "_active_gadget", (None, None))
        if (
            active_window == window
            and active
            and mem.r16(active + 16) & 7 == 5
            and event.kind in ("button_down", "button_up", "motion", "key")
        ):
            return self._custom_input(ctx, window, active, 3, event)
        if event.kind in ("button_down", "button_up") and event.button == 1:
            x, y = self._guest_mouse(event.x, event.y, event.window_id)
            target = 0
            for gadget in chain(mem, win.FirstGadget.val):
                gx, gy, w, h = self._gadget_box(ctx, window, gadget)
                if (
                    not mem.r16(gadget + 12) & 256
                    and gx <= x < gx + w
                    and gy <= y < gy + h
                ):
                    if mem.r16(gadget + 16) & 7 == 5:
                        result, _ = self._custom_method(ctx, window, gadget, 0, event)
                        if not result & 4:  # GMR_GADGETHIT
                            continue
                    target = gadget
                    break
            if event.kind == "button_down":
                if not target:
                    return False
                self._deactivate_gadget(ctx, abort=True)
                self._active_gadget = (window, target)
                if mem.r16(target + 16) & 7 == 5:
                    return self._custom_input(ctx, window, target, 2, event)
                activation = mem.r16(target + 14)
                if activation & 2:
                    self.queue_idcmp(ctx, window, 0x20, x, y, iaddress=target)
                return True
            active_window, active = getattr(self, "_active_gadget", (None, None))
            if active_window != window or not active:
                return False
            if mem.r16(active + 16) & 7 != 4:
                self._active_gadget = (None, None)
            if active == target:
                activation = mem.r16(active + 14)
                if activation & 256:
                    mem.w16(active + 12, mem.r16(active + 12) ^ 128)
                    self._draw_gadget(ctx, window, active)
                if activation & 1:
                    self.queue_idcmp(ctx, window, 0x40, x, y, iaddress=active)
            return True
        if event.kind == "key":
            active_window, gadget = getattr(self, "_active_gadget", (None, None))
            if active_window != window or not gadget or mem.r16(gadget + 16) & 7 != 4:
                return False
            key = event.text_key
            if not key or not key[0]:
                return False
            info = mem.r32(gadget + 34)
            if not info:
                return False
            buffer, maximum = mem.r32(info), mem.r16(info + 10)
            if not buffer or maximum < 1:
                return False
            text = (
                bytes(mem.r_block(buffer, maximum)).split(b"\0", 1)[0].decode("latin-1")
            )
            if len(text) == maximum:
                return False
            code = key[1]
            if code == 13:
                self._active_gadget = (None, None)
                self.queue_idcmp(ctx, window, 0x40, code=13, iaddress=gadget)
            elif code in (8, 127):
                text = text[:-1]
            elif 32 <= code <= 255 and len(text) < maximum - 1:
                text += chr(code)
            mem.w_cstr(buffer, text)
            mem.w16(info + 8, len(text))
            mem.w16(info + 16, len(text))
            self._draw_gadget(ctx, window, gadget)
            return True
        return False

    def _deactivate_gadget(self, ctx, abort=False):
        window, gadget = getattr(self, "_active_gadget", (None, None))
        self._active_gadget = (None, None)
        if gadget and ctx.mem.r16(gadget + 16) & 7 == 5:
            self._custom_method(ctx, window, gadget, 4, abort=abort)

    def _custom_input(self, ctx, window, gadget, method, event):
        result, code = self._custom_method(ctx, window, gadget, method, event)
        if result & 6:  # GMR_NOREUSE or GMR_REUSE
            self._deactivate_gadget(ctx)
            if result & 8:  # GMR_VERIFY
                x, y = (
                    self._guest_mouse(event.x, event.y, event.window_id)
                    if event
                    else (0, 0)
                )
                self.queue_idcmp(
                    ctx, window, 0x40, x, y, code=code & 65535, iaddress=gadget
                )
        return not result & 4  # GMR_REUSE returns the event to normal handling.

    def _custom_render(self, ctx, window, gadget):
        self._custom_method(ctx, window, gadget, 1)

    def _custom_method(self, ctx, window, gadget, method, event=None, abort=False):
        from .boopsi import call_hook

        mem = ctx.mem
        hook = mem.r32(gadget + 30)
        if not hook:
            return (0 if method == 0 else 2), 0
        win = WindowStruct(mem, window)
        block = ctx.alloc.alloc_memory(
            112, label="Gadget method context", except_on_failure=False
        )
        if block is None:
            return (0 if method == 0 else 2), 0
        draw = 0
        rp = win.RPort.val
        saved_port = bytes(mem.r_block(rp, RastPortStruct.get_size())) if rp else None
        try:
            draw = self.GetScreenDrawInfo(ctx, win.WScreen.val)
            mem.clear_block(block.addr, 112, 0)
            info, message, input_event, termination = (
                block.addr + n for n in (0, 60, 84, 108)
            )
            for offset, value in (
                (0, win.WScreen.val),
                (4, window),
                (12, rp),
                (16, win.WLayer.val),
                (30, draw),
            ):
                mem.w32(info + offset, value)
            mem.w16(info + 24, win.Width.val)
            mem.w16(info + 26, win.Height.val)
            mem.w8(info + 28, 1)
            mem.w32(message, method)
            mem.w32(message + 4, info)
            x, y = (0, 0)
            if event:
                x, y = self._guest_mouse(event.x, event.y, event.window_id)
                gx, gy, _, _ = self._gadget_box(ctx, window, gadget)
                x, y = x - gx, y - gy
            if method == 0:
                mem.w16(message + 8, x & 65535)
                mem.w16(message + 10, y & 65535)
            elif method == 1:
                mem.w32(message + 8, rp)
                mem.w32(message + 12, 1)  # GREDRAW_REDRAW
            elif method in (2, 3):
                mem.w32(message + 8, input_event if event else 0)
                mem.w32(message + 12, termination)
                mem.w16(message + 16, x & 65535)
                mem.w16(message + 18, y & 65535)
                if event:
                    if event.kind == "key" and event.raw_key:
                        _, code, qualifier = event.raw_key
                        mem.w8(input_event + 4, 1)  # IECLASS_RAWKEY
                        mem.w16(input_event + 6, code)
                        mem.w16(input_event + 8, qualifier)
                    else:
                        mem.w8(input_event + 4, 2)  # IECLASS_RAWMOUSE
                        code = {1: 0x68, 2: 0x6A, 3: 0x69}.get(event.button, 0xFF)
                        if event.kind == "button_up":
                            code |= 0x80
                        mem.w16(input_event + 6, code)
                        mem.w16(input_event + 10, x & 65535)
                        mem.w16(input_event + 12, y & 65535)
            elif method == 4:
                mem.w32(message + 8, int(abort))
            result = call_hook(ctx, hook, gadget, message)
            return result, mem.r32(termination)
        finally:
            if saved_port is not None:
                mem.w_block(rp, saved_port)
            if draw:
                self.FreeScreenDrawInfo(ctx, win.WScreen.val, draw)
            ctx.alloc.free_memory(block)

    def ObtainGIRPort(self, ctx, gInfo):
        if not gInfo:
            return 0
        source = ctx.mem.r32(gInfo + 12)
        window = ctx.mem.r32(gInfo + 4)
        if not source or not window:
            return 0
        backing = self.graphics_lib.get_rp_graphics(source)
        if backing is None:
            return 0
        block = ctx.alloc.alloc_memory(
            RastPortStruct.get_size(), label="Gadget RastPort", except_on_failure=False
        )
        if block is None:
            return 0
        ctx.mem.w_block(block.addr, bytes(ctx.mem.r_block(source, block.size)))
        self._gadget_rports[block.addr] = (block, window, self.graphics_lib)
        self.graphics_lib.rp_graphics_map[block.addr] = backing
        self.rp_2_win_addr[block.addr] = window
        return block.addr

    def ReleaseGIRPort(self, ctx, rp):
        owned = self._gadget_rports.pop(rp, None)
        if owned is not None:
            block, window, graphics = owned
            graphics.rp_graphics_map.pop(rp, None)
            self.rp_2_win_addr.pop(rp, None)
            ctx.alloc.free_memory(block)

    def _release_gadget_rports(self, ctx, window=None):
        for rp, (_, owner, _) in tuple(self._gadget_rports.items()):
            if window is None or owner == window:
                self.ReleaseGIRPort(ctx, rp)
