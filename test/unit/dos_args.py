from __future__ import print_function

from amitools.vamos.lib.dos.Args import *

def template_arg_test():
  # string
  ta = TemplateArg.parse_string("a=b/k")
  assert(ta.ktype == TemplateArg.TYPE_STRING)
  assert(not ta.is_required)
  assert(ta.is_keyword)
  assert(not ta.is_multi)
  assert(not ta.is_full)
  assert(ta.keys == ['A', 'B'])
  # number
  ta = TemplateArg.parse_string("my=fancy/n")
  assert(ta.ktype == TemplateArg.TYPE_NUMBER)
  assert(not ta.is_required)
  assert(not ta.is_keyword)
  assert(not ta.is_multi)
  assert(not ta.is_full)
  assert(ta.keys == ['MY', 'FANCY'])
  # switch
  ta = TemplateArg.parse_string("my=fancy/s")
  assert(ta.ktype == TemplateArg.TYPE_SWITCH)
  assert(not ta.is_required)
  assert(ta.is_keyword)
  assert(not ta.is_multi)
  assert(not ta.is_full)
  # toggle
  ta = TemplateArg.parse_string("my=fancy/t")
  assert(ta.ktype == TemplateArg.TYPE_TOGGLE)
  assert(not ta.is_required)
  assert(ta.is_keyword)
  assert(not ta.is_multi)
  assert(not ta.is_full)
  # multi
  ta = TemplateArg.parse_string("my=fancy/m")
  assert(ta.ktype == TemplateArg.TYPE_STRING)
  assert(not ta.is_required)
  assert(not ta.is_keyword)
  assert(ta.is_multi)
  assert(not ta.is_full)
  # full
  ta = TemplateArg.parse_string("my=fancy/f")
  assert(ta.ktype == TemplateArg.TYPE_STRING)
  assert(not ta.is_required)
  assert(not ta.is_keyword)
  assert(not ta.is_multi)
  assert(ta.is_full)

def template_arg_list_test():
  tal = TemplateArgList.parse_string("a=b/k,all/m")
  assert(tal.len() == 2)
  assert(tal.get_arg(0).pos == 0)
  assert(tal.get_arg(1).pos == 1)
  assert(tal.get_arg(2) is None)
  assert(tal.get_arg(-1) is None)
  assert(tal.find_arg("a").pos == 0)
  assert(tal.find_arg("ALL").pos == 1)
  assert(tal.find_arg("blob") is None)
