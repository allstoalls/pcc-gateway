# `super().__init__(kw=value)` against a keyword-only base parameter.
#
# A super() method reference is a function object at runtime, so the call goes
# through `py_func_call`, which re-packs the emitted positional slots into a
# Python argument tuple. `_resolve_call_kwargs` has already flattened the
# keyword-only argument into a positional slot for the native ABI, so the
# runtime binder was handed a keyword-only formal as a positional and refused
# it: "native function got too many positional arguments".
#
# CPython prints "7" then "42". Fixed in core; kept as the regression shape.
class Base:
    def __init__(self, *, loop=None) -> None:
        self.loop = loop


class Child(Base):
    def __init__(self, coro, *, loop=None) -> None:
        super().__init__(loop=loop)
        self.coro = coro


def main() -> None:
    c = Child(7, loop=42)
    print(c.coro)
    print(c.loop)


main()
