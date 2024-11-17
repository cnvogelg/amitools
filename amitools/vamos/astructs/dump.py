from dataclasses import dataclass
from .astruct import AmigaStruct
from .array import ArrayType


@dataclass
class DumpState:
    addr: int = 0
    depth: int = 0
    max_depth: int = 0
    show_offsets: bool = False
    offsets: list[int] = None
    type_size: int = 0
    field_size: int = 0
    indent_size: int = 2
    field_filter: list[any] = None


@dataclass
class SizeState:
    type_size: int = 0
    field_size: int = 0
    depth: int = 0
    max_depth: int = 0
    indent_size: int = 2

    def add_type_size(self, size):
        total = self.indent_size * self.depth + size
        if total > self.type_size:
            self.type_size = total

    def extend_type_size(self, ext):
        self.type_size += ext

    def add_field_size(self, size):
        if size > self.field_size:
            self.field_size = size

    def merge(self, sub_state):
        if sub_state.type_size > self.type_size:
            self.type_size = sub_state.type_size
        if sub_state.field_size > self.field_size:
            self.field_size = sub_state.field_size
        new_depth = sub_state.max_depth + 1
        if new_depth > self.max_depth:
            self.max_depth = new_depth

    def clone(self):
        return SizeState(depth=self.depth + 1, indent_size=self.indent_size)


