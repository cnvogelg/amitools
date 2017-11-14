/*
 * AF, selco, 05.Nov.2017
 * test mathieeedoubxxx functions for vamos
 * ~/opt/m68k-amigaos/bin/m68k-amigaos-gcc -I. -Wall -pedantic  mathieeedoubxxx_test.c -o mathieeedoubxxx_test -noixemul
 *
 * you will see %f from printf instead of values. Thats OK... If all is fine up to this point, add -lm to the compiler call to see hopefully perfect printf output
 * (this adds a lot more math stuff that can fail)
 *
 * ~/opt/m68k-amigaos/bin/m68k-amigaos-gcc -I. -Wall -pedantic  mathieeedoubxxx_test.c -o mathieeedoubxxx_test -noixemul -lm
*/


#include <stdio.h>
#include <string.h>

#include <limits.h>

#include <exec/types.h>
#include <clib/exec_protos.h>

#include <libraries/mathieeedp.h>
#include <clib/mathieeedoubbas_protos.h>
#include <clib/mathieeedoubtrans_protos.h>
#include <clib/utility_protos.h>


struct Library *MathIeeeDoubBasBase;
struct Library *MathIeeeDoubTransBase;
struct Library *UtilityBase;


int fequal(double a, double b)
{
	// It's difficult to compare floating point for equality, especially is they com from different platforms and languages
	// the simple wa is a string compare...

	static char val1str[1024];    // big enough to hold even long numbers, don't use the stack
	static char val2str[1024];

	snprintf(val1str,1024,"%f",a);
	snprintf(val2str,1024,"%f",b);

	return 0==strncmp(val1str,val2str,1024);
}


int printDouble(char *Function,double value,unsigned char *ExpectedResult)
{
    static unsigned char ResultArray[8];

    double *ValuePtr=&value;
    unsigned int i;
    int Error=0;
    char *WarningColorString;

    if(fequal(value,*(double*)ExpectedResult))   // are both Amiga and vamon double-Result very very nearly the same?
    {

        WarningColorString="\033[43m";     // YES, no Error. print it YELLOW
    }
    else
    {

        WarningColorString="\033[31m";     // No, print differences RED
        Error=1; 
    }   



    printf("%s",Function);
    printf("\nhere                    ");
    for(i=0;i<8;i++)
    {
        ResultArray[i]=((unsigned char*)ValuePtr)[i];	
	printf("%02x ",ResultArray[i]);
    }

    printf(" --> %.16g\n",value);


    printf("\nreference real Amiga    ");

    for(i=0;i<8;i++)
    {
            if(ResultArray[i]==ExpectedResult[i])
            {
                printf("%02x ",ExpectedResult[i]);
            }
	    else
            {
                printf("%s%02x\033[0m ",WarningColorString,ExpectedResult[i]);
            }
    }

    printf(" --> %.16g",*(double*)ExpectedResult);


    printf("\n\n");

    return Error;

}

int printLong(char *Function,long value,unsigned char *ExpectedResult)
{
    static unsigned char ResultArray[4];

    long *ValuePtr=&value;
    unsigned int i;
    int Error=0;

    printf("%s",Function);
    printf("\nhere                    ");
    for(i=0;i<4;i++)
    {
        ResultArray[i]=((unsigned char*)ValuePtr)[i];
        printf("%02x ",ResultArray[i]);
    }

    printf("\nreference real Amiga    ");

    for(i=0;i<4;i++)
    {
            if(ResultArray[i]==ExpectedResult[i])
            {
                printf("%02x ",ExpectedResult[i]);
            }
            else if ((i==3) && ((ResultArray[i]==ExpectedResult[i]+1) || (ResultArray[i]==ExpectedResult[i]-1))) // allow +-1 in lowest byte
            {
                printf("\033[43m%02x\033[0m ",ExpectedResult[i]);
            }
            else
            {
                printf("\033[31m%02x\033[0m ",ExpectedResult[i]);
                Error=1;
            }
    }

    printf("\n\n");

    return Error;
}


