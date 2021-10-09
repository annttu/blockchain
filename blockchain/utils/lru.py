from collections import OrderedDict


class LRUDict(OrderedDict):
    """
    LRU implementation for dictionary
    """

    def __init__(self, *args, max_size: int = 100, **kwargs):
        super().__init__(*args, **kwargs)
        if max_size <= 0:
            raise ValueError("Invalid cache length")
        self.max_size = max_size

    def __setitem__(self, key, value):
        """
        Add new item and move to back of the dict,
        remove least recently used if cache is full
        """
        super().__setitem__(key, value)
        super().move_to_end(key)

        if len(self) >= self.max_size:
            key_to_remove = next(iter(self))
            super().__delitem__(key_to_remove)

    def __getitem__(self, key):
        """
        Move most recently used to back of the dict
        """
        super().move_to_end(key)
        return super().__getitem__(key)
