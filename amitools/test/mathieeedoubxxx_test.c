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


int printDouble(char *Function,double value,unsigned char *ExpectedResult)
{
    static unsigned char ResultArray[8];

    double *ValuePtr=&value;
    unsigned int i;
    int Error=0;

    printf("%s",Function);
    printf("\nhere                    ");
    for(i=0;i<8;i++)
    {
        ResultArray[i]=((unsigned char*)ValuePtr)[i];	
	printf("%02x ",ResultArray[i]);
    }

    printf("\nreference real Amiga    ");

    for(i=0;i<8;i++)
    {
            if(ResultArray[i]==ExpectedResult[i])
            {
                printf("%02x ",ExpectedResult[i]);
            }
            else if ((i==7) && ((ResultArray[i]==ExpectedResult[i]+1) || (ResultArray[i]==ExpectedResult[i]-1))) // allow +-1 in lowest byte
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
            else if ((i==7) && ((ResultArray[i]==ExpectedResult[i]+1) || (ResultArray[i]==ExpectedResult[i]-1))) // allow +-1 in lowest byte
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


int IEEEDPFlt_Test(int value, unsigned char *ExpectedResult)
{
    double Result;
    char Function[64];

    Result=IEEEDPFlt(value);  // Condition codes all undefined

    snprintf(Function,64,"IEEEDPFlt(%d)= ",value);
    return  printDouble(Function,Result,ExpectedResult);
}


int IEEEDPMul_Test(double factor1, double factor2, unsigned char *ExpectedResult)
{
    double Result;
    char Function[64];

    Result=IEEEDPMul(factor1,factor2);  // Condition codes all undefined

    snprintf(Function,64,"IEEEDPMul(%f * %f)= ",factor1,factor2);
    return  printDouble(Function,Result,ExpectedResult);
}

int IEEEDPCmp_Test(double val1, double val2, unsigned char *ExpectedResult)
{
    double Result;
    char Function[64];

    Result=IEEEDPCmp(val1,val2);  // Condition codes ARE changed but not tested here !?!

    snprintf(Function,64,"IEEEDPCmp(%f * %f)= ",val1,val2);
    return  printDouble(Function,Result,ExpectedResult);

}

int IEEEDPFix_Test(double value, unsigned char *ExpectedResult)
{
    double Result;
    char Function[64];

    Result=IEEEDPFix(value);  // Condition codes all undefined

    snprintf(Function,64,"IEEEDPFix(%f)= ",value);
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

		{
			unsigned char ExpectedResult[8]={0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00};
			Error+=IEEEDPFlt_Test(0,ExpectedResult);
		}

                {
                        unsigned char ExpectedResult[8]={0x40, 0x8f, 0x40, 0x00, 0x00, 0x00, 0x00, 0x00};
                        Error+=IEEEDPFlt_Test(1000,ExpectedResult);
                }

                {
                        unsigned char ExpectedResult[8]={0xc0, 0x8f, 0x40, 0x00, 0x00, 0x00, 0x00, 0x00};
                        Error+=IEEEDPFlt_Test(-1000,ExpectedResult);
                }

                {
                        unsigned char ExpectedResult[8]={0x41, 0xdf, 0xff, 0xff, 0xff, 0xc0, 0x00, 0x00};
                        Error+=IEEEDPFlt_Test(INT_MAX,ExpectedResult);
                }

                {
                        unsigned char ExpectedResult[8]={0xc1, 0xe0, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00};
                        Error+=IEEEDPFlt_Test(INT_MIN,ExpectedResult);
                }

		printf("===============================================\n\n");

                {
                        unsigned char ExpectedResult[8]={0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00};
                        Error+=IEEEDPMul_Test(0,0,ExpectedResult);
                }

                {
                        unsigned char ExpectedResult[8]={0x42, 0x7f, 0x3f, 0xff, 0xff, 0xc1, 0x80, 0x00};
                        Error+=IEEEDPMul_Test(INT_MAX,1000,ExpectedResult);
                }

                {
                        unsigned char ExpectedResult[8]={0xc2, 0x7f, 0x40, 0x00, 0x00, 0x00, 0x00, 0x00};
                        Error+=IEEEDPMul_Test(1000,INT_MIN,ExpectedResult);
                }

                {
                        unsigned char ExpectedResult[8]={0x43, 0xcf, 0xff, 0xff, 0xff, 0x80, 0x00, 0x00};
                        Error+=IEEEDPMul_Test(INT_MAX,INT_MAX,ExpectedResult);
                }

                {
                        unsigned char ExpectedResult[8]={0x43, 0xd0, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00};
                        Error+=IEEEDPMul_Test(INT_MIN,INT_MIN,ExpectedResult);
                }

                printf("===============================================\n\n");

                {
                        unsigned char ExpectedResult[8]={0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00};
                        Error+=IEEEDPCmp_Test(0,0,ExpectedResult);
                }

                {
                        unsigned char ExpectedResult[8]={0x3f, 0xf0, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00};
                        Error+=IEEEDPCmp_Test(1000,10,ExpectedResult);
                }

                {
                        unsigned char ExpectedResult[8]={0xbf, 0xf0, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00};
                        Error+=IEEEDPCmp_Test(-1000,10,ExpectedResult);
                }

                {
                        unsigned char ExpectedResult[8]={0x3f, 0xf0, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00};
                        Error+=IEEEDPCmp_Test(INT_MAX,10,ExpectedResult);
                }

                {
                        unsigned char ExpectedResult[8]={0xbf, 0xf0, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00};
                        Error+=IEEEDPCmp_Test(INT_MIN,10,ExpectedResult);
                }

                {
                        unsigned char ExpectedResult[8]={0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00};
                        Error+=IEEEDPCmp_Test(INT_MAX,INT_MAX,ExpectedResult);
                }

                {
                        unsigned char ExpectedResult[8]={0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00};
                        Error+=IEEEDPCmp_Test(INT_MIN,INT_MIN,ExpectedResult);
                }

                printf("===============================================\n\n");
               {
                        unsigned char ExpectedResult[8]={0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00};
                        Error+=IEEEDPFix_Test(0,ExpectedResult);
                }

                {
                        unsigned char ExpectedResult[8]={0x40, 0x8f, 0x40, 0x00, 0x00, 0x00, 0x00, 0x00};
                        Error+=IEEEDPFix_Test(1000,ExpectedResult);
                }

                {
                        unsigned char ExpectedResult[8]={0xc0, 0x8f, 0x40, 0x00, 0x00, 0x00, 0x00, 0x00};
                        Error+=IEEEDPFix_Test(-1000,ExpectedResult);
                }

                {
                        unsigned char ExpectedResult[8]={0x41, 0xdf, 0xff, 0xff, 0xff, 0xc0, 0x00, 0x00};
                        Error+=IEEEDPFix_Test(INT_MAX,ExpectedResult);
                }

                {
                        unsigned char ExpectedResult[8]={0xc1, 0xe0, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00 };
                        Error+=IEEEDPFix_Test(INT_MIN,ExpectedResult);
                }

                {
                        unsigned char ExpectedResult[8]={0x41, 0xdf, 0xff, 0xff, 0xff, 0xc0, 0x00, 0x00};
                        Error+=IEEEDPFix_Test(2.0*INT_MAX,ExpectedResult);
                }

                {
                        unsigned char ExpectedResult[8]={0xc1, 0xe0, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00};
                        Error+=IEEEDPFix_Test(2.0*INT_MIN,ExpectedResult);
                }

                {
                        unsigned char ExpectedResult[8]={0x41, 0xdf, 0xff, 0xff, 0xff, 0xc0, 0x00, 0x00};
                        Error+=IEEEDPFix_Test(DBL_MAX,ExpectedResult);
                }

                {
                        unsigned char ExpectedResult[8]={0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00};
                        Error+=IEEEDPFix_Test(DBL_MIN,ExpectedResult);
                }


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
    char Function[64];

    Result=IEEEDPAcos(value);  // Condition codes all undefined

    snprintf(Function,64,"IEEEDPAcos(%f)= ",value);
    return  printDouble(Function,Result,ExpectedResult);
}


int IEEEDPSqrt_Test(double value, unsigned char *ExpectedResult)
{
    double Result;
    char Function[64];

    Result=IEEEDPSqrt(value);  // Condition codes all undefined

    snprintf(Function,64,"IEEEDPSqrt(%f)= ",value);
    return  printDouble(Function,Result,ExpectedResult);
}

int IEEEDPLog10_Test(double value, unsigned char *ExpectedResult)
{
    double Result;
    char Function[64];

    Result=IEEEDPLog10(value);  // Condition codes all undefined

    snprintf(Function,64,"IEEEDPLog10(%f)= ",value);
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
    char Function[64];

    Result=SMult32(factor1,factor2);

    snprintf(Function,64,"SMult32(%ld * %ld)= ",factor1,factor2);
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
	
//	Error+=test_MathIeeeDoubBas();
//	Error+=test_MathIeeeDoubTrans();
	Error+=test_Utility();

	printf("1     = %f\n",1.0);
//	printf("0.1   = %f\n",0.1);
//	printf("0.02  = %f\n",0.02);
//	printf("1.23  = %f\n",1.23);
//      printf("-1.23 = %f\n",-1.23);
//	printf("-0.1  = %f\n",-0.1);
//	printf("-0.02 = %f\n",-0.02);
//	printf("PI    = %f\n",(double)3.141592653589793);
	

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
