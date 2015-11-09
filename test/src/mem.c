#include <proto/exec.h>
#include <exec/memory.h>

static int test_CopyMem(unsigned long size)
{
  unsigned char *ptr;
  int i,j;

  ptr = (unsigned char *)AllocMem(size * 2, MEMF_CLEAR);
  if(ptr == NULL) {
    return 1;
  }

  /* fill memory */
  for(i=0;i<size;i++) {
    ptr[i] = (unsigned char)(i & 0xff);
  }

  CopyMem(ptr, ptr+size, size);

  /* check memory */
  j = size;
  for(i=0;i<size;i++) {
    if(ptr[j] != (unsigned char)(i & 0xff)) {
      return 2;
    }
    j++;
  }

  FreeMem(ptr, size * 2);
  return 0;
}

static int test_CopyMemQuick(unsigned long size)
{
  unsigned char *ptr;
  int i,j;

  ptr = (unsigned char *)AllocMem(size * 2, MEMF_CLEAR);
  if(ptr == NULL) {
    return 1;
  }

  /* fill memory */
  for(i=0;i<size;i++) {
    ptr[i] = (unsigned char)(i & 0xff);
  }

  CopyMemQuick(ptr, ptr+size, size);

  /* check memory */
  j = size;
  for(i=0;i<size;i++) {
    if(ptr[j] != (unsigned char)(i & 0xff)) {
      return 2;
    }
    j++;
  }

  FreeMem(ptr, size * 2);
  return 0;
}

int main(int argc, char *argv[])
{
  int result;

  result = test_CopyMem(1024);
  if(result != 0) {
    return result;
  }

  result = test_CopyMemQuick(1024);
  if(result != 0) {
    return result;
  }

  return 0;
}
