#include <dos/dos.h>
#include <proto/dos.h>
#include <stdlib.h>

int main(int argc, char *argv[])
{
  BPTR seglist;
  LONG rc;
  ULONG arg_size;
  char *arg_ptr;

  if(argc != 3) {
    Printf("Usage: %s <cmd> <args>\n", (ULONG)argv[0]);
    return 1;
  }

  seglist = LoadSeg(argv[1]);
  if(seglist == 0) {
    Printf("No seglist found: %s\n", (ULONG)argv[1]);
    return 2;
  }

  /* append newline to arg */
  arg_size = strlen(argv[1]);
  arg_ptr = (char *)malloc(arg_size + 2);
  strcpy(arg_ptr, argv[1]);
  arg_ptr[arg_size] = '\n';
  arg_ptr[arg_size+1] = '\0';
  Printf("arg: '%s'\n", (ULONG)arg_ptr);

  rc = RunCommand(seglist, 4096, arg_ptr, arg_size + 1);
  if(rc != 0) {
    Printf("RunCommand failed: %ld", rc);
  }

  free(arg_ptr);

  UnLoadSeg(seglist);
  return rc;
}
