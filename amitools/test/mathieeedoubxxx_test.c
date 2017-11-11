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



int IEEEDPFix_Test(double value, unsigned char *ExpectedResult)
{
    double Result;
    static char Function[1024];

    Result=IEEEDPFix(value);  // Condition codes all undefined

    snprintf(Function,1024,"IEEEDPFix(%f)= ",value);
    return  printDouble(Function,Result,ExpectedResult);
}



int test_MathIeeeDoubBas(void)
{
	int Error=0;
	MathIeeeDoubBasBase=OpenLibrary((unsigned char*)"mathieeedoubbas.library",34);
	if(MathIeeeDoubBasBase)
	{
		printf("mathieeedoubbas.library %d.%d\n\n",MathIeeeDoubBasBase->lib_Version,MathIeeeDoubBasBase->lib_Revision);
                // expeced results are from mathieeedoubbas.library 38.1 (OS3.1)

			            Error+=double_is_long_test(IEEEDPFlt,"IEEEDPFlt",0,       0x00,     0x00,0x00,0x00,0x00,0x00,0x00,0x00);
                        Error+=double_is_long_test(IEEEDPFlt,"IEEEDPFlt",1000,    0x40,     0x8f, 0x40, 0x00, 0x00, 0x00, 0x00, 0x00);
                        Error+=double_is_long_test(IEEEDPFlt,"IEEEDPFlt",-1000,   0xc0,     0x8f, 0x40, 0x00, 0x00, 0x00, 0x00, 0x00);
                        Error+=double_is_long_test(IEEEDPFlt,"IEEEDPFlt",INT_MAX, 0x41,     0xdf, 0xff, 0xff, 0xff, 0xc0, 0x00, 0x00);
                        Error+=double_is_long_test(IEEEDPFlt,"IEEEDPFlt",INT_MIN, 0xc1,     0xe0, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00);

		        printf("===============================================\n\n");

                        Error= double_is_double_double_test(IEEEDPMul,"EEEDPMul",0,       0,          0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00);
                        Error+=double_is_double_double_test(IEEEDPMul,"EEEDPMul",INT_MAX, 1000,       0x42, 0x7f, 0x3f, 0xff, 0xff, 0xc1, 0x80, 0x00);
                        Error+=double_is_double_double_test(IEEEDPMul,"EEEDPMul",1000,    INT_MIN,    0xc2, 0x7f, 0x40, 0x00, 0x00, 0x00, 0x00, 0x00);
                        Error+=double_is_double_double_test(IEEEDPMul,"EEEDPMul",INT_MAX, INT_MAX,    0x43, 0xcf, 0xff, 0xff, 0xff, 0x80, 0x00, 0x00);
                        Error+=double_is_double_double_test(IEEEDPMul,"EEEDPMul",INT_MIN, INT_MIN,    0x43, 0xd0, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00);

                printf("===============================================\n\n");

                        Error+=long_is_double_double_test(IEEEDPCmp,"IEEEDPCmp",0,             0,    0x00, 0x00, 0x00, 0x00);
                        Error+=long_is_double_double_test(IEEEDPCmp,"IEEEDPCmp",1000,         10,    0x00, 0x00, 0x00, 0x01);
                        Error+=long_is_double_double_test(IEEEDPCmp,"IEEEDPCmp",-1000,        10,    0xff, 0xff, 0xff, 0xff);
                        Error+=long_is_double_double_test(IEEEDPCmp,"IEEEDPCmp",INT_MAX,      10,    0x00, 0x00, 0x00, 0x01);
                        Error+=long_is_double_double_test(IEEEDPCmp,"IEEEDPCmp",INT_MIN,      10,    0xff, 0xff, 0xff, 0xff);
                        Error+=long_is_double_double_test(IEEEDPCmp,"IEEEDPCmp",INT_MAX, INT_MAX,    0x00, 0x00, 0x00, 0x00);
                        Error+=long_is_double_double_test(IEEEDPCmp,"IEEEDPCmp",INT_MIN, INT_MIN,    0x00, 0x00, 0x00, 0x00);


                printf("===============================================\n\n");
                        Error+=long_is_double_test(IEEEDPFix,"IEEEDPFix",0,              0x00, 0x00, 0x00, 0x00);
                        Error+=long_is_double_test(IEEEDPFix,"IEEEDPFix",1000,           0x00, 0x00, 0x03, 0xe8);
                        Error+=long_is_double_test(IEEEDPFix,"IEEEDPFix",-1000,          0xff, 0xff, 0xfc, 0x18);
                        Error+=long_is_double_test(IEEEDPFix,"IEEEDPFix",INT_MAX,        0x7f, 0xff, 0xff, 0xff);

                        Error+=long_is_double_test(IEEEDPFix,"IEEEDPFix",INT_MIN,        0x80, 0x00, 0x00, 0x00);
                        Error+=long_is_double_test(IEEEDPFix,"IEEEDPFix",2.0*INT_MAX,    0x7f, 0xff, 0xff, 0xff);
                        Error+=long_is_double_test(IEEEDPFix,"IEEEDPFix",2.0*INT_MIN,    0x80, 0x00, 0x00, 0x00);
                        Error+=long_is_double_test(IEEEDPFix,"IEEEDPFix",DBL_MAX,        0x7f, 0xff, 0xff, 0xff);
                        Error+=long_is_double_test(IEEEDPFix,"IEEEDPFix",DBL_MIN,        0x00, 0x00, 0x00, 0x00);


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

int IEEEDPAcos_Test(double value, unsigned char *ExpectedResult)
{
    double Result;
    static char Function[1024];

    Result=IEEEDPAcos(value);  // Condition codes all undefined

    snprintf(Function,1024,"IEEEDPAcos(%f)= ",value);
    return  printDouble(Function,Result,ExpectedResult);
}


int IEEEDPSqrt_Test(double value, unsigned char *ExpectedResult)
{
    double Result;
    static char Function[1024];

    Result=IEEEDPSqrt(value);  // Condition codes all undefined

    snprintf(Function,1024,"IEEEDPSqrt(%f)= ",value);
    return  printDouble(Function,Result,ExpectedResult);
}

int IEEEDPLog10_Test(double value, unsigned char *ExpectedResult)
{
    double Result;
    static char Function[1024];

    Result=IEEEDPLog10(value);  // Condition codes all undefined

    snprintf(Function,1024,"IEEEDPLog10(%f)= ",value);
    return  printDouble(Function,Result,ExpectedResult);
}


int IEEEDPPow_Test(double value1, double value2, unsigned char *ExpectedResult)
{
    double Result;
    static char Function[1024];

    Result=IEEEDPPow(value1,value2);

    snprintf(Function,1024,"IEEEDPPow(%f hoch %f)= ",value2,value1);
    return  printDouble(Function,Result,ExpectedResult);
}


int test_MathIeeeDoubTrans(void)
{
	int Error=0;
	MathIeeeDoubTransBase=OpenLibrary((unsigned char*)"mathieeedoubtrans.library",34);
	if(MathIeeeDoubTransBase)
	{

		printf("mathieeedoubtrans.library %d.%d\n\n",MathIeeeDoubTransBase->lib_Version,MathIeeeDoubTransBase->lib_Revision);
                // expeced results are from mathieeedoubtrans.library 37.1 (OS3.1)


		// acos is defined from -1 ... +1 ,and has values  -Pi/2 ... +Pi/2
		{
			unsigned char ExpectedResult[8]={0x40, 0x09, 0x21, 0xfb, 0x54, 0x44, 0x2d, 0x18};
			Error+=IEEEDPAcos_Test(-1,ExpectedResult);
		}

		{
			unsigned char ExpectedResult[8]={0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00};
			Error+=IEEEDPAcos_Test(1,ExpectedResult);
		}

		{
			unsigned char ExpectedResult[8]={0x3f, 0xf9, 0x21, 0xfb, 0x54, 0x44, 0x2d, 0x18};
			Error+=IEEEDPAcos_Test(0,ExpectedResult);
		}

		{
			unsigned char ExpectedResult[8]={0x40, 0x00, 0xc1, 0x52, 0x38, 0x2d, 0x73, 0x65};
			Error+=IEEEDPAcos_Test(-0.5,ExpectedResult);
		}

		{
			unsigned char ExpectedResult[8]={0x3f, 0xf0, 0xc1, 0x52, 0x38, 0x2d, 0x73, 0x65};
			Error+=IEEEDPAcos_Test(0.5,ExpectedResult);
		}


		printf("===============================================\n\n");

                {
                        unsigned char ExpectedResult[8]={0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00};
                        Error+=IEEEDPSqrt_Test(0,ExpectedResult);
                }

                {
                        unsigned char ExpectedResult[8]={0x40, 0x3f, 0x9f, 0x6e, 0x49, 0x90, 0xf2, 0x27};
                        Error+=IEEEDPSqrt_Test(1000,ExpectedResult);
                }

                {
                        unsigned char ExpectedResult[8]={0x43, 0xef, 0xff, 0xff, 0xef, 0xff, 0xff, 0xfb};
                        Error+=IEEEDPSqrt_Test(FLT_MAX,ExpectedResult);
                }

                {
                        unsigned char ExpectedResult[8]={0x5f, 0xef, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff};
                        Error+=IEEEDPSqrt_Test(DBL_MAX,ExpectedResult);
                }

/*
                        IEEEDPSqrt()   
                	Might have returned bare nonsense if the argument was out of range
                        for pre-V45 releases. Returns NAN for V45 in these cases.
*/
                {
                        unsigned char ExpectedResult[8]={0xff, 0xf8, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00};
                        Error+=IEEEDPSqrt_Test(-1000,ExpectedResult);
                }


                printf("===============================================\n\n");

               
                // defined from 0 ... infinity 
                {
                        unsigned char ExpectedResult[8]={0xff, 0xf0, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00};
                        Error+=IEEEDPLog10_Test(0,ExpectedResult);
                }

                {
                        unsigned char ExpectedResult[8]={0x40, 0x07, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff};
                        Error+=IEEEDPLog10_Test(1000,ExpectedResult);
                }

                {
                        unsigned char ExpectedResult[8]={0x40, 0x43, 0x44, 0x13, 0x50, 0x67, 0xe3, 0x08};
                        Error+=IEEEDPLog10_Test(FLT_MAX,ExpectedResult);
                }

                {
                        unsigned char ExpectedResult[8]={0x40, 0x73, 0x44, 0x13, 0x50, 0x9f, 0x79, 0xfe};
                        Error+=IEEEDPLog10_Test(DBL_MAX,ExpectedResult);
                }

                {
                        unsigned char ExpectedResult[8]={0xff, 0xf8, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00};
                        Error+=IEEEDPLog10_Test(-1000,ExpectedResult);
                }


                printf("===============================================\n\n");

               {
                        unsigned char ExpectedResult[8]={0x3f, 0xf0, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00};
                        Error+=IEEEDPPow_Test(0,0,ExpectedResult);
                }

                {
                        unsigned char ExpectedResult[8]={0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00};
                        Error+=IEEEDPPow_Test(1000.0,0.0,ExpectedResult);
                }

                {
                        unsigned char ExpectedResult[8]={0x7f, 0xef, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff};
                        Error+=IEEEDPPow_Test(FLT_MAX,FLT_MAX,ExpectedResult);
                }

                {
                        unsigned char ExpectedResult[8]={0x7f, 0xef, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff};
                        Error+=IEEEDPPow_Test(DBL_MAX,DBL_MAX,ExpectedResult);
                }

                {
                        unsigned char ExpectedResult[8]={0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00};
                        Error+=IEEEDPPow_Test(-1000,-1000,ExpectedResult);
                }

                {
                        unsigned char ExpectedResult[8]={0x40, 0x50, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00};
                        Error+=IEEEDPPow_Test(3,4,ExpectedResult);
                }


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


                {
                        unsigned char ExpectedResult[4]={0x00, 0x00, 0x04, 0x00};
                        Error+=SMult32_Test(32,32,ExpectedResult);
                }

                {
                        unsigned char ExpectedResult[4]={0x00, 0x00, 0x00, 0x01};
                        Error+=SMult32_Test(INT_MAX,INT_MAX,ExpectedResult);
                }

                {
                        unsigned char ExpectedResult[4]={0xff, 0xff, 0xff, 0xfe};
                        Error+=SMult32_Test(INT_MAX,2,ExpectedResult);
                }

                {
                        unsigned char ExpectedResult[4]={0xff, 0xff, 0xfc, 0x00};
                        Error+=SMult32_Test(-32,32,ExpectedResult);
                }

                {
                        unsigned char ExpectedResult[4]={0x00, 0x00, 0x04, 0x00};
                        Error+=SMult32_Test(-32,-32,ExpectedResult);
                }

                {
                        unsigned char ExpectedResult[4]={0x00, 0x00, 0x00, 0x00};
                        Error+=SMult32_Test(INT_MIN,2,ExpectedResult);
                }

                {
                        unsigned char ExpectedResult[4]={0x00, 0x00, 0x00, 0x00};
                        Error+=SMult32_Test(INT_MIN,INT_MIN,ExpectedResult);
                }

                {
                        unsigned char ExpectedResult[4]={0x80, 0x00, 0x00, 0x00};
                        Error+=SMult32_Test(INT_MAX,INT_MIN,ExpectedResult);
                }

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

	printf("1     = %f\n",1.0);
	printf("0.1   = %f\n",0.1);
	printf("0.02  = %f\n",0.02);
	printf("1.23  = %f\n",1.23);
    printf("-1.23 = %f\n",-1.23);
	printf("-0.1  = %f\n",-0.1);
	printf("-0.02 = %f\n",-0.02);
	printf("PI    = %f\n",(double)3.141592653589793);
	

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
IEEEDPAdd(        mathieeedoubbas
IEEEDPCmp(        mathieeedoubbas                   Test
IEEEDPDiv(        mathieeedoubbas
IEEEDPFix(        mathieeedoubbas                   Test
IEEEDPFlt(        mathieeedoubbas                   Test
IEEEDPMul(        mathieeedoubbas                   Test
IEEEDPSub(        mathieeedoubbas

IEEEDPAcos(       MathIEEEDoubTransLibrary	    Test
IEEEDPLog10(      MathIEEEDoubTransLibrary          Test
IEEEDPSqrt(       MathIEEEDoubTransLibrary          Test

*/
