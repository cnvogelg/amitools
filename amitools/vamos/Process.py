from Log import log_proc
from lib.lexec.ExecStruct import *
from lib.dos.DosStruct import *

NT_PROCESS = 13

class Process:
  def __init__(self, ctx, bin_file, bin_args, input_fh=None, output_fh=None, stack_size=4096, exit_addr=0):
    self.ctx = ctx
    if input_fh == None:
      input_fh = self.ctx.dos_lib.file_mgr.get_input()
    if output_fh == None:
      output_fh = self.ctx.dos_lib.file_mgr.get_output()
    self.ok = self.load_binary(bin_file)
    if not self.ok:
      return
    self.init_stack(stack_size, exit_addr)
    self.init_args(bin_args)
    self.init_cli_struct(input_fh, output_fh)
    self.init_task_struct(input_fh, output_fh)

  def free(self):
    self.free_task_struct()
    self.free_cli_struct()
    self.free_args()
    self.free_stack()
    self.unload_binary()

  def __str__(self):
    return "[bin='%s']" % self.bin_file

  # ----- stack -----
  # stack size in KiB
  def init_stack(self, stack_size, exit_addr):
    self.exit_addr = exit_addr
    self.stack_size = stack_size
    self.stack = self.ctx.alloc.alloc_memory( self.bin_basename + "_stack", self.stack_size )
    self.stack_base = self.stack.addr
    self.stack_end = self.stack_base + self.stack_size
    log_proc.info("stack: base=%06x end=%06x", self.stack_base, self.stack_end)
    log_proc.info(self.stack)
    # prepare stack
    # TOP: size
    # TOP-4: return from program -> magic_ed
    self.stack_initial = self.stack_end - 4
    self.ctx.mem.access.w32(self.stack_initial, self.stack_size)
    self.stack_initial -= 4
    self.ctx.mem.access.w32(self.stack_initial, self.exit_addr)

  def free_stack(self):
    self.ctx.alloc.free_memory(self.stack)

  # ----- binary -----
  def load_binary(self, ami_bin_file):
    self.bin_basename = self.ctx.path_mgr.ami_name_of_path(ami_bin_file)
    self.bin_file = ami_bin_file
    self.bin_seg_list = self.ctx.seg_loader.load_seg(ami_bin_file)
    if self.bin_seg_list == None:
      log_proc.error("failed loading binary: %s", self.ctx.seg_loader.error)
      return False
    self.prog_start = self.bin_seg_list.prog_start
    log_proc.info("loaded binary: %s", self.bin_seg_list)
    for seg in self.bin_seg_list.segments:
      log_proc.info(seg)
    return True

  def unload_binary(self):
    self.ctx.seg_loader.unload_seg(self.bin_seg_list)

  # ----- args -----
  def init_args(self, bin_args):
    # setup arguments
    self.bin_args = bin_args
    self.arg_text = " ".join(bin_args) + "\n" # AmigaDOS appends a new line to the end
    self.arg_len  = len(self.arg_text)
    self.arg_size = self.arg_len + 1
    self.arg = self.ctx.alloc.alloc_memory(self.bin_basename + "_args", self.arg_size)
    self.arg_base = self.arg.addr
    self.ctx.mem.access.w_cstr(self.arg_base, self.arg_text)
    log_proc.info("args: '%s' (%d)", self.arg_text[:-1], self.arg_size)
    log_proc.info(self.arg)

  def free_args(self):
    self.ctx.alloc.free_memory(self.arg)

  # ----- cli struct -----
  def init_cli_struct(self, input_fh, output_fh):
    self.cli = self.ctx.alloc.alloc_struct(self.bin_basename + "_CLI",CLIDef)
    self.cli.access.w_s("cli_DefaultStack", self.stack_size / 4) # in longs
    self.cmd = self.ctx.alloc.alloc_bstr(self.bin_basename + "_cmd",self.bin_file)
    log_proc.info(self.cmd)
    self.cli.access.w_s("cli_CommandName", self.cmd.addr)
    self.cli.access.w_s("cli_StandardInput", input_fh.b_addr)
    self.cli.access.w_s("cli_CurrentInput", input_fh.b_addr)
    self.cli.access.w_s("cli_StandardOutput", output_fh.b_addr)
    self.cli.access.w_s("cli_CurrentOutput", output_fh.b_addr)
    log_proc.info(self.cli)

  def free_cli_struct(self):
    self.ctx.alloc.free_bstr(self.cmd)
    self.ctx.alloc.free_struct(self.cli)

  def get_cli_struct(self):
    return self.cli.addr

  # ----- task struct -----
  def init_task_struct(self, input_fh, output_fh):
    # Inject arguments into input stream (Needed for C:Execute)
    input_fh.ungets(self.arg_text)
    self.this_task = self.ctx.alloc.alloc_struct(self.bin_basename + "_ThisTask",ProcessDef)
    self.this_task.access.w_s("pr_Task.tc_Node.ln_Type", NT_PROCESS)
    self.this_task.access.w_s("pr_CLI", self.cli.addr)
    self.this_task.access.w_s("pr_CIS", input_fh.b_addr<<2) # compensate BCPL auto-conversion
    self.this_task.access.w_s("pr_COS", output_fh.b_addr<<2) # compensate BCPL auto-conversion
    log_proc.info(self.this_task)

  def free_task_struct(self):
    self.ctx.alloc.free_struct(self.this_task)

  def get_input(self):
    fh_b = self.this_task.access.r_s("pr_CIS") >> 2
    return self.ctx.dos_lib.file_mgr.get_by_b_addr(fh_b)

  def set_input(self, input_fh):
    self.this_task.access.w_s("pr_CIS", input_fh.b_addr<<2) # compensate BCPL auto-conversion

  def get_output(self):
    fh_b = self.this_task.access.r_s("pr_COS") >> 2
    return self.ctx.dos_lib.file_mgr.get_by_b_addr(fh_b)

  def set_output(self, output_fh):
    self.this_task.access.w_s("pr_COS", output_fh.b_addr<<2) # compensate BCPL auto-conversion

