import sys


class FSString:
  """Simple string class that allows to manage strings encoded in Latin-1 used for the Amiga FS.
     It stores the string internally as a python UTF-8 string but allows to convert to Amiga format.
  """
  
  def __init__(self, txt, encoding="Latin-1"):
    """Init the string. Either with a unicode string or with a 8-Bit string.
       If the latter is given then the "encoding" flag determines the encoding.
    """
    if sys.version_info[0] == 3 and type(txt) == str:
      self.txt = txt
    elif type(txt) == unicode:
      self.txt = txt
    elif type(txt) == str:
      self.txt = txt.decode(encoding)
    else:
      raise ValueError("FSString must be str or unicode!")
      
  def __repr__(self):
    return self.__str__()
  
  def __str__(self):
    return self.__unicode__().encode("UTF-8")
    
  def __unicode__(self):
    return self.txt
  
  def get_unicode(self):
    return self.txt
  
  def get_ami_str(self):
    return self.txt.encode("Latin-1")
  