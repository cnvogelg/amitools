from amitools.vamos.AmigaStruct import AmigaStruct

# TagItem
class TagItemStruct(AmigaStruct):
  _name = "TagItem"
  _format = [
    ('ULONG','ti_Tag'),
    ('ULONG','ti_Data')
  ]
TagItemDef = TagItemStruct()

#selco
#ClockData
class ClockDataStruct(AmigaStruct):
  _name = "ClockData"
  _format = [
    ('UWORD', 'sec'),
    ('UWORD', 'min'),
    ('UWORD', 'hour'),
    ('UWORD', 'mday'),
    ('UWORD', 'month'),
    ('UWORD', 'year'),
    ('UWORD', 'wday')
  ]
ClockDataDef = ClockDataStruct()

