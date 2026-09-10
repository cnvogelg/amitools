/* Unix path syntax through libnix on vamos: "." and ".." components are
   rewritten into the AmigaDOS parent step ("a//b"), which vamos must then
   resolve anywhere in a path.  Runs from the test directory (curdir:), so
   src/ and bin/ exist.  Only libnix rewrites paths; the other runtimes
   pass them through and the checks are skipped there.

   usage: dos_unixpath  (exit 0 on success, 1 otherwise)  */
#ifdef __libnix__

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <fcntl.h>
#include <unistd.h>
#include <dirent.h>
#include <sys/stat.h>

#define EXPECT(cond) \
  do { \
    if (!(cond)) { \
      printf("%s:%d: EXPECT(%s) failed\n", __FILE__, __LINE__, #cond); \
      return 1; \
    } \
  } while (0)

static int is_dir(const char *path)
{
  struct stat st;
  return stat(path, &st) == 0 && S_ISDIR(st.st_mode);
}

static int is_file(const char *path)
{
  struct stat st;
  return stat(path, &st) == 0 && !S_ISDIR(st.st_mode);
}

static int can_open(const char *path)
{
  int fd = open(path, O_RDONLY);
  if (fd < 0)
    return 0;
  close(fd);
  return 1;
}

static int dir_has(const char *path, const char *name)
{
  DIR *dir = opendir(path);
  struct dirent *ent;
  int found = 0;
  if (dir == NULL)
    return 0;
  while ((ent = readdir(dir)) != NULL)
    if (strcmp(ent->d_name, name) == 0)
      found = 1;
  closedir(dir);
  return found;
}

static int ends_with(const char *s, const char *tail)
{
  size_t ls = strlen(s), lt = strlen(tail);
  return ls >= lt && strcmp(s + ls - lt, tail) == 0;
}

int main(void)
{
  char path[256];

  EXPECT(access("src/../src/dos_unixpath.c", R_OK) == 0);
  EXPECT(access("src/./dos_unixpath.c", R_OK) == 0);
  EXPECT(is_dir("bin/../src"));
  EXPECT(is_file("src/dos_unixpath.c"));
  EXPECT(is_file("src/../bin/../src/dos_unixpath.c"));
  EXPECT(can_open("bin/../src/dos_unixpath.c"));
  EXPECT(dir_has("src/..", "src"));

  EXPECT(chdir("src/..") == 0);
  EXPECT(access("src/dos_unixpath.c", R_OK) == 0);
  EXPECT(chdir("src/../src/./../src") == 0);
  EXPECT(access("dos_unixpath.c", R_OK) == 0);
  EXPECT(chdir("..") == 0);

  /* a native parent step still works, and a missing target still fails */
  EXPECT(access("src//src/dos_unixpath.c", R_OK) == 0);
  EXPECT(access("src/../nonexistent", R_OK) != 0);

  /* realpath resolves through dos.library and must come back canonical */
  EXPECT(realpath("bin/../src/dos_unixpath.c", path) != NULL);
  EXPECT(strstr(path, "..") == NULL && strstr(path, "//") == NULL);
  EXPECT(ends_with(path, "src/dos_unixpath.c"));

  return 0;
}

#else

int main(void)
{
  return 0;
}

#endif