int double_is_long_test(double (*Function)(long),char *FunctionName, int value1,unsigned char ExpectedResult_0,
		                                                                       unsigned char ExpectedResult_1,
												 							   unsigned char ExpectedResult_2,
												 							   unsigned char ExpectedResult_3,
												 							   unsigned char ExpectedResult_4,
												 							   unsigned char ExpectedResult_5,
												 							   unsigned char ExpectedResult_6,
												 							   unsigned char ExpectedResult_7)
{
    double Result;
    unsigned char ExpectedResult[8];
    static char FunctionLine[1024];

    ExpectedResult[0]=ExpectedResult_0;
    ExpectedResult[1]=ExpectedResult_1;
    ExpectedResult[2]=ExpectedResult_2;
    ExpectedResult[3]=ExpectedResult_3;
    ExpectedResult[4]=ExpectedResult_4;
    ExpectedResult[5]=ExpectedResult_5;
    ExpectedResult[6]=ExpectedResult_6;
    ExpectedResult[7]=ExpectedResult_7;

    Result=Function(value1);

    snprintf(FunctionLine,1024,"%s(%.16g) = ",FunctionName,value1);
    return  printDouble(FunctionLine,Result,ExpectedResult);
}


int double_is_double_double_test(double (*Function)(double,double),char *FunctionName, double value1, double value2,unsigned char ExpectedResult_0,
		                                                                                                            unsigned char ExpectedResult_1,
																													unsigned char ExpectedResult_2,
																													unsigned char ExpectedResult_3,
																													unsigned char ExpectedResult_4,
																													unsigned char ExpectedResult_5,
																													unsigned char ExpectedResult_6,
																													unsigned char ExpectedResult_7)
{
    double Result;
    unsigned char ExpectedResult[8];
    static char FunctionLine[1024];

    ExpectedResult[0]=ExpectedResult_0;
    ExpectedResult[1]=ExpectedResult_1;
    ExpectedResult[2]=ExpectedResult_2;
    ExpectedResult[3]=ExpectedResult_3;
    ExpectedResult[4]=ExpectedResult_4;
    ExpectedResult[5]=ExpectedResult_5;
    ExpectedResult[6]=ExpectedResult_6;
    ExpectedResult[7]=ExpectedResult_7;

    Result=Function(value1,value2);

    snprintf(FunctionLine,1024,"%s(%.16g , %.16g) = ",FunctionName,value1,value2);
    return  printDouble(FunctionLine,Result,ExpectedResult);
}



int long_is_double_double_test(long (*Function)(double,double),char *FunctionName, double value1, double value2,unsigned char ExpectedResult_0,
		                                                                                                        unsigned char ExpectedResult_1,
				  																							    unsigned char ExpectedResult_2,
																											    unsigned char ExpectedResult_3)
{
    long Result;
    unsigned char ExpectedResult[4];
    static char FunctionLine[1024];

    ExpectedResult[0]=ExpectedResult_0;
    ExpectedResult[1]=ExpectedResult_1;
    ExpectedResult[2]=ExpectedResult_2;
    ExpectedResult[3]=ExpectedResult_3;

    Result=Function(value1,value2);

    snprintf(FunctionLine,1024,"%s(%.16g , %.16g) = ",FunctionName,value1,value2);
    return  printLong(FunctionLine,Result,ExpectedResult);
}

int long_is_long_long_test(long (*Function)(long,long),char *FunctionName, long value1, long value2,unsigned char ExpectedResult_0,
		                                                                                            unsigned char ExpectedResult_1,
				  																					unsigned char ExpectedResult_2,
																									unsigned char ExpectedResult_3)
{
    long Result;
    unsigned char ExpectedResult[4];
    static char FunctionLine[1024];

    ExpectedResult[0]=ExpectedResult_0;
    ExpectedResult[1]=ExpectedResult_1;
    ExpectedResult[2]=ExpectedResult_2;
    ExpectedResult[3]=ExpectedResult_3;

    Result=Function(value1,value2);

    snprintf(FunctionLine,1024,"%s(%d , %d) = ",FunctionName,value1,value2);
    return  printLong(FunctionLine,Result,ExpectedResult);
}



int long_is_double_test(long (*Function)(double),char *FunctionName, double value1, unsigned char ExpectedResult_0,
		                                                                            unsigned char ExpectedResult_1,
				  								      							    unsigned char ExpectedResult_2,
																					unsigned char ExpectedResult_3)
{
    long Result;
    unsigned char ExpectedResult[4];
    static char FunctionLine[1024];

    ExpectedResult[0]=ExpectedResult_0;
    ExpectedResult[1]=ExpectedResult_1;
    ExpectedResult[2]=ExpectedResult_2;
    ExpectedResult[3]=ExpectedResult_3;

    Result=Function(value1);

    snprintf(FunctionLine,1024,"%s(%.16g ) = ",FunctionName,value1);
    return  printLong(FunctionLine,Result,ExpectedResult);
}

