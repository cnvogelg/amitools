// The following ifdef block is the standard way of creating macros which make exporting 
// from a DLL simpler. All files within this DLL are compiled with the MUSASHIWIN_EXPORTS
// symbol defined on the command line. This symbol should not be defined on any project
// that uses this DLL. This way any other project whose source files include this file see 
// MUSASHIWIN_API functions as being imported from a DLL, whereas this DLL sees symbols
// defined with this macro as being exported.
#ifdef MUSASHIWIN_EXPORTS
#define MUSASHIWIN_API __declspec(dllexport)
#else
#define MUSASHIWIN_API __declspec(dllimport)
#endif

// This class is exported from the musashiWin.dll
class MUSASHIWIN_API CmusashiWin {
public:
	CmusashiWin(void);
	// TODO: add your methods here.
};

extern MUSASHIWIN_API int nmusashiWin;

MUSASHIWIN_API int fnmusashiWin(void);
