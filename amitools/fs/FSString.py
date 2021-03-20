import sys
import unicodedata


class FSString:
    """Simple string class that allows to manage strings encoded in Latin-1 used for the Amiga FS.
    It stores the string internally as a python UTF-8 string but allows to convert to Amiga format.
    """

    def __init__(self, txt="", encoding="Latin-1"):
        """Init the string. Either with a string or with bytes.
        If the latter is given then the "encoding" flag determines the encoding.
        """
        if type(txt) is str:
            self.txt = txt
        elif type(txt) is bytes:
            self.txt = txt.decode(encoding)
        else:
            raise ValueError("FSString must be str or bytes!")

    def __repr__(self):
        return "FSString({})".format(self.txt)

    def __str__(self):
        return self.txt

    def __eq__(self, other):
        if isinstance(other, FSString):
            return self.txt == other.txt
        else:
            return False

    def __ne__(self, other):
        if isinstance(other, FSString):
            return self.txt != other.txt
        else:
            return True

    def get_unicode(self):
        return self.txt

    def get_ami_str(self):
        # make sure to normalize utf-8
        nrm = unicodedata.normalize("NFKC", self.txt)
        return nrm.encode("Latin-1")
