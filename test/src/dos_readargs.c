#include <dos/dos.h>
#include <dos/rdargs.h>
#include <proto/dos.h>

#include <string.h>

#define ARG_MAX  20

#define BEGIN_STR(str) \
  cur_str = str; \
  if(use_csrc) { \
    rdargs_in->RDA_Source.CS_Buffer = str "\n"; \
    rdargs_in->RDA_Source.CS_Length = strlen(str "\n"); \
    rdargs_in->RDA_Source.CS_CurChr = 0; \
  } else { \
    if(rdargs_in) { \
      rdargs_in->RDA_Source.CS_Buffer = NULL; \
    } \
    io = Open("readargs.tmp", MODE_NEWFILE); \
    Write(io, str "\n", strlen(str "\n")); \
    Close(io); \
    io = Open("readargs.tmp", MODE_OLDFILE); \
    oldin = Input(); \
    SelectInput(io); \
  }

#define END_STR() \
  if(!use_csrc) { \
    Close(io); \
    SelectInput(oldin); \
    DeleteFile("readargs.tmp"); \
  }

#define ERROR_MSG \
  Printf("line %ld: csrc=%ld rdargs_in=@%08lx template='%s' input='%s'\n",\
    __LINE__, (LONG)use_csrc, (ULONG)rdargs_in, (ULONG)cur_templ, (ULONG)cur_str); \

#define BEGIN_TEST(template, exp_error) \
  num_tests++; \
  memset(array, 0, sizeof(LONG) * ARG_MAX); \
  cur_templ = template; \
  rdargs = ReadArgs(template, array, rdargs_in); \
  if(!rdargs) { \
    if(exp_error == 0) { \
      ERROR_MSG \
      PrintFault(IoErr(), "ReadArgs() failed!"); \
      num_errors++; \
    } \
  } else { \
    if(exp_error != 0) { \
      ERROR_MSG \
      PrintFault(exp_error, "ReadArgs() did not fail!"); \
      num_errors++; \
    } else {

#define END_TEST() \
    } \
    FreeArgs(rdargs); \
  }

#define CHECK_NULL(pos) \
  if(array[pos] != 0) { \
    ERROR_MSG \
    Printf("#%ld: not NULL! %08lx\n", pos, array[pos]); \
    num_errors++; \
  }

#define CHECK_STRING(pos, val) \
  str = (STRPTR)array[pos]; \
  if(!str) { \
    ERROR_MSG \
    Printf("#%ld: string is NULL!\n", pos); \
    num_errors++; \
  } \
  else if(strcmp(str, val)!=0) { \
    ERROR_MSG \
    Printf("#%ld: string mismatch: %s != %s\n", pos, (ULONG)str, (ULONG)val); \
    num_errors++; \
  }

int num_errors = 0;
int num_tests = 0;

void test(struct RDArgs *rdargs_in, BOOL use_csrc)
{
  struct RDArgs *rdargs;
  int i;
  BPTR io;
  BPTR oldin;
  STRPTR cur_str;
  STRPTR cur_templ;
  STRPTR str;
  LONG array[ARG_MAX];

  BEGIN_STR("hello")

  BEGIN_TEST("AKEY", 0)
  CHECK_STRING(0, "hello")
  END_TEST()

  END_STR()
}

int main(int argc, char **argv)
{
  struct RDArgs *rdargs;
  int result = RETURN_FAIL;

  if ((rdargs = AllocDosObject(DOS_RDARGS, NULL)))
  {
    rdargs->RDA_ExtHelp = "a usage\ntext";

    test(rdargs, TRUE);
    test(rdargs, FALSE);
    test(NULL, FALSE);

    if(num_errors == 0) {
      Printf("All %ld tests passed.\n", num_tests);
      result = 0;
    } else {
      Printf("%ld ERRORS in %ld tests!\n", num_errors, num_tests);
    }

    FreeDosObject(DOS_RDARGS, rdargs);
  }
  else
  {
    PrintFault(ERROR_NO_FREE_STORE, "AllocDosObject()");
  }

  return result;
}
