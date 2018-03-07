const ULONG dbl_max_ul[2] = { 0x7FEFFFFFUL, 0xFFFFFFFFUL };
const ULONG dbl_min_ul[2] = { 0x00100000UL, 0x00000000UL };
const ULONG dbl_max_neg_ul[2] = { 0xFFEFFFFFUL, 0xFFFFFFFFUL };
const ULONG dbl_min_neg_ul[2] = { 0x80100000UL, 0x00000000UL };

const ULONG flt_max_ul[2] = { 0x47EFFFFFUL, 0xE091FF3DUL };
const ULONG flt_min_ul[2] = { 0x380FFFFFUL, 0xFF9FDBA8UL };
const ULONG flt_max_neg_ul[2] = { 0xC7EFFFFFUL, 0xE091FF3DUL };
const ULONG flt_min_neg_ul[2] = { 0xB80FFFFFUL, 0xFF9FDBA8UL };

const ULONG flt_flt_max[1] = { 0x7F7FFFFFUL };
const ULONG flt_flt_min[1] = { 0x00100000UL };
const ULONG flt_flt_max_neg[1] = { 0xFF7FFFFFUL };
const ULONG flt_flt_min_neg[1] = { 0x80100000UL };

/* double constants */
#define DBL_MAX (*(const double *)(const void *)dbl_max_ul)
#define DBL_MIN (*(const double *)(const void *)dbl_min_ul)
#define DBL_MAX_NEG (*(const double *)(const void *)dbl_max_neg_ul)
#define DBL_MIN_NEG (*(const double *)(const void *)dbl_min_neg_ul)

#define FLT_MAX (*(const double *)(const void *)flt_max_ul)
#define FLT_MIN (*(const double *)(const void *)flt_min_ul)
#define FLT_MAX_NEG (*(const double *)(const void *)flt_max_neg_ul)
#define FLT_MIN_NEG (*(const double *)(const void *)flt_min_neg_ul)

/* float constants */
#define FLT_FLT_MAX (*(const float *)(const void *)flt_flt_max)
#define FLT_FLT_MIN (*(const float *)(const void *)flt_flt_min)
#define FLT_FLT_MAX_NEG (*(const float *)(const void *)flt_flt_max_neg)
#define FLT_FLT_MIN_NEG (*(const float *)(const void *)flt_flt_min_neg)
