# `map` has no native lowering under --python-libpython=off: the name is not
# resolved at all and the program dies with `NameError: name 'map' is not
# defined` at runtime. CPython prints "7" then "[5, 6]".
def main() -> None:
    a, b = map(int, ["3", "4"])
    print(a + b)
    print(list(map(int, ["5", "6"])))


main()
