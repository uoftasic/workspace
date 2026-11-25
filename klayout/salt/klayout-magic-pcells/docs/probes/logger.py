import klayout.tl as tl
print("tl.Logger", hasattr(tl, "Logger"), [a for a in dir(tl.Logger) if not a.startswith("_")] if hasattr(tl, "Logger") else None)
