"""Explicit data-suite membership; selecting a suite never implies skipping it."""


def data_test(suite):
    if suite not in {"controlled", "received"}:
        raise ValueError(f"unknown data suite: {suite}")

    def mark(method):
        method.data_suite = suite
        return method

    return mark