int double_is_double_test(double (*Function)(double),char *FunctionName, double value1, unsigned char ExpectedResult_0,
		                                                                                unsigned char ExpectedResult_1,
																						unsigned char ExpectedResult_2,
																						unsigned char ExpectedResult_3,
																						unsigned char ExpectedResult_4,
																						unsigned char ExpectedResult_5,
																						unsigned char ExpectedResult_6,
																						unsigned char ExpectedResult_7)
{
    double Result;
    unsigned char ExpectedResult[8];
    static char FunctionLine[1024];

    ExpectedResult[0]=ExpectedResult_0;
    ExpectedResult[1]=ExpectedResult_1;
    ExpectedResult[2]=ExpectedResult_2;
    ExpectedResult[3]=ExpectedResult_3;
    ExpectedResult[4]=ExpectedResult_4;
    ExpectedResult[5]=ExpectedResult_5;
    ExpectedResult[6]=ExpectedResult_6;
    ExpectedResult[7]=ExpectedResult_7;

    Result=Function(value1);

    snprintf(FunctionLine,1024,"%s(%.16g) = ",FunctionName,value1);
    return  printDouble(FunctionLine,Result,ExpectedResult);
}


int test_MathIeeeDoubBas(void)
{
	int Error=0;
	MathIeeeDoubBasBase=OpenLibrary((unsigned char*)"mathieeedoubbas.library",34);
	if(MathIeeeDoubBasBase)
	{
		printf("mathieeedoubbas.library %d.%d\n\n",MathIeeeDoubBasBase->lib_Version,MathIeeeDoubBasBase->lib_Revision);
        // expeced results are from mathieeedoubbas.library 38.1 (OS3.1)


		Error+=double_is_double_test(IEEEDPAbs,"IEEEDPAbs",      -1,    0x3f, 0xf0, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00);
		Error+=double_is_double_test(IEEEDPAbs,"IEEEDPAbs",       1,    0x3f, 0xf0, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00);
		Error+=double_is_double_test(IEEEDPAbs,"IEEEDPAbs",       0,    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00);
		Error+=double_is_double_test(IEEEDPAbs,"IEEEDPAbs", FLT_MIN,    0x38, 0x10, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00);
		Error+=double_is_double_test(IEEEDPAbs,"IEEEDPAbs", FLT_MAX,    0x47, 0xef, 0xff, 0xff, 0xe0, 0x00, 0x00, 0x00);
		Error+=double_is_double_test(IEEEDPAbs,"IEEEDPAbs", DBL_MIN,    0x00, 0x10, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00);
		Error+=double_is_double_test(IEEEDPAbs,"IEEEDPAbs", DBL_MAX,    0x7f, 0xef, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff);
		Error+=double_is_double_test(IEEEDPAbs,"IEEEDPAbs",-FLT_MAX,    0x47, 0xef, 0xff, 0xff, 0xe0, 0x00, 0x00, 0x00);
		Error+=double_is_double_test(IEEEDPAbs,"IEEEDPAbs",-DBL_MAX,    0x7f, 0xef, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff);

		printf("===============================================\n\n");

		Error+=double_is_double_test(IEEEDPCeil,"IEEEDPCeil",      -1,    0xbf, 0xf0, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00);
		Error+=double_is_double_test(IEEEDPCeil,"IEEEDPCeil",       1,    0x3f, 0xf0, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00);
		Error+=double_is_double_test(IEEEDPCeil,"IEEEDPCeil",       0,    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00);
		Error+=double_is_double_test(IEEEDPCeil,"IEEEDPCeil", FLT_MIN,    0x3f, 0xf0, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00);
		Error+=double_is_double_test(IEEEDPCeil,"IEEEDPCeil", FLT_MAX,    0x47, 0xef, 0xff, 0xff, 0xe0, 0x00, 0x00, 0x00);
		Error+=double_is_double_test(IEEEDPCeil,"IEEEDPCeil", DBL_MIN,    0x3f, 0xf0, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00);
		Error+=double_is_double_test(IEEEDPCeil,"IEEEDPCeil", DBL_MAX,    0x7f, 0xef, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff);
		Error+=double_is_double_test(IEEEDPCeil,"IEEEDPCeil",-FLT_MIN,    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00);
		Error+=double_is_double_test(IEEEDPCeil,"IEEEDPCeil",-FLT_MAX,    0xc7, 0xef, 0xff, 0xff, 0xe0, 0x00, 0x00, 0x00);
		Error+=double_is_double_test(IEEEDPCeil,"IEEEDPCeil",-DBL_MIN,    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00);
		Error+=double_is_double_test(IEEEDPCeil,"IEEEDPCeil",-DBL_MAX,    0xff, 0xef, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff);

		printf("===============================================\n\n");


		Error+=double_is_long_test(IEEEDPFlt,"IEEEDPFlt",0,          0x00, 0x00,0x00,0x00,0x00,0x00,0x00,0x00);
        Error+=double_is_long_test(IEEEDPFlt,"IEEEDPFlt",1000,       0x40, 0x8f, 0x40, 0x00, 0x00, 0x00, 0x00, 0x00);
        Error+=double_is_long_test(IEEEDPFlt,"IEEEDPFlt",-1000,      0xc0, 0x8f, 0x40, 0x00, 0x00, 0x00, 0x00, 0x00);
        Error+=double_is_long_test(IEEEDPFlt,"IEEEDPFlt",INT_MAX,    0x41, 0xdf, 0xff, 0xff, 0xff, 0xc0, 0x00, 0x00);
        Error+=double_is_long_test(IEEEDPFlt,"IEEEDPFlt",INT_MIN,    0xc1, 0xe0, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00);

		printf("===============================================\n\n");

        Error= double_is_double_double_test(IEEEDPMul,"EEEDPMul",0,       0,          0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00);
        Error+=double_is_double_double_test(IEEEDPMul,"EEEDPMul",INT_MAX, 1000,       0x42, 0x7f, 0x3f, 0xff, 0xff, 0xc1, 0x80, 0x00);
        Error+=double_is_double_double_test(IEEEDPMul,"EEEDPMul",1000,    INT_MIN,    0xc2, 0x7f, 0x40, 0x00, 0x00, 0x00, 0x00, 0x00);
        Error+=double_is_double_double_test(IEEEDPMul,"EEEDPMul",INT_MAX, INT_MAX,    0x43, 0xcf, 0xff, 0xff, 0xff, 0x80, 0x00, 0x00);
        Error+=double_is_double_double_test(IEEEDPMul,"EEEDPMul",INT_MIN, INT_MIN,    0x43, 0xd0, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00);

        printf("===============================================\n\n");
        Error+=double_is_double_test(IEEEDPNeg,"IEEEDPNeg",      -1,    0x3f, 0xf0, 0x00 ,0x00, 0x00, 0x00, 0x00, 0x00);
		Error+=double_is_double_test(IEEEDPNeg,"IEEEDPNeg",       1,    0xbf, 0xf0, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00);
		Error+=double_is_double_test(IEEEDPNeg,"IEEEDPNeg", FLT_MIN,    0xb8, 0x10, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00);
		Error+=double_is_double_test(IEEEDPNeg,"IEEEDPNeg", FLT_MAX,    0xc7, 0xef, 0xff, 0xff, 0xe0, 0x00, 0x00, 0x00);
		Error+=double_is_double_test(IEEEDPNeg,"IEEEDPNeg", DBL_MIN,    0x80, 0x10, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00);
		Error+=double_is_double_test(IEEEDPNeg,"IEEEDPNeg", DBL_MAX,    0xff, 0xef, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff);
		Error+=double_is_double_test(IEEEDPNeg,"IEEEDPNeg",-FLT_MIN,    0x38, 0x10, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00);
		Error+=double_is_double_test(IEEEDPNeg,"IEEEDPNeg",-FLT_MAX,    0x47, 0xef, 0xff, 0xff, 0xe0, 0x00, 0x00, 0x00);
		Error+=double_is_double_test(IEEEDPNeg,"IEEEDPNeg",-DBL_MIN,    0x00, 0x10, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00);
		Error+=double_is_double_test(IEEEDPNeg,"IEEEDPNeg",-DBL_MAX,    0x7f, 0xef, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff);

		printf("===============================================\n\n");

        Error+=long_is_double_double_test(IEEEDPCmp,"IEEEDPCmp",0,             0,    0x00, 0x00, 0x00, 0x00);
        Error+=long_is_double_double_test(IEEEDPCmp,"IEEEDPCmp",1000,         10,    0x00, 0x00, 0x00, 0x01);
        Error+=long_is_double_double_test(IEEEDPCmp,"IEEEDPCmp",-1000,        10,    0xff, 0xff, 0xff, 0xff);
        Error+=long_is_double_double_test(IEEEDPCmp,"IEEEDPCmp",INT_MAX,      10,    0x00, 0x00, 0x00, 0x01);
        Error+=long_is_double_double_test(IEEEDPCmp,"IEEEDPCmp",INT_MIN,      10,    0xff, 0xff, 0xff, 0xff);
        Error+=long_is_double_double_test(IEEEDPCmp,"IEEEDPCmp",INT_MAX, INT_MAX,    0x00, 0x00, 0x00, 0x00);
        Error+=long_is_double_double_test(IEEEDPCmp,"IEEEDPCmp",INT_MIN, INT_MIN,    0x00, 0x00, 0x00, 0x00);

        printf("===============================================\n\n");

        Error+=long_is_double_test(IEEEDPFix,"IEEEDPFix",      0,        0x00, 0x00, 0x00, 0x00);
        Error+=long_is_double_test(IEEEDPFix,"IEEEDPFix",   1000,        0x00, 0x00, 0x03, 0xe8);
        Error+=long_is_double_test(IEEEDPFix,"IEEEDPFix",  -1000,        0xff, 0xff, 0xfc, 0x18);
        Error+=long_is_double_test(IEEEDPFix,"IEEEDPFix",INT_MAX,        0x7f, 0xff, 0xff, 0xff);

        Error+=long_is_double_test(IEEEDPFix,"IEEEDPFix",    INT_MIN,    0x80, 0x00, 0x00, 0x00);
        Error+=long_is_double_test(IEEEDPFix,"IEEEDPFix",2.0*INT_MAX,    0x7f, 0xff, 0xff, 0xff);
        Error+=long_is_double_test(IEEEDPFix,"IEEEDPFix",2.0*INT_MIN,    0x80, 0x00, 0x00, 0x00);
        Error+=long_is_double_test(IEEEDPFix,"IEEEDPFix"    ,DBL_MAX,    0x7f, 0xff, 0xff, 0xff);
        Error+=long_is_double_test(IEEEDPFix,"IEEEDPFix",    DBL_MIN,    0x00, 0x00, 0x00, 0x00);

        printf("===============================================\n\n");

        Error+=double_is_double_test(IEEEDPFloor,"IEEEDPFloor",     -1,    0xbf, 0xf0, 0x00 ,0x00, 0x00, 0x00, 0x00, 0x00);
		Error+=double_is_double_test(IEEEDPFloor,"IEEEDPFloor",      1,    0x3f, 0xf0, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00);
		Error+=double_is_double_test(IEEEDPFloor,"IEEEDPFloor",      0,    0x00 ,0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00);
		Error+=double_is_double_test(IEEEDPFloor,"IEEEDPFloor",FLT_MIN,    0x00 ,0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00);
		Error+=double_is_double_test(IEEEDPFloor,"IEEEDPFloor",FLT_MAX,    0x47, 0xef, 0xff, 0xff, 0xe0, 0x00, 0x00, 0x00);
		Error+=double_is_double_test(IEEEDPFloor,"IEEEDPFloor",DBL_MIN,    0x00 ,0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00);
		Error+=double_is_double_test(IEEEDPFloor,"IEEEDPFloor",DBL_MAX,    0x7f, 0xef, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff);

		printf("===============================================\n\n");

		CloseLibrary(MathIeeeDoubBasBase);
	}
	else
	{
		printf("Can't open mathieeedoubbas.library\n");
		Error++;
	}

	return Error;
}


