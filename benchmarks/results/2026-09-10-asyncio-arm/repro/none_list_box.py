class Thing:
    def go(self, n: int) -> int:
        return n * 2


_BOX = [None]


def put(t) -> None:
    _BOX[0] = t


def get():
    v = _BOX[0]
    if v is None:
        raise RuntimeError("empty")
    return v


class Holder:
    def __init__(self) -> None:
        self._t = None

    def enter(self) -> None:
        self._t = get()

    def use(self, n: int) -> int:
        return self._t.go(n)


def main() -> None:
    put(Thing())
    h = Holder()
    h.enter()
    print(h.use(3))


main()
