from amitools.vamos.cfg import LibsParser
import argparse


def cfg_libs_dict_test():
  lp = LibsParser()
  input_dict = {
      'libs': {
          "*.library": {
              "mode": "vamos",
              "version": 42,
              "expunge": "last_close",
              "num_fake_calls": 0
          },
          "test.library": {
              "mode": "amiga",
              "version": 0,
              "expunge": "shutdown",
              "num_fake_calls": 0
          }
      },
      'devs': {
          "*.device": {
              "mode": "fake",
              "version": 0,
              "expunge": "no_mem",
              "num_fake_calls": 0
          },
          "test.device": {
              "mode": "off",
              "version": 42,
              "expunge": "no_mem",
              "num_fake_calls": 0
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
          "expunge": "no_mem",
          "num_fake_calls": 1
      },
      "test.library": {
          "mode": "amiga",
          "version": 0,
          "expunge": "shutdown",
          "num_fake_calls": 2
      },
      "*.device": {
          "mode": "fake",
          "version": 0,
          "expunge": "last_close",
          "num_fake_calls": 3
      },
      "test.device": {
          "mode": "off",
          "version": 42,
          "expunge": "shutdown",
          "num_fake_calls": 4
      }
  }
  lp.parse_config(ini_dict, 'ini')
  assert lp.get_cfg_dict() == {
      'libs': {
          "*.library": {
              "mode": "vamos",
              "version": 42,
              "expunge": "no_mem",
              "num_fake_calls": 1
          },
          "test.library": {
              "mode": "amiga",
              "version": 0,
              "expunge": "shutdown",
              "num_fake_calls": 2
          }
      },
      'devs': {
          "*.device": {
              "mode": "fake",
              "version": 0,
              "expunge": "last_close",
              "num_fake_calls": 3
          },
          "test.device": {
              "mode": "off",
              "version": 42,
              "expunge": "shutdown",
              "num_fake_calls": 4
          }
      }
  }


def cfg_libs_args_test():
  lp = LibsParser()
  ap = argparse.ArgumentParser()
  lp.setup_args(ap)
  args = ap.parse_args(
      ['-O', '*.library=mode:vamos,version:42,expunge:last_close,num_fake_calls:1',
       '-O', 'test.library=mode:amiga',
       '-O', '*.device=mode:amiga+test.device=mode:fake,version:42,expunge:no_mem'])
  lp.parse_args(args)
  assert lp.get_cfg_dict() == {
      "libs": {
          "*.library": {
              "mode": "vamos",
              "version": 42,
              "expunge": "last_close",
              "num_fake_calls": 1
          },
          "test.library": {
              "mode": "amiga",
              "version": 0,
              "expunge": "shutdown",
              "num_fake_calls": 0
          }
      },
      "devs": {
          "*.device": {
              "mode": "amiga",
              "version": 0,
              "expunge": "shutdown",
              "num_fake_calls": 0
          },
          "test.device": {
              "mode": "fake",
              "version": 42,
              "expunge": "no_mem",
              "num_fake_calls": 0
          }
      }
  }
