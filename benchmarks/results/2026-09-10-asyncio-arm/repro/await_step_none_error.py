# `py_await_step(iterator, value, error)` decides between send and throw by
# null-checking `error`, so "no exception" has to be a NULL pointer. asyncio's
# `Task._step` passed Python's None, which is a real object pointer, so every
# ordinary coroutine resume took the throw path:
#
#   TypeError: exceptions must derive from BaseException
#
# The `value` argument does not have this problem -- the runtime accepts either
# NULL or the None object there (py_coroutine.py:512), which is exactly the
# convention `error` was missing. Fixed in pcc/py_stdlib/asyncio.py.
#
# This is the smallest program that drives a coroutine through Task._step;
# CPython prints "41" then "1".
import asyncio


async def child():
    await asyncio.sleep(0)
    return 41


async def main_async():
    values = await asyncio.gather(child())
    print(values[0])
    print(len(values))


asyncio.run(main_async())