/* ####################################################################################################### */


int test_MathIeeeDoubTrans(void)
{
	int Error=0;
	MathIeeeDoubTransBase=OpenLibrary((unsigned char*)"mathieeedoubtrans.library",34);
	if(MathIeeeDoubTransBase)
	{

		printf("mathieeedoubtrans.library %d.%d\n\n",MathIeeeDoubTransBase->lib_Version,MathIeeeDoubTransBase->lib_Revision);
        // expeced results are from mathieeedoubtrans.library 37.1 (OS3.1)


		// acos is defined from -1 ... +1 ,and has values  -Pi/2 ... +Pi/2
		Error+=double_is_double_test(IEEEDPAcos,"IEEEDPAcos",  -1, 0x40,    0x09, 0x21, 0xfb, 0x54, 0x44, 0x2d, 0x18);
		Error+=double_is_double_test(IEEEDPAcos,"IEEEDPAcos",   1, 0x00,    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00);
		Error+=double_is_double_test(IEEEDPAcos,"IEEEDPAcos",   0, 0x3f,    0xf9, 0x21, 0xfb, 0x54, 0x44, 0x2d, 0x18);
		Error+=double_is_double_test(IEEEDPAcos,"IEEEDPAcos",-0.5, 0x40,    0x00, 0xc1, 0x52, 0x38, 0x2d, 0x73, 0x65);
		Error+=double_is_double_test(IEEEDPAcos,"IEEEDPAcos", 0.5, 0x3f,    0xf0, 0xc1, 0x52, 0x38, 0x2d, 0x73, 0x65);

		printf("===============================================\n\n");

        Error+=double_is_double_test(IEEEDPSqrt,"IEEEDPSqrt",      0,    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00);
        Error+=double_is_double_test(IEEEDPSqrt,"IEEEDPSqrt",   1000,    0x40, 0x3f, 0x9f, 0x6e, 0x49, 0x90, 0xf2, 0x27);
        Error+=double_is_double_test(IEEEDPSqrt,"IEEEDPSqrt",FLT_MAX,    0x43, 0xef, 0xff, 0xff, 0xef, 0xff, 0xff, 0xfb);
        Error+=double_is_double_test(IEEEDPSqrt,"IEEEDPSqrt",DBL_MAX,    0x5f, 0xef, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff);
        Error+=double_is_double_test(IEEEDPSqrt,"IEEEDPSqrt",  -1000,    0xff, 0xf8, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00);

        printf("===============================================\n\n");
               
        Error+=double_is_double_test(IEEEDPLog10,"IEEEDPLog10",      0,    0xff, 0xf0, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00);
        Error+=double_is_double_test(IEEEDPLog10,"IEEEDPLog10",   1000,    0x40, 0x07, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff);
        Error+=double_is_double_test(IEEEDPLog10,"IEEEDPLog10",FLT_MAX,    0x40, 0x43, 0x44, 0x13, 0x50, 0x67, 0xe3, 0x08);
        Error+=double_is_double_test(IEEEDPLog10,"IEEEDPLog10",DBL_MAX,    0x40, 0x73, 0x44, 0x13, 0x50, 0x9f, 0x79, 0xfe);
        Error+=double_is_double_test(IEEEDPLog10,"IEEEDPLog10",  -1000,    0xff, 0xf8, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00);

        printf("===============================================\n\n");

        Error+=double_is_double_double_test(IEEEDPPow,"IEEEDPPow",0,            0,    0x3f, 0xf0, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00);
        Error+=double_is_double_double_test(IEEEDPPow,"IEEEDPPow",1000.0,     0.0,    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00);
        Error+=double_is_double_double_test(IEEEDPPow,"IEEEDPPow",FLT_MAX,FLT_MAX,    0x7f, 0xef, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff);
        Error+=double_is_double_double_test(IEEEDPPow,"IEEEDPPow",DBL_MAX,DBL_MAX,    0x7f, 0xef, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff);
        Error+=double_is_double_double_test(IEEEDPPow,"IEEEDPPow",  -1000,  -1000,    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00);
        Error+=double_is_double_double_test(IEEEDPPow,"IEEEDPPow",      3,      4,    0x40, 0x50, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00);

        printf("===============================================\n\n");

		CloseLibrary(MathIeeeDoubTransBase);
	}
	else
	{
		printf("Can't open mathieeedoubtrans.library\n");
		Error++;
	}

	return Error;
}