class TypeDumper:
    def __init__(self, print_func=print):
        self._print_func = print_func

    def dump_obj(self, obj):
        self.dump(type(obj), base_addr=obj.addr, obj=obj)

    def dump_fields(
        self, *field_defs, base_addr=0, obj=None, indent_size=2, show_offsets=False
    ):
        struct = field_defs[0].struct
        self.dump(
            struct,
            base_addr=base_addr,
            obj=obj,
            indent_size=indent_size,
            show_offsets=show_offsets,
            field_filter=field_defs,
        )

    def dump(
        self,
        type_cls,
        base_addr=0,
        obj=None,
        indent_size=2,
        show_offsets=False,
        field_filter=None,
    ):
        size_state = self.calc_sizes(type_cls, indent_size=indent_size)

        dump_state = DumpState(
            addr=base_addr,
            type_size=size_state.type_size,
            field_size=size_state.field_size,
            max_depth=size_state.max_depth,
            indent_size=indent_size,
            show_offsets=show_offsets,
            field_filter=field_filter,
            offsets=[],
        )
        self._dump_any(type_cls, dump_state, obj)

    def calc_sizes(self, type_cls, state=None, indent_size=0):
        # create state if needed
        if not state:
            state = SizeState()
            if indent_size > 0:
                state.indent_size = indent_size
        # return SizeStata
        if issubclass(type_cls, AmigaStruct):
            return self._calc_struct_sizes(type_cls, state)
        elif issubclass(type_cls, ArrayType):
            return self._calc_array_sizes(type_cls, state)
        else:
            # simple type:
            # * field size: 0
            # * type size: len(name)
            type_name = type_cls.get_signature()
            state.add_type_size(len(type_name))
            return state

    def _calc_struct_sizes(self, type_cls, state):
        # type name: "MyStruct {""
        # field name: ".ln_succ"
        type_name = type_cls.get_signature() + " {"
        state.add_type_size(len(type_name))

        sub_state = state.clone()

        # go through fields
        type_size = state.type_size + state.indent_size
        for field_def in type_cls.sdef.get_field_defs():
            # field name = ".lnSucc"
            field_type = field_def.type
            sub_state.add_field_size(len(field_def.name))

            # now recurse
            self.calc_sizes(field_type, sub_state)

        state.merge(sub_state)
        return state

    def _calc_array_sizes(self, type_cls, state):
        type_name = type_cls.get_signature()
        state.add_type_size(len(type_name))

        sub_state = state.clone()

        # recurse
        elem_type = type_cls.get_element_type()
        self.calc_sizes(elem_type, sub_state)

        # extend the type by size of max index '[123]'
        array_size = type_cls.get_array_size()
        max_index = f" [{array_size - 1}]"
        sub_state.extend_type_size(len(max_index))

        state.merge(sub_state)

        return state

    def _dump_any(
        self, type_cls, state, obj=None, index=None, field_name=None, show=True
    ):
        """return byte size"""
        if issubclass(type_cls, AmigaStruct):
            return self._dump_struct(type_cls, state, obj, index, field_name, show)
        elif issubclass(type_cls, ArrayType):
            return self._dump_array(type_cls, state, obj, index, field_name, show)
        else:
            return self._dump_simple(type_cls, state, obj, index, field_name, show)

    def _dump_simple(self, type_cls, state, obj, index, field_name, show):
        type_name = type_cls.get_signature()
        self._print_line(state, show, type_name, index, field_name, obj)

        byte_size = type_cls.get_byte_size()
        if byte_size is None:
            byte_size = 0
        return byte_size

    def _dump_struct(self, type_cls, state, obj, index, field_name, show):
        type_name = type_cls.sdef.get_type_name()
        byte_size = type_cls.get_byte_size()

        # header
        self._print_line(state, show, type_name, index, field_name, type_extra=" {")

        state.depth += 1
        state.offsets.append(0)
        offset = 0

        sub_show = show
        for field_def in type_cls.sdef.get_field_defs():
            field_type = field_def.type
            field_name = field_def.name
            if obj:
                sub_obj = obj.get(field_def.name)
            else:
                sub_obj = None

            # apply a field filter?
            if state.field_filter:
                if field_def in state.field_filter:
                    sub_show = True
                else:
                    sub_show = False

            byte_size = self._dump_any(
                field_type, state, sub_obj, field_name=field_name, show=sub_show
            )

            # update addr
            state.addr += byte_size
            for i in range(state.depth):
                state.offsets[i] += byte_size

        state.depth -= 1

        # footer
        self._print_line(state, show, type_extra="}", offset_prefix="=")

        # pop offsets after footer so it will be shown
        state.offsets.pop()

        return byte_size

    def _dump_array(self, type_cls, state, obj, index, field_name, show):
        type_name = type_cls.get_signature()
        array_size = type_cls.get_array_size()
        element_type = type_cls.get_element_type()
        total_size = type_cls.get_byte_size()

        # header
        self._print_line(state, show, type_name, index, field_name, type_extra=" {")

        total_size = 0
        state.depth += 1
        state.offsets.append(0)
        offset = 0
        for index in range(array_size):
            sub_obj = None
            if obj:
                sub_obj = obj[index]

            byte_size = self._dump_any(
                element_type, state, sub_obj, index=index, show=show
            )

            # update addr
            state.addr += byte_size
            for i in range(state.depth):
                state.offsets[i] += byte_size

        state.depth -= 1

        # footer
        self._print_line(state, show, type_extra="}", offset_prefix="=")

        state.offsets.pop()

        return total_size

    def _print_line(
        self,
        state,
        show,
        type_name=None,
        index=None,
        field_name=None,
        obj=None,
        type_extra=None,
        offset_prefix=None,
    ):
        if not show:
            return
        # format is:
        #  addr      off   reloff
        # @00000000 +0000 +0000   Node * [0]  .ln_succ  obj_value
        # addr
        line = f"@{state.addr:08x}  "
        # optional offsets
        if state.max_depth > 0 and state.show_offsets:
            num_offsets = len(state.offsets)
            num = 0
            for offset in state.offsets:
                if offset is not None:
                    # if last offset then show optional own offset prefix
                    if offset_prefix and num == num_offsets - 1:
                        line += f"{offset_prefix}{offset:04x}  "
                    else:
                        line += f"+{offset:04x}  "
                else:
                    line += " " * 7
                num += 1
            missing = state.max_depth - num_offsets
            for i in range(missing):
                line += " " * 7
        # type name
        if not type_name:
            type_name = ""
        if state.depth > 0:
            indent_size = state.depth * state.indent_size
            line += " " * indent_size
            type_size = state.type_size - indent_size
        else:
            type_size = state.type_size
        # add optional index to type name
        if index is not None:
            type_name += f" [{index}]"
        # an optional extra for the type name
        if type_extra:
            type_name += type_extra
        if field_name or obj:
            line += f"{type_name:{type_size}}"
        else:
            line += type_name
        # optional field name
        if field_name:
            if obj:
                line += f"  {field_name:{state.field_size}}"
            else:
                line += f"  {field_name}"
        # optional obj value
        if obj:
            line += f" c{obj}"

        self._print_func(line)
