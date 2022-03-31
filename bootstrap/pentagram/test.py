from __future__ import annotations

import pytest

from collections.abc import Callable
from collections.abc import Iterable
from inspect import signature
from typing import Any
from typing import TypeVar
from typing import cast

F = TypeVar("F", bound=Callable[..., Any])


def params(
    generator: Callable[[], Iterable[Any]]
) -> Callable[[F], F]:
    def inner(func: F) -> F:
        arg_names = tuple(signature(func).parameters.keys())
        arg_values = generator()
        return cast(
            F,
            pytest.mark.parametrize(arg_names, arg_values)(
                func
            ),
        )

    return inner
