from amitools.vamos.cfg import LibsParser
import argparse


def cfg_libs_dict_test():
  lp = LibsParser()
  input_dict = {
      'libs': {
          "*.library": {
              "mode": "blubber",
              "version": 42,
              "expunge": "foo"
          },
          "test.library": {
              "mode": "amiga",
              "version": 0,
              "expunge": "shutdown"
          }
      },
      'devs': {
          "*.device": {
              "mode": "bla",
              "version": 0,
              "expunge": "bar"
          },
          "test.device": {
              "mode": "blubber",
              "version": 42,
              "expunge": "baz"
          }
      }
  }
  lp.parse_config(input_dict, 'dict')
  assert lp.get_cfg_dict() == input_dict


def cfg_libs_ini_test():
  lp = LibsParser()
  ini_dict = {
      "*.library": {
          "mode": "blubber",
          "version": 42,
          "expunge": "foo"
      },
      "test.library": {
          "mode": "amiga",
          "version": 0,
          "expunge": "shutdown"
      },
      "*.device": {
          "mode": "bla",
          "version": 0,
          "expunge": "bar"
      },
      "test.device": {
          "mode": "blubber",
          "version": 42,
          "expunge": "baz"
      }
  }
  lp.parse_config(ini_dict, 'ini')
  assert lp.get_cfg_dict() == {
      'libs': {
          "*.library": {
              "mode": "blubber",
              "version": 42,
              "expunge": "foo"
          },
          "test.library": {
              "mode": "amiga",
              "version": 0,
              "expunge": "shutdown"
          }
      },
      'devs': {
          "*.device": {
              "mode": "bla",
              "version": 0,
              "expunge": "bar"
          },
          "test.device": {
              "mode": "blubber",
              "version": 42,
              "expunge": "baz"
          }
      }
  }


def cfg_libs_args_test():
  lp = LibsParser()
  ap = argparse.ArgumentParser()
  lp.setup_args(ap)
  args = ap.parse_args(
      ['-O', '*.library=mode:vamos,version:42,expunge:never',
       '-O', 'test.library=mode:amiga',
       '-O', '*.device=mode:bla+test.device=mode:foo,version:42,expunge:baz'])
  lp.parse_args(args)
  assert lp.get_cfg_dict() == {
      "libs": {
          "*.library": {
              "mode": "vamos",
              "version": 42,
              "expunge": "never"
          },
          "test.library": {
              "mode": "amiga",
              "version": 0,
              "expunge": "shutdown"
          }
      },
      "devs": {
          "*.device": {
              "mode": "bla",
              "version": 0,
              "expunge": "shutdown"
          },
          "test.device": {
              "mode": "foo",
              "version": 42,
              "expunge": "baz"
          }
      }
  }
