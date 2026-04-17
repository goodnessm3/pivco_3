def listindex(ls, val):

    """use a value of 0-65535 to look up something in a list.
    Regardless of list length, 65535 is divided evenly among its items"""

    index = (len(ls) * val) // 65536
    return ls[index]

def fpmult(a, b):

    """Scale 'a' down by a factor b of 0-65536 (returns a * (b/65536))"""

    c = a * b
    return c >> 16