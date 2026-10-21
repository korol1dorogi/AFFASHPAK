"""The synthetic world the simulators answer from (S2 generator, default seed and size).

One cached dataset for the registry lookup and for the pipeline's sources, so a company the
registry knows is also known to ЕГРЮЛ, БКИ and «Прозрачный бизнес». S1 replaces this with HTTP.
"""

from functools import cache

from apps.demo_data.build import generate


@cache
def dataset() -> dict:
    return generate()


def simulators() -> dict:
    return dataset()["simulators"]