int SMult32_Test(long factor1, long factor2, unsigned char *ExpectedResult)
{
    double Result;
    static char Function[1024];

    Result=SMult32(factor1,factor2);

    snprintf(Function,1024,"SMult32(%ld * %ld)= ",factor1,factor2);
    return  printLong(Function,Result,ExpectedResult);
}


int test_Utility(void)
{
        int Error=0;
        UtilityBase=OpenLibrary((unsigned char*)"utility.library",34);
        if(UtilityBase)
        {
        	printf("utility.library %d.%d\n\n",UtilityBase->lib_Version,UtilityBase->lib_Revision);
            // expeced results are from utility.library 40.1 (OS3.1)

            Error+=long_is_long_long_test(SMult32,"SMult32",     32,     32,    0x00, 0x00, 0x04, 0x00);
            Error+=long_is_long_long_test(SMult32,"SMult32",INT_MAX,INT_MAX,    0x00, 0x00, 0x00, 0x01);
            Error+=long_is_long_long_test(SMult32,"SMult32",INT_MAX,      2,    0xff, 0xff, 0xff, 0xfe);
            Error+=long_is_long_long_test(SMult32,"SMult32",    -32,     32,    0xff, 0xff, 0xfc, 0x00);
            Error+=long_is_long_long_test(SMult32,"SMult32",    -32,    -32,    0x00, 0x00, 0x04, 0x00);
            Error+=long_is_long_long_test(SMult32,"SMult32",INT_MIN,      2,    0x00, 0x00, 0x00, 0x00);
            Error+=long_is_long_long_test(SMult32,"SMult32",INT_MIN,INT_MIN,    0x00, 0x00, 0x00, 0x00);
            Error+=long_is_long_long_test(SMult32,"SMult32",INT_MAX,INT_MIN,    0x80, 0x00, 0x00, 0x00);

            printf("===============================================\n\n");

            CloseLibrary(UtilityBase);
        }
        else
        {
            printf("Can't open mathieeedoubtrans.library\n");
            Error++;
        }

        return Error;
}




