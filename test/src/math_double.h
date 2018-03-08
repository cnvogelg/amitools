const ULONG dbl_max_ul[2] = { 0x7FEFFFFFUL, 0xFFFFFFFFUL };
const ULONG dbl_min_ul[2] = { 0x00100000UL, 0x00000000UL };
const ULONG dbl_max_neg_ul[2] = { 0xFFEFFFFFUL, 0xFFFFFFFFUL };
const ULONG dbl_min_neg_ul[2] = { 0x80100000UL, 0x00000000UL };

const ULONG dbl_flt_max_ul[2] = { 0x47EFFFFFUL, 0xE091FF3DUL };
const ULONG dbl_flt_min_ul[2] = { 0x380FFFFFUL, 0xFF9FDBA8UL };
const ULONG dbl_flt_max_neg_ul[2] = { 0xC7EFFFFFUL, 0xE091FF3DUL };
const ULONG dbl_flt_min_neg_ul[2] = { 0xB80FFFFFUL, 0xFF9FDBA8UL };

/* double constants */
#define DBL_MAX (*(const double *)(const void *)dbl_max_ul)
#define DBL_MIN (*(const double *)(const void *)dbl_min_ul)
#define DBL_MAX_NEG (*(const double *)(const void *)dbl_max_neg_ul)
#define DBL_MIN_NEG (*(const double *)(const void *)dbl_min_neg_ul)

#define DBL_FLT_MAX (*(const double *)(const void *)dbl_flt_max_ul)
#define DBL_FLT_MIN (*(const double *)(const void *)dbl_flt_min_ul)
#define DBL_FLT_MAX_NEG (*(const double *)(const void *)dbl_flt_max_neg_ul)
#define DBL_FLT_MIN_NEG (*(const double *)(const void *)dbl_flt_min_neg_ul)
