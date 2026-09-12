# The rest of the argument shapes the same dynamic super() path has to carry:
# keyword-only defaults left unbound, bound out of order, and the packed
# `*args` / `**kwargs` slots that have to be splatted back out of their
# positional slots. CPython prints, one per line:
#   10 1 2  20 1 7  30 9 8  40 5  50 (51, 52) 6
class Base:
    def __init__(self, a, *, b=1, c=2) -> None:
        self.a = a
        self.b = b
        self.c = c


class Omit(Base):
    def __init__(self) -> None:
        super().__init__(10)


class Some(Base):
    def __init__(self) -> None:
        super().__init__(20, c=7)


class All(Base):
    def __init__(self) -> None:
        super().__init__(30, c=8, b=9)


class VarKw:
    def __init__(self, x, **rest) -> None:
        self.x = x
        self.rest = rest


class VarKwChild(VarKw):
    def __init__(self) -> None:
        super().__init__(40, y=5)


class VarPos:
    def __init__(self, x, *rest, k=3) -> None:
        self.x = x
        self.rest = rest
        self.k = k


class VarPosChild(VarPos):
    def __init__(self) -> None:
        super().__init__(50, 51, 52, k=6)


def show(o) -> None:
    print(o.a)
    print(o.b)
    print(o.c)


def main() -> None:
    show(Omit())
    show(Some())
    show(All())
    v = VarKwChild()
    print(v.x)
    print(v.rest["y"])
    p = VarPosChild()
    print(p.x)
    print(p.rest)
    print(p.k)


main()
