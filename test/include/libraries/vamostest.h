#ifndef LIBRARIES_VAMOSTEST_H
#define LIBRARIES_VAMOSTEST_H

#ifndef EXEC_LIBRARIES_H
#include <exec/libraries.h>
#endif

#define VAMOSTESTNAME "vamostest.library"

struct VamosTestBase
{
  struct Library vtb_LibNode;
};

#endif  /* LIBRARIES_VAMOSTEST_H */
