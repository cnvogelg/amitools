class SlotArray:
    """manage an array of fixed size and allow to allocate slots.

    both allocation and deallocation is O(1)
    """

    def __init__(self, size):
        self._array = []
        self._num_free = size
        self._first_free = 0
        # build free list in array
        for i in range(size - 1):
            self._array.append(i + 1)
        self._array.append(None)

    def num_free(self):
        return self._num_free

    def alloc(self, value=None):
        """allocate a new slot and set the value

        return slot id or None if no more slots are free
        """
        # no slot free
        if self._num_free == 0:
            return None
        # get new id
        id = self._first_free
        # update free
        self._num_free -= 1
        if self._num_free == 0:
            self._first_free = None
        else:
            self._first_free = self._array[self._first_free]
        # set value
        self._array[id] = value
        return id

    def free(self, slot_id):
        """free slot"""
        self._array[slot_id] = self._first_free
        self._first_free = slot_id
        self._num_free += 1

    def __len__(self):
        """return length of total array"""
        return len(self._array)

    def __getitem__(self, key):
        """read slot"""
        return self._array[key]

    def __setitem__(self, key, val):
        """write slot"""
        self._array[key] = val
