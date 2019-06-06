#include <dos/dos.h>
#include <proto/dos.h>
#include <utility/tagitem.h>
#include <string.h>

int main(int argc, char *argv[])
{
  LONG rc;
  struct TagItem tags[] = {
    {TAG_DONE, 0}
  };

  if(argc != 2) {
    Printf("Usage: %s <cmd_line>\n", (ULONG)argv[0]);
    return 1;
  }

  rc = SystemTagList(argv[1], tags);
  if(rc != 0) {
    Printf("SystemTagList returned: %ld\n", rc);
  }

  return rc;
}
