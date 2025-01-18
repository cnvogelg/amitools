from enum import IntEnum


class MapTagsFlag(IntEnum):
    MAP_REMOVE_NOT_FOUND = 0
    MAP_KEEP_NOT_FOUND = 1


class FilterTagItemsFlag(IntEnum):
    TAGFILTER_AND = 0
    TAGFILTER_NOT = 1
