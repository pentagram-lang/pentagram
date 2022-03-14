import pytest

from inspect import signature


def params(generator):
    def inner(func):
        arg_names = tuple(signature(func).parameters.keys())
        arg_values = generator()
        return pytest.mark.parametrize(
            arg_names, arg_values
        )(func)

    return inner
