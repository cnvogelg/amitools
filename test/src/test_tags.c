#include <libraries/vamostest.h>
#include <proto/vamostest.h>
#include <proto/exec.h>
#include <utility/tagitem.h>

struct VamosTestBase *VamosTestBase;

int main(int argc, char *argv[])
{
  if ((VamosTestBase = (struct VamosTestBase *)OpenLibrary("vamostest.library", 23)))
  {
    int result = 0;
    struct TagItem tag_list[] = {
        { TAG_USER, 21 },
        { TAG_USER+1, 42 },
        { TAG_USER+2, (ULONG)"hello world!" },
        { TAG_DONE }
    };

    ULONG tag_value = MyFindTagData(TAG_USER+1, tag_list);
    if(tag_value != 42) {
        result = 2;
    }

    tag_value = MyFindTagDataTags(TAG_USER+1, TAG_USER, 21, TAG_USER+1, 42,
        TAG_USER+2, (ULONG)"hello world!", TAG_DONE);
    if(tag_value != 42) {
        result = 3;
    }

    CloseLibrary((struct Library *)VamosTestBase);
    return result;
  } else {
    return 1;
  }
}
