import vtest

class VPrintfTests(vtest.VamosTestCase):

  programs = ["vprintf"]

  def testFormats(self):
    lines = self.run_prog_checked("vprintf")
    self.assertEqual(lines[0], "int %d %x" % (0xdead, 0xdead), msg="int formatting")
