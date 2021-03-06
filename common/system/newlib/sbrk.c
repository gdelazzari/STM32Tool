/*
  This file implements the _sbrk syscall required by newlib to dinamically
  allocate memory (for example when using malloc)
*/

#include <!CMSIS_FAMILY_INCLUDE!>

#include <errno.h>
#include <sys/unistd.h>

/*
 sbrk
 Increase program data space.
 Malloc and related functions depend on this
 */
caddr_t _sbrk(int incr)
{
  extern char _ebss;
  static char* heap_end;
  char* prev_heap_end;

  if (heap_end == 0) heap_end = &_ebss;
  prev_heap_end = heap_end;

  char* stack = (char *) __get_MSP();
  if (heap_end + incr >  stack)
  {
    errno = ENOMEM;
    return (caddr_t) -1;
  }

  heap_end += incr;
  return (caddr_t) prev_heap_end;
}
