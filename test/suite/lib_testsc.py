import os
import pytest


def lib_testsc_test(vamos, buildlibsc):
  lib_file = buildlibsc.make_lib("testsc")
  libs_dir = os.path.basename(os.path.dirname(lib_file))
  vargs = ["-a+libs:bin:" + libs_dir]
  vamos.run_prog_checked("lib_testsc", vargs=vargs)
