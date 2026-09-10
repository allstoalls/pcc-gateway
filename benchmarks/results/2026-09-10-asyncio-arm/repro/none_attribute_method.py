class Inner:
    def __init__(self) -> None:
        self.hits = 0

    def bump(self, n: int) -> int:
        self.hits = self.hits + n
        return self.hits


class Holder:
    def __init__(self) -> None:
        self._x = None

    def put(self, v) -> None:
        self._x = v

    def poke(self, n: int) -> int:
        if self._x is not None and self._x.bump(n) > 0:
            return 1
        return 0


def main() -> None:
    h = Holder()
    print(h.poke(1))
    h.put(Inner())
    print(h.poke(5))


main()
