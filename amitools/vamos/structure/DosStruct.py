from amitools.vamos.AmigaStruct import AmigaStruct

class DosLibraryStruct(AmigaStruct):
  _name = "Dos"
  _format = [
    ("Library","lib")
  ]
DosLibraryDef = DosLibraryStruct()
