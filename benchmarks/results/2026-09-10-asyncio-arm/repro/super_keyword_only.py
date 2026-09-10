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