int main(void)
{
	int Error=0;
	
	Error+=test_MathIeeeDoubBas();
//	Error+=test_MathIeeeDoubTrans();
//	Error+=test_Utility();

    // some testprintfs with %f
/*
	printf("1     = %f\n",1.0);
	printf("0.1   = %f\n",0.1);
	printf("0.02  = %f\n",0.02);
	printf("1.23  = %f\n",1.23);
    printf("-1.23 = %f\n",-1.23);
	printf("-0.1  = %f\n",-0.1);
	printf("-0.02 = %f\n",-0.02);
	printf("PI    = %f\n",(double)3.141592653589793);
	
*/
	if(Error)
	{
		printf("\033[31m%s\033[0m","Some tests failed!\n");
	}
	else
	{
        printf("\033[32m%s\033[0m","All tests passed\n");
	}

	return Error;
}


/*

mathieeedoubbas.library
     IEEEDPAbs()               Te
     IEEEDPAdd()
     IEEEDPCeil()              Te
     IEEEDPCmp()               Test
     IEEEDPDiv()
     IEEEDPFix()               Test
     IEEEDPFloor()             Te
     IEEEDPFlt()               Test
     IEEEDPMul()               Test
     IEEEDPNeg()               Te
     IEEEDPSub()
     IEEEDPTst()


mathieeedoubtrans.library
     IEEEDPAcos()              Test
     IEEEDPAsin()
     IEEEDPAtan()
     IEEEDPCos()
     IEEEDPCosh()
     IEEEDPExp()
     IEEEDPFieee()
     IEEEDPLog()
     IEEEDPLog10()             Test
     IEEEDPPow()               Test
     IEEEDPSin()
     IEEEDPSincos()
     IEEEDPSinh()
     IEEEDPSqrt()              Test
     IEEEDPTan()
     IEEEDPTanh()
     IEEEDPTieee()


utility.library
     AddNamedObject()
     AllocateTagItems()
     AllocNamedObjectA()
     Amiga2Date()
     ApplyTagChanges()
     AttemptRemNamedObject()
     CallHookPkt()
     CheckDate()
     CloneTagItems()
     Date2Amiga()
     FilterTagChanges()
     FilterTagItems()
     FindNamedObject()
     FindTagItem()
     FreeNamedObject()
     FreeTagItems()
     GetTagData()
     GetUniqueID()
     MapTags()
     NamedObjectName()
     NextTagItem()
     PackBoolTags()
     PackStructureTags()
     RefreshTagItemClones()
     ReleaseNamedObject()
     RemNamedObject()
     SDivMod32()
     SMult32()                 Test
     SMult64()
     Stricmp()
     Strnicmp()
     TagInArray()
     ToLower()
     ToUpper()
     UDivMod32()
     UMult32()
     UMult64()
     UnpackStructureTags()


*/
