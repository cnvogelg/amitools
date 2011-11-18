from amitools.vamos.AmigaStruct import AmigaStruct

# TagItem
class TagItemStruct(AmigaStruct):
  _name = "TagItem"
  _format = [
    ('ULONG','ti_Tag'),
    ('ULONG','ti_Data')
  ]
TagItemDef = TagItemStruct()

