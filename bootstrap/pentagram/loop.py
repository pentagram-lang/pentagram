from typing import Any
from typing import Callable


def loop(func: Callable[[str], Any]) -> None:
    try:
        while True:
            try:
                text = input("> ")
                while text.endswith(" "):
                    text += f"\n{input('- ')}"
            except KeyboardInterrupt:
                print()
                continue
            print(func(text))
    except EOFError:
        print()
