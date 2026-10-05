"""Finite real-scalar normalization for acceptance records, never arrays/bools."""
import math
import numbers


def finite_scalar(value):
    # NumPy scalars implement Real; restricting exact Python types rejects
    # otherwise valid engine outputs. Bool and complex remain invalid.
    if isinstance(value,bool) or not isinstance(value,numbers.Real):
        return None
    try:
        number=float(value)
    except (ValueError,TypeError,OverflowError):
        return None
    return number if math.isfinite(number) else None
