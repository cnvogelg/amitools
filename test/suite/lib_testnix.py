import os
import pytest


def lib_testnix_test(vamos, buildlibnix):
  lib_file = buildlibnix.make_lib("testnix")
  libs_dir = os.path.basename(os.path.dirname(lib_file))
  vargs = ["-a+libs:bin:" + libs_dir]
  vamos.run_prog_checked("lib_testnix", vargs=vargs)
