import array

class CustomFIFO:

    """Code from Grok because it wasn't particularly interesting to write"""

    def __init__(self, size: int = 64):

        self._buffer = array.array('H', [0] * size)   # or bytearray(size)
        self._size = size
        self._head = 0      # read index (next to dequeue)
        self._tail = 0      # write index (next to enqueue)
        self._count = 0     # current number of items

    def put(self, value: int) -> bool:
        """Add item. Returns False if full (optional: or overwrite)."""
        if self._count >= self._size:
            return False                    # or self._overwrite(value)
        self._buffer[self._tail] = value
        self._tail = (self._tail + 1) % self._size
        self._count += 1
        return True

    def get(self) -> int | None:
        """Remove and return oldest item, or None if empty."""
        if self._count == 0:
            return None
        value = self._buffer[self._head]
        self._head = (self._head + 1) % self._size
        self._count -= 1
        return value

    def peek(self) -> int | None:
        """Look at oldest item without removing it."""
        return self._buffer[self._head] if self._count > 0 else None

    def full(self) -> bool:
        return self._count >= self._size

    def empty(self) -> bool:
        return self._count == 0

    def qsize(self) -> int:
        return self._count