from .astructdef import AmigaStructDef
from .astruct import AmigaStruct

# TagItem
@AmigaStructDef
class TagItemStruct(AmigaStruct):
  _format = [
    ('ULONG','ti_Tag'),
    ('ULONG','ti_Data')
  ]

# ClockData
@AmigaStructDef
class ClockDataStruct(AmigaStruct):
  _format = [
    ('UWORD', 'sec'),
    ('UWORD', 'min'),
    ('UWORD', 'hour'),
    ('UWORD', 'mday'),
    ('UWORD', 'month'),
    ('UWORD', 'year'),
    ('UWORD', 'wday')
  ]
