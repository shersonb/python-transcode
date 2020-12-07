def formatUID(uid):
    c, d = divmod(uid, 16**4)
    b, c = divmod(c, 16**4)
    a, b = divmod(b, 16**4)
    return f"{a:04x} {b:04x} {c:04x} {d:04x}"
