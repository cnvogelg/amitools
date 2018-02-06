/* proc_args

   print program arguments
   first by calling GetArgStr()
   and then by reading Input() until newline
*/

#include <dos/dos.h>
#include <proto/dos.h>

static void print_args(STRPTR topic, STRPTR line)
{
  BPTR out = Output();

  PutStr(topic);

  if(line == NULL) {
    PutStr("NULL\n");
  } else {
    PutStr("\"");
    while(TRUE) {
      ULONG ch = *line++;
      if(ch == 0) {
        break;
      }
      else if(ch == '\n') {
        PutStr("\\n");
      }
      else if(ch == '\"') {
        PutStr("\\\"");
      }
      else if(ch < 32) {
        Printf("\\x%02lx", ch);
      }
      else if(ch == '\\') {
        PutStr("\\\\");
      }
      else {
        FPutC(out, ch);
      }
    }
    PutStr("\"\n");
  }
}

int main(int argc, char *argv[])
{
  UBYTE buf[256];
  STRPTR arg_str;
  STRPTR in_str;

  arg_str = GetArgStr();
  print_args("a0:", arg_str);

  in_str = FGets(Input(), buf, 255UL);
  print_args("in:", in_str);

  return 0;
}
