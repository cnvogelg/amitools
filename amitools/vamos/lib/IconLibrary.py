from amitools.vamos.AmigaLibrary import AmigaLibrary
from amitools.vamos.structure.ExecStruct import LibraryDef

class IconLibrary(AmigaLibrary):
  name = "icon.library"
  icon_calls = (
    (30, 'iconPrivate1', None),
    (36, 'iconPrivate2', None),
    (42, 'iconPrivate3', None),
    (48, 'iconPrivate4', None),
    (54, 'FreeFreeList', (('freelist', 'a0'),)),
    (60, 'iconPrivate5', None),
    (66, 'iconPrivate6', None),
    (72, 'AddFreeList', (('freelist', 'a0'), ('mem', 'a1'), ('size', 'a2'))),
    (78, 'GetDiskObject', (('name', 'a0'),)),
    (84, 'PutDiskObject', (('name', 'a0'), ('diskobj', 'a1'))),
    (90, 'FreeDiskObject', (('diskobj', 'a0'),)),
    (96, 'FindToolType', (('toolTypeArray', 'a0'), ('typeName', 'a1'))),
    (102, 'MatchToolValue', (('typeString', 'a0'), ('value', 'a1'))),
    (108, 'BumpRevision', (('newname', 'a0'), ('oldname', 'a1'))),
    (114, 'iconPrivate7', None),
    (120, 'GetDefDiskObject', (('type', 'd0'),)),
    (126, 'PutDefDiskObject', (('diskObject', 'a0'),)),
    (132, 'GetDiskObjectNew', (('name', 'a0'),)),
    (138, 'DeleteDiskObject', (('name', 'a0'),))
  )
  
  def __init__(self, version=39):
    AmigaLibrary.__init__(self, self.name, version, self.icon_calls, LibraryDef)
