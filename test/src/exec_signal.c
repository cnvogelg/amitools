#include <exec/exec.h>
#include <proto/exec.h>

int check_signal(long signal)
{
    ULONG mask;
    ULONG new_mask;

    /* set and check signal */
    mask = 1 << signal;
    SetSignal(mask, mask);
    new_mask = SetSignal(0,0);
    if((new_mask & mask) == 0) {
        return 50;
    }

    /* clear and check */
    SetSignal(0, mask);
    new_mask = SetSignal(0,0);
    if((new_mask & mask) != 0) {
        return 51;
    }

    return 0;
}

int main(int argc, char *argv[])
{
    int result;

    /* try to allocate signal */
    long signal = AllocSignal(-1);
    if(signal == -1)
        return 40;

    result = check_signal(signal);
    if(result != 0) {
        FreeSignal(signal);
        return result;
    }

    FreeSignal(signal);

    /* now try a fixed signal */
    signal = AllocSignal(24);
    if(signal == -1)
        return 41;

    result = check_signal(signal);
    if(result != 0) {
        FreeSignal(signal);
        return result;
    }

    FreeSignal(signal);

    return signal;
}
