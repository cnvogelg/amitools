from amitools.vamos.cfg import LibsParser
import argparse


def cfg_libs_dict_test():
  lp = LibsParser()
  input_dict = {
      'libs': {
          "*.library": {
              "mode": "vamos",
              "version": 42,
              "expunge": "last_close"
          },
          "test.library": {
              "mode": "amiga",
              "version": 0,
              "expunge": "shutdown"
          }
      },
      'devs': {
          "*.device": {
              "mode": "fake",
              "version": 0,
              "expunge": "no_mem"
          },
          "test.device": {
              "mode": "off",
              "version": 42,
              "expunge": "no_mem"
          }
      }
  }
  lp.parse_config(input_dict, 'dict')
  assert lp.get_cfg_dict() == input_dict


def cfg_libs_ini_test():
  lp = LibsParser()
  ini_dict = {
      "*.library": {
          "mode": "vamos",
          "version": 42,
          "expunge": "no_mem"
      },
      "test.library": {
          "mode": "amiga",
          "version": 0,
          "expunge": "shutdown"
      },
      "*.device": {
          "mode": "fake",
          "version": 0,
          "expunge": "last_close"
      },
      "test.device": {
          "mode": "off",
          "version": 42,
          "expunge": "shutdown"
      }
  }
  lp.parse_config(ini_dict, 'ini')
  assert lp.get_cfg_dict() == {
      'libs': {
          "*.library": {
              "mode": "vamos",
              "version": 42,
              "expunge": "no_mem"
          },
          "test.library": {
              "mode": "amiga",
              "version": 0,
              "expunge": "shutdown"
          }
      },
      'devs': {
          "*.device": {
              "mode": "fake",
              "version": 0,
              "expunge": "last_close"
          },
          "test.device": {
              "mode": "off",
              "version": 42,
              "expunge": "shutdown"
          }
      }
  }


def cfg_libs_args_test():
  lp = LibsParser()
  ap = argparse.ArgumentParser()
  lp.setup_args(ap)
  args = ap.parse_args(
      ['-O', '*.library=mode:vamos,version:42,expunge:last_close',
       '-O', 'test.library=mode:amiga',
       '-O', '*.device=mode:amiga+test.device=mode:fake,version:42,expunge:no_mem'])
  lp.parse_args(args)
  assert lp.get_cfg_dict() == {
      "libs": {
          "*.library": {
              "mode": "vamos",
              "version": 42,
              "expunge": "last_close"
          },
          "test.library": {
              "mode": "amiga",
              "version": 0,
              "expunge": "shutdown"
          }
      },
      "devs": {
          "*.device": {
              "mode": "amiga",
              "version": 0,
              "expunge": "shutdown"
          },
          "test.device": {
              "mode": "fake",
              "version": 42,
              "expunge": "no_mem"
          }
      }
  }
