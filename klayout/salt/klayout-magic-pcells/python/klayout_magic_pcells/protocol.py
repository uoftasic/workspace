"""Wire format between the backend and kmp_server.tcl.

A request is one line, ``kmp::req <id> <hex>``, where ``<hex>`` is the hex
encoding of a UTF-8 JSON object. A reply is a block of framed lines::

    KMP_BEGIN <id>
    KMP_KV <id> <key> <hex value>
    KMP_PARAM <id> <hex name> <hex value>
    KMP_END <id>

Every other line Magic prints on stdout is passed through as ``other``.
"""

import json
import re

PROTOCOL = 1
READY_PREFIX = "KMP_READY "

_ID_RE = re.compile(r"^[0-9]+$")


class ProtocolError(Exception):
    """A reply line that doesn't fit the framing."""


def encode_request(req_id, obj):
    """Return the request line (with its newline) for ``obj``."""
    data = json.dumps(obj, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    return "kmp::req %d %s\n" % (req_id, data.encode("utf-8").hex())


def unhex(text):
    return bytes.fromhex(text).decode("utf-8") if text else ""


def tcl_word(text):
    """Quote ``text`` as a single Tcl word by backslash-escaping it."""
    out = []
    for ch in text:
        if ch in ' \t"$[]{}\\;':
            out.append("\\" + ch)
        elif ch == "\n":
            out.append("\\n")
        else:
            out.append(ch)
    return "".join(out)


class Reply:
    """One complete reply: ``kv`` (str -> str) and ``params`` (ordered)."""

    def __init__(self, req_id):
        self.id = req_id
        self.kv = {}
        self.params = {}

    @property
    def rc(self):
        return int(self.kv.get("rc", "1") or "1")

    @property
    def ok(self):
        return self.rc == 0

    @property
    def log(self):
        return self.kv.get("log", "")

    @property
    def error(self):
        return self.kv.get("error", "")

    def __repr__(self):
        return "Reply(id=%d, kv=%r, params=%d)" % (self.id, self.kv, len(self.params))


class ReplyParser:
    """Feed it stdout lines; it returns each reply once its KMP_END arrives.

    ``feed()`` returns ``("reply", Reply)``, ``("ready", protocol)``,
    ``("other", line)`` or ``("partial", None)``.
    """

    def __init__(self):
        self._open = {}

    def feed(self, line):
        line = line.rstrip("\r\n")
        if line.startswith(READY_PREFIX):
            return ("ready", line[len(READY_PREFIX):].strip())
        if not line.startswith("KMP_"):
            return ("other", line)
        parts = line.split(" ")
        tag = parts[0]
        if len(parts) < 2 or not _ID_RE.match(parts[1]):
            raise ProtocolError("bad reply line: %r" % line[:200])
        rid = int(parts[1])
        if tag == "KMP_BEGIN":
            if len(parts) != 2:
                raise ProtocolError("bad KMP_BEGIN: %r" % line[:200])
            self._open[rid] = Reply(rid)
            return ("partial", None)
        rep = self._open.get(rid)
        if rep is None:
            raise ProtocolError("reply line for unopened id %d: %r" % (rid, line[:200]))
        try:
            if tag == "KMP_KV":
                if len(parts) not in (3, 4):
                    raise ProtocolError("bad KMP_KV: %r" % line[:200])
                rep.kv[parts[2]] = unhex(parts[3] if len(parts) == 4 else "")
            elif tag == "KMP_PARAM":
                if len(parts) not in (3, 4):
                    raise ProtocolError("bad KMP_PARAM: %r" % line[:200])
                rep.params[unhex(parts[2])] = unhex(parts[3] if len(parts) == 4 else "")
            elif tag == "KMP_END":
                del self._open[rid]
                return ("reply", rep)
            else:
                raise ProtocolError("unknown tag %r" % tag)
        except ValueError as e:
            raise ProtocolError("bad hex in %r: %s" % (line[:200], e))
        return ("partial", None)

    def discard(self):
        self._open.clear()
