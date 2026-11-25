"""The text the PCell must send Magic for a value: the README's contract
("Parameters"), written again here without importing the plugin, so that a
bug in klayout_magic_pcells.manifest.format() fails the sweep's request and
geometry checks instead of reaching both paths.

  float  -> the value as KLayout keeps it in a saved file (its 15
            significant digits, rounded half-even on the exact binary value,
            as C's %.15g does), taken as the nearest double and rounded to 12
            significant digits the same way, in Python's float notation:
            shortest digits, at least one digit after the point, exponent
            form ("1e-05", "1e+16") below 1e-4 and from 1e16 on; a zero is
            "0.0", negative or not (KLayout saves -0.0 as 0); "inf", "-inf"
            and "nan" as Python writes them;
            if the text equals the one the manifest default gives, the
            default's own text ("0.420")
  int    -> decimal digits
  bool01 -> "1" or "0"
  signed -> the text as typed

The arithmetic is done with Decimal on the exact binary values, not with
printf, so it is a second implementation of the same rule.
"""

import math
import sys
from decimal import Context, Decimal, ROUND_HALF_EVEN

_C12 = Context(prec=12, rounding=ROUND_HALF_EVEN)
_C15 = Context(prec=15, rounding=ROUND_HALF_EVEN)


def _python_notation(d):
    """A nonzero finite Decimal with at most 17 digits -> Python's repr text
    of the double with exactly those digits."""
    sign, digits, _exp = d.normalize().as_tuple()
    s = "".join(str(x) for x in digits)
    e = d.adjusted()  # exponent of the first digit
    neg = "-" if sign else ""
    if -4 <= e < 16:
        if e < 0:
            body = "0." + "0" * (-e - 1) + s
        elif len(s) > e + 1:
            body = s[:e + 1] + "." + s[e + 1:]
        else:
            body = s + "0" * (e + 1 - len(s)) + ".0"
        return neg + body
    mant = s[0] + ("." + s[1:] if len(s) > 1 else "")
    return "%s%se%s%02d" % (neg, mant, "-" if e < 0 else "+", abs(e))


def _text12(x):
    x = float(x)
    if math.isnan(x):
        return "nan"
    if math.isinf(x):
        return "inf" if x > 0 else "-inf"
    if x == 0:
        return "0.0"
    d15 = _C15.plus(Decimal(x))
    d12 = _C12.plus(Decimal(float(d15)))
    if abs(d12) < Decimal(sys.float_info.min):
        # Subnormal: fewer digits than 12 already name the double, and
        # Python writes the fewest ("5e-324").
        return repr(float(d12))
    return _python_notation(d12)


def float_text(x, default=None):
    t = _text12(x)
    if default is not None:
        try:
            if t == _text12(float(default)):
                return default
        except ValueError:
            pass
    return t


def typed(ptype, text):
    """The text a user types -> the value given to Layout.create_cell."""
    if ptype == "float":
        return float(text)
    if ptype == "int":
        return int(text)
    if ptype == "bool01":
        return bool(int(text))
    return str(text)


def text(ptype, value, default=None):
    if ptype == "float":
        return float_text(value, default)
    if ptype == "int":
        return "%d" % value
    if ptype == "bool01":
        return "1" if value else "0"
    return str(value)
