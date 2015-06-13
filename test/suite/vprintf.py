import vtest

class VPrintfTests(vtest.VamosTestCase):

  programs = ["vprintf"]

  def runTest(self):
    self.run_prog_check_data("vprintf")
