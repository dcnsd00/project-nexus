/*
 * miner.c - miner Bitcoin (double SHA-256) real, pe CPU, cu mai multe variante + benchmark.
 *
 * Compilare (pe laptop):   gcc -O3 -march=native -pthread -o miner miner.c
 * Compilare portabila:     gcc -O3 -mavx2 -pthread -o miner miner.c
 *
 * Folosire:
 *   ./miner bench [N]              # toate variantele, 1 thread, N nonce-uri (implicit 20M)
 *   ./miner run <v> <threads> <N>  # varianta v (0..4), cate thread-uri, N nonce-uri total
 *
 * Validare: scanam o fereastra in jurul nonce-ului REAL al blocului genesis Bitcoin
 * (2083236893). Fiecare varianta trebuie sa-l gaseasca, altfel e gresita.
 *
 * Variante:
 *   0 naiv      : 2x SHA-256 complet pe antet (80 B) la fiecare nonce
 *   1 midstate  : primul bloc (64 B) calculat o data; per nonce doar blocul 2 + hash-ul 2
 *   2 + early   : hash-ul 2 oprit la runda 60; verificam daca ultimul cuvant poate fi 0
 *   3 AVX2 x8   : 8 nonce-uri in paralel pe lane-uri SIMD + midstate + 3 runde precalculate + early exit
 *   4 AVX-512   : 16 nonce-uri in paralel (doar CPU cu AVX-512: Intel server/Xeon, AMD Zen4+)
 */
#ifndef _WIN32
#define _GNU_SOURCE
#endif
#include <errno.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#if defined(_WIN32)
#define WIN32_LEAN_AND_MEAN
#define NOMINMAX
#include <windows.h>
#include <intrin.h>
#else
#include <immintrin.h>
#include <pthread.h>
#endif

#if defined(_WIN32)
#define NEXUS_EXPORT __declspec(dllexport)
#else
#define NEXUS_EXPORT __attribute__((visibility("default")))
#endif


typedef uint32_t u32;
typedef uint64_t u64;
typedef uint8_t u8;

static const u32 K[64] = {
    0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5,
    0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3, 0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174,
    0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc, 0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
    0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7, 0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967,
    0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13, 0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85,
    0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
    0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3,
    0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208, 0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2};
static const u32 IV[8] = {0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a,
                          0x510e527f, 0x9b05688c, 0x1f83d9ab, 0x5be0cd19};

#define ROR(x, n) (((x) >> (n)) | ((x) << (32 - (n))))
#define BS S32(x)
static inline u32 bswap32(u32 x) {
#if defined(_MSC_VER)
    return (u32)_byteswap_ulong((unsigned long)x);
#else
    return __builtin_bswap32(x);
#endif
}
static inline unsigned ctz32(u32 x) {
#if defined(_MSC_VER)
    unsigned long index = 0;
    return _BitScanForward(&index, (unsigned long)x) ? (unsigned)index : 32u;
#else
    return x ? (unsigned)__builtin_ctz(x) : 32u;
#endif
}
static inline u32 S0(u32 x) { return ROR(x, 2) ^ ROR(x, 13) ^ ROR(x, 22); }
static inline u32 S1(u32 x) { return ROR(x, 6) ^ ROR(x, 11) ^ ROR(x, 25); }
static inline u32 s0(u32 x) { return ROR(x, 7) ^ ROR(x, 18) ^ (x >> 3); }
static inline u32 s1(u32 x) { return ROR(x, 17) ^ ROR(x, 19) ^ (x >> 10); }

/* ---------- SHA-256 scalar ---------- */
static void compress(u32 st[8], const u32 in[16]) {
    u32 w[64];
    memcpy(w, in, 64);
    for (int t = 16; t < 64; t++) w[t] = w[t - 16] + s0(w[t - 15]) + w[t - 7] + s1(w[t - 2]);
    u32 a = st[0], b = st[1], c = st[2], d = st[3], e = st[4], f = st[5], g = st[6], h = st[7];
    for (int t = 0; t < 64; t++) {
        u32 t1 = h + S1(e) + ((e & f) ^ (~e & g)) + K[t] + w[t];
        u32 t2 = S0(a) + ((a & b) ^ (a & c) ^ (b & c));
        h = g; g = f; f = e; e = d + t1; d = c; c = b; b = a; a = t1 + t2;
    }
    st[0] += a; st[1] += b; st[2] += c; st[3] += d; st[4] += e; st[5] += f; st[6] += g; st[7] += h;
}

/* al doilea hash (intrare 32 B) oprit dupa runda 60: starea finala h[7] = IV[7] + e(runda 60) */
static u32 second_e60(const u32 d[8]) {
    u32 w[61];
    memcpy(w, d, 32);
    w[8] = 0x80000000u;
    for (int i = 9; i < 15; i++) w[i] = 0;
    w[15] = 256;
    for (int t = 16; t < 61; t++) w[t] = w[t - 16] + s0(w[t - 15]) + w[t - 7] + s1(w[t - 2]);
    u32 a = IV[0], b = IV[1], c = IV[2], d_ = IV[3], e = IV[4], f = IV[5], g = IV[6], h = IV[7];
    for (int t = 0; t <= 60; t++) {
        u32 t1 = h + S1(e) + ((e & f) ^ (~e & g)) + K[t] + w[t];
        u32 t2 = S0(a) + ((a & b) ^ (a & c) ^ (b & c));
        h = g; g = f; f = e; e = d_ + t1; d_ = c; c = b; b = a; a = t1 + t2;
    }
    return e;
}

static void sha256_bytes(const u8 *msg, size_t len, u8 out[32]) {
    u32 st[8], in[16];
    memcpy(st, IV, 32);
    size_t full = len / 64;
    for (size_t i = 0; i < full; i++) {
        for (int k = 0; k < 16; k++) {
            u32 word; memcpy(&word, msg + i * 64 + (size_t)k * 4, 4);
            in[k] = bswap32(word);
        }
        compress(st, in);
    }
    u8 buf[128];
    size_t rem = len % 64;
    memset(buf, 0, 128);
    memcpy(buf, msg + full * 64, rem);
    buf[rem] = 0x80;
    size_t nb = (rem < 56) ? 1 : 2;
    u64 bits = (u64)len * 8;
    for (int k = 0; k < 8; k++) buf[nb * 64 - 1 - k] = (u8)(bits >> (8 * k));
    for (size_t b = 0; b < nb; b++) {
        for (int k = 0; k < 16; k++) {
            u32 word; memcpy(&word, buf + b * 64 + (size_t)k * 4, 4);
            in[k] = bswap32(word);
        }
        compress(st, in);
    }
    for (int k = 0; k < 8; k++) {
        u32 word = bswap32(st[k]); memcpy(out + (size_t)k * 4, &word, 4);
    }
}

/* ---------- job ---------- */
typedef struct {
    u8 hdr[80];
    u32 mid[8];   /* starea dupa primul bloc de 64 B */
    u32 tail[3];  /* cuvintele 0..2 ale blocului 2 (merkle tail, time, bits) */
    u8 target[32];/* big-endian */
} Job;

typedef struct {
    int found;
    u32 nonce;
    u64 candidates;
} Result;

static int hash_le_target(const Job *j, const u8 h2[32]) {
    for (int i = 0; i < 32; i++) {  /* hash-ul ca numar = digest inversat */
        u8 hb = h2[31 - i];
        if (hb < j->target[i]) return 1;
        if (hb > j->target[i]) return 0;
    }
    return 1;
}

/* Early-exit-ul bazat pe ultimul cuvant SHA-256 este sigur numai daca primii
 * 32 biti ai targetului big-endian sunt zero. Pentru targeturi mai usoare,
 * scan_v1 verifica fiecare digest complet, evitand pierderea share-urilor. */
static int target_requires_zero_top_word(const Job *j) {
    return j->target[0] == 0 && j->target[1] == 0 && j->target[2] == 0 && j->target[3] == 0;
}

static int verify_nonce(const Job *j, u32 nonce) {
    u8 h[80], h1[32], h2[32];
    memcpy(h, j->hdr, 80);
    h[76] = (u8)nonce; h[77] = (u8)(nonce >> 8);
    h[78] = (u8)(nonce >> 16); h[79] = (u8)(nonce >> 24);
    sha256_bytes(h, 80, h1);
    sha256_bytes(h1, 32, h2);
    return hash_le_target(j, h2);
}

static void job_init_header(Job *j, const u8 header[80]) {
    memcpy(j->hdr, header, 80);
    u32 in[16];
    for (int k = 0; k < 16; k++) {
        u32 word; memcpy(&word, j->hdr + (size_t)k * 4, 4);
        in[k] = bswap32(word);
    }
    memcpy(j->mid, IV, 32);
    compress(j->mid, in);
    for (int k = 0; k < 3; k++) {
        u32 word; memcpy(&word, j->hdr + 64 + (size_t)k * 4, 4);
        j->tail[k] = bswap32(word);
    }
    memset(j->target, 0, 32);
}

static void job_init(Job *j, const char *hex) {
    u8 header[80];
    for (int i = 0; i < 80; i++) { unsigned v = 0; sscanf(hex + 2 * i, "%2x", &v); header[i] = (u8)v; }
    job_init_header(j, header);
    u32 bits = (u32)header[72] | ((u32)header[73] << 8) |
               ((u32)header[74] << 16) | ((u32)header[75] << 24);
    int exp = (int)(bits >> 24);
    u32 m = bits & 0x007fffffU;
    if ((bits & 0x00800000U) == 0 && m != 0 && exp >= 3 && exp <= 32) {
        int lsb = 34 - exp;
        j->target[lsb - 2] = (u8)(m >> 16);
        j->target[lsb - 1] = (u8)(m >> 8);
        j->target[lsb] = (u8)m;
    }
}

/* ---------- variante scalare ---------- */
static void scan_v0(const Job *j, u64 start, u64 count, Result *r) {
    for (u64 n = start; n < start + count; n++)
        if (verify_nonce(j, (u32)n)) { r->found = 1; r->nonce = (u32)n; }
}

static void scan_v1(const Job *j, u64 start, u64 count, Result *r) {
    u32 in[16] = {j->tail[0], j->tail[1], j->tail[2], 0, 0x80000000u, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 640};
    for (u64 n = start; n < start + count; n++) {
        in[3] = bswap32((u32)n);
        u32 st[8];
        memcpy(st, j->mid, 32);
        compress(st, in);
        u32 in2[16] = {st[0], st[1], st[2], st[3], st[4], st[5], st[6], st[7], 0x80000000u, 0, 0, 0, 0, 0, 0, 256};
        u32 st2[8];
        memcpy(st2, IV, 32);
        compress(st2, in2);
        if (!target_requires_zero_top_word(j) || st2[7] == 0) {
            r->candidates++;
            if (verify_nonce(j, (u32)n)) { r->found = 1; r->nonce = (u32)n; }
        }
    }
}

static void scan_v2(const Job *j, u64 start, u64 count, Result *r) {
    if (!target_requires_zero_top_word(j)) { scan_v1(j, start, count, r); return; }
    u32 in[16] = {j->tail[0], j->tail[1], j->tail[2], 0, 0x80000000u, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 640};
    for (u64 n = start; n < start + count; n++) {
        in[3] = bswap32((u32)n);
        u32 st[8];
        memcpy(st, j->mid, 32);
        compress(st, in);
        if (second_e60(st) + IV[7] == 0) { r->candidates++; if (verify_nonce(j, (u32)n)) { r->found = 1; r->nonce = (u32)n; } }
    }
}

#if !defined(_MSC_VER)
/* ---------- AVX2, 8 nonce-uri in paralel ---------- */
#define V __m256i
#define VADD _mm256_add_epi32
#define VXOR _mm256_xor_si256
#define VAND _mm256_and_si256
#define VANDN _mm256_andnot_si256
#define VOR _mm256_or_si256
#define VSET1 _mm256_set1_epi32
#define VROR(x, n) VOR(_mm256_srli_epi32(x, n), _mm256_slli_epi32(x, 32 - (n)))
#define VS0(x) VXOR(VXOR(VROR(x, 2), VROR(x, 13)), VROR(x, 22))
#define VS1(x) VXOR(VXOR(VROR(x, 6), VROR(x, 11)), VROR(x, 25))
#define Vs0(x) VXOR(VXOR(VROR(x, 7), VROR(x, 18)), _mm256_srli_epi32(x, 3))
#define Vs1(x) VXOR(VXOR(VROR(x, 17), VROR(x, 19)), _mm256_srli_epi32(x, 10))
#define VCH(e, f, g) VXOR(VAND(e, f), VANDN(e, g))
#define VMAJ(a, b, c) VXOR(VXOR(VAND(a, b), VAND(a, c)), VAND(b, c))
#define VROUND(t, wt)                                                              \
    {                                                                              \
        V t1 = VADD(VADD(VADD(h, VS1(e)), VADD(VCH(e, f, g), VSET1(K[t]))), wt);   \
        V t2 = VADD(VS0(a), VMAJ(a, b, c));                                        \
        h = g; g = f; f = e; e = VADD(d, t1); d = c; c = b; b = a; a = VADD(t1, t2); \
    }

__attribute__((target("avx2")))
static void scan_v3(const Job *j, u64 start, u64 count, Result *r) {
    if (!target_requires_zero_top_word(j)) { scan_v1(j, start, count, r); return; }
    /* primele 3 runde ale blocului 2 nu depind de nonce -> scalar, o singura data */
    u32 p[8];
    memcpy(p, j->mid, 32);
    {
        u32 a = p[0], b = p[1], c = p[2], d = p[3], e = p[4], f = p[5], g = p[6], h = p[7];
        for (int t = 0; t < 3; t++) {
            u32 t1 = h + S1(e) + ((e & f) ^ (~e & g)) + K[t] + j->tail[t];
            u32 t2 = S0(a) + ((a & b) ^ (a & c) ^ (b & c));
            h = g; g = f; f = e; e = d + t1; d = c; c = b; b = a; a = t1 + t2;
        }
        p[0] = a; p[1] = b; p[2] = c; p[3] = d; p[4] = e; p[5] = f; p[6] = g; p[7] = h;
    }
    const V lane = _mm256_setr_epi32(0, 1, 2, 3, 4, 5, 6, 7);
    const V bsw = _mm256_setr_epi8(3, 2, 1, 0, 7, 6, 5, 4, 11, 10, 9, 8, 15, 14, 13, 12,
                                   3, 2, 1, 0, 7, 6, 5, 4, 11, 10, 9, 8, 15, 14, 13, 12);
    const V zero = _mm256_setzero_si256();
    V w[64];
    for (u64 n = start; n + 8 <= start + count; n += 8) {
        /* hash 1, blocul 2 */
        w[0] = VSET1(j->tail[0]); w[1] = VSET1(j->tail[1]); w[2] = VSET1(j->tail[2]);
        w[3] = _mm256_shuffle_epi8(VADD(VSET1((u32)n), lane), bsw);
        w[4] = VSET1(0x80000000u);
        for (int i = 5; i < 15; i++) w[i] = zero;
        w[15] = VSET1(640);
        for (int t = 16; t < 64; t++) w[t] = VADD(VADD(w[t - 16], Vs0(w[t - 15])), VADD(w[t - 7], Vs1(w[t - 2])));
        V a = VSET1(p[0]), b = VSET1(p[1]), c = VSET1(p[2]), d = VSET1(p[3]);
        V e = VSET1(p[4]), f = VSET1(p[5]), g = VSET1(p[6]), h = VSET1(p[7]);
        for (int t = 3; t < 64; t++) VROUND(t, w[t]);
        V dg[8] = {VADD(a, VSET1(j->mid[0])), VADD(b, VSET1(j->mid[1])), VADD(c, VSET1(j->mid[2])), VADD(d, VSET1(j->mid[3])),
                   VADD(e, VSET1(j->mid[4])), VADD(f, VSET1(j->mid[5])), VADD(g, VSET1(j->mid[6])), VADD(h, VSET1(j->mid[7]))};
        /* hash 2, oprit la runda 60 */
        for (int i = 0; i < 8; i++) w[i] = dg[i];
        w[8] = VSET1(0x80000000u);
        for (int i = 9; i < 15; i++) w[i] = zero;
        w[15] = VSET1(256);
        for (int t = 16; t < 61; t++) w[t] = VADD(VADD(w[t - 16], Vs0(w[t - 15])), VADD(w[t - 7], Vs1(w[t - 2])));
        a = VSET1(IV[0]); b = VSET1(IV[1]); c = VSET1(IV[2]); d = VSET1(IV[3]);
        e = VSET1(IV[4]); f = VSET1(IV[5]); g = VSET1(IV[6]); h = VSET1(IV[7]);
        for (int t = 0; t <= 60; t++) VROUND(t, w[t]);
        V m = _mm256_cmpeq_epi32(VADD(e, VSET1(IV[7])), zero);
        int mask = _mm256_movemask_ps(_mm256_castsi256_ps(m));
        while (mask) {
            int l = (int)ctz32((u32)mask);
            mask &= mask - 1;
            r->candidates++;
            if (verify_nonce(j, (u32)(n + l))) { r->found = 1; r->nonce = (u32)(n + l); }
        }
    }
    u64 end = start + count;
    u64 tail_start = start + ((count / 8) * 8);
    if (tail_start < end) scan_v1(j, tail_start, end - tail_start, r);
}


/* ---------- AVX-512, 16 nonce-uri in paralel (rotate nativ + ternary logic) ---------- */
#define Z __m512i
#define ZADD _mm512_add_epi32
#define ZSET1 _mm512_set1_epi32
#define ZROR _mm512_ror_epi32
#define ZX3(a, b, c) _mm512_ternarylogic_epi32(a, b, c, 0x96)
#define ZS0(x) ZX3(ZROR(x, 2), ZROR(x, 13), ZROR(x, 22))
#define ZS1(x) ZX3(ZROR(x, 6), ZROR(x, 11), ZROR(x, 25))
#define Zs0(x) ZX3(ZROR(x, 7), ZROR(x, 18), _mm512_srli_epi32(x, 3))
#define Zs1(x) ZX3(ZROR(x, 17), ZROR(x, 19), _mm512_srli_epi32(x, 10))
#define ZCH(e, f, g) _mm512_ternarylogic_epi32(e, f, g, 0xCA)
#define ZMAJ(a, b, c) _mm512_ternarylogic_epi32(a, b, c, 0xE8)
#define ZROUND(t, wt)                                                              \
    {                                                                              \
        Z t1 = ZADD(ZADD(ZADD(h, ZS1(e)), ZADD(ZCH(e, f, g), ZSET1(K[t]))), wt);   \
        Z t2 = ZADD(ZS0(a), ZMAJ(a, b, c));                                        \
        h = g; g = f; f = e; e = ZADD(d, t1); d = c; c = b; b = a; a = ZADD(t1, t2); \
    }

__attribute__((target("avx512f")))
static void scan_v4(const Job *j, u64 start, u64 count, Result *r) {
    if (!target_requires_zero_top_word(j)) { scan_v1(j, start, count, r); return; }
    u32 p[8];
    memcpy(p, j->mid, 32);
    {
        u32 a = p[0], b = p[1], c = p[2], d = p[3], e = p[4], f = p[5], g = p[6], h = p[7];
        for (int t = 0; t < 3; t++) {
            u32 t1 = h + S1(e) + ((e & f) ^ (~e & g)) + K[t] + j->tail[t];
            u32 t2 = S0(a) + ((a & b) ^ (a & c) ^ (b & c));
            h = g; g = f; f = e; e = d + t1; d = c; c = b; b = a; a = t1 + t2;
        }
        p[0] = a; p[1] = b; p[2] = c; p[3] = d; p[4] = e; p[5] = f; p[6] = g; p[7] = h;
    }
    const Z zero = _mm512_setzero_si512();
    Z w[64];
    u32 tmp[16];
    for (u64 n = start; n + 16 <= start + count; n += 16) {
        w[0] = ZSET1(j->tail[0]); w[1] = ZSET1(j->tail[1]); w[2] = ZSET1(j->tail[2]);
        for (int l = 0; l < 16; l++) tmp[l] = bswap32((u32)(n + l));
        w[3] = _mm512_loadu_si512(tmp);
        w[4] = ZSET1(0x80000000u);
        for (int i = 5; i < 15; i++) w[i] = zero;
        w[15] = ZSET1(640);
        for (int t = 16; t < 64; t++) w[t] = ZADD(ZADD(w[t - 16], Zs0(w[t - 15])), ZADD(w[t - 7], Zs1(w[t - 2])));
        Z a = ZSET1(p[0]), b = ZSET1(p[1]), c = ZSET1(p[2]), d = ZSET1(p[3]);
        Z e = ZSET1(p[4]), f = ZSET1(p[5]), g = ZSET1(p[6]), h = ZSET1(p[7]);
        for (int t = 3; t < 64; t++) ZROUND(t, w[t]);
        Z dg[8] = {ZADD(a, ZSET1(j->mid[0])), ZADD(b, ZSET1(j->mid[1])), ZADD(c, ZSET1(j->mid[2])), ZADD(d, ZSET1(j->mid[3])),
                   ZADD(e, ZSET1(j->mid[4])), ZADD(f, ZSET1(j->mid[5])), ZADD(g, ZSET1(j->mid[6])), ZADD(h, ZSET1(j->mid[7]))};
        for (int i = 0; i < 8; i++) w[i] = dg[i];
        w[8] = ZSET1(0x80000000u);
        for (int i = 9; i < 15; i++) w[i] = zero;
        w[15] = ZSET1(256);
        for (int t = 16; t < 61; t++) w[t] = ZADD(ZADD(w[t - 16], Zs0(w[t - 15])), ZADD(w[t - 7], Zs1(w[t - 2])));
        a = ZSET1(IV[0]); b = ZSET1(IV[1]); c = ZSET1(IV[2]); d = ZSET1(IV[3]);
        e = ZSET1(IV[4]); f = ZSET1(IV[5]); g = ZSET1(IV[6]); h = ZSET1(IV[7]);
        for (int t = 0; t <= 60; t++) ZROUND(t, w[t]);
        unsigned mask = _mm512_cmpeq_epi32_mask(ZADD(e, ZSET1(IV[7])), zero);
        while (mask) {
            int l = __builtin_ctz(mask);
            mask &= mask - 1;
            r->candidates++;
            if (verify_nonce(j, (u32)(n + l))) { r->found = 1; r->nonce = (u32)(n + l); }
        }
    }
    u64 end = start + count;
    u64 tail_start = start + ((count / 16) * 16);
    if (tail_start < end) scan_v1(j, tail_start, end - tail_start, r);
}
#else
/* MSVC first-stage backend: scalar/midstate code is native; SIMD remains disabled
 * until separately compiled ISA translation units are added and CPUID-tested. */
static void scan_v3(const Job *j, u64 start, u64 count, Result *r) {
    scan_v1(j, start, count, r);
}
static void scan_v4(const Job *j, u64 start, u64 count, Result *r) {
    scan_v1(j, start, count, r);
}
#endif

typedef void (*scan_fn)(const Job *, u64, u64, Result *);
static scan_fn VARIANTS[5] = {scan_v0, scan_v1, scan_v2, scan_v3, scan_v4};
static const char *NAMES[5] = {"0 naiv (2x SHA complet)", "1 midstate", "2 midstate + early exit", "3 AVX2 x8 + precalc + early", "4 AVX-512 x16 (daca CPU-ul il are)"};

typedef struct { const Job *j; u64 start, count; int v; Result res; } Task;
#if defined(_WIN32)
static DWORD WINAPI worker(LPVOID p) {
    Task *t = (Task *)p;
    VARIANTS[t->v](t->j, t->start, t->count, &t->res);
    return 0;
}
#else
static void *worker(void *p) {
    Task *t = (Task *)p;
    VARIANTS[t->v](t->j, t->start, t->count, &t->res);
    return NULL;
}
#endif

static double now(void) {
#if defined(_WIN32)
    LARGE_INTEGER counter, frequency;
    if (!QueryPerformanceFrequency(&frequency) || frequency.QuadPart <= 0)
        return 0.0;
    QueryPerformanceCounter(&counter);
    return (double)counter.QuadPart / (double)frequency.QuadPart;
#else
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return ts.tv_sec + ts.tv_nsec * 1e-9;
#endif
}

static double run(const Job *j, int v, int threads, u64 start, u64 total, Result *out) {
#if defined(_WIN32)
    HANDLE th[256];
#else
    pthread_t th[256];
#endif
    Task tk[256];
    int launched[256] = {0};
    u64 base = total / (u64)threads;
    u64 rem = total % (u64)threads;
    u64 offset = 0;
    double t0 = now();
    memset(out, 0, sizeof *out);
    for (int i = 0; i < threads; i++) {
        u64 count = base + ((u64)i < rem ? 1ULL : 0ULL);
        tk[i].j = j;
        tk[i].start = start + offset;
        tk[i].count = count;
        tk[i].v = v;
        memset(&tk[i].res, 0, sizeof(tk[i].res));
        offset += count;
        if (count == 0) continue;
#if defined(_WIN32)
        th[i] = CreateThread(NULL, 0, worker, &tk[i], 0, NULL);
        if (th[i]) launched[i] = 1;
        else worker(&tk[i]); /* fallback sigur: nu pierdem segmentul daca CreateThread esueaza */
#else
        int rc = pthread_create(&th[i], NULL, worker, &tk[i]);
        if (rc == 0) launched[i] = 1;
        else worker(&tk[i]); /* fallback sigur: nu pierdem segmentul daca pthread_create esueaza */
#endif
    }
    for (int i = 0; i < threads; i++) {
#if defined(_WIN32)
        if (launched[i]) {
            WaitForSingleObject(th[i], INFINITE);
            CloseHandle(th[i]);
        }
#else
        if (launched[i]) pthread_join(th[i], NULL);
#endif
        out->candidates += tk[i].res.candidates;
        if (tk[i].res.found) { out->found = 1; out->nonce = tk[i].res.nonce; }
    }
    double dt = now() - t0;
    return dt > 0.0 ? (double)total / dt / 1e6 : 0.0; /* MH/s */
}

static int cpu_has_avx2(void) {
#if defined(_MSC_VER)
    return 0; /* MSVC build currently compiles the portable scalar backends only. */
#elif defined(__GNUC__) || defined(__clang__)
    __builtin_cpu_init();
    return __builtin_cpu_supports("avx2");
#else
    return 0;
#endif
}
static int cpu_has_avx512(void) {
#if defined(_MSC_VER)
    return 0; /* AVX-512 remains a separately validated compiler backend. */
#elif defined(__GNUC__) || defined(__clang__)
    __builtin_cpu_init();
    return __builtin_cpu_supports("avx512f");
#else
    return 0;
#endif
}

/* API C ABI pentru integrarea NEXUS/Stratum. header=80 bytes; target=32 bytes BE. */
NEXUS_EXPORT int nexus_variant_supported(int variant) {
    if (variant < 0 || variant > 4) return 0;
    if (variant == 3) return cpu_has_avx2();
    if (variant == 4) return cpu_has_avx512();
    return 1;
}

NEXUS_EXPORT int nexus_scan_range(const u8 *header, const u8 *target_be, u32 start_nonce,
                     u64 count, int variant, int threads, u32 *nonce_out,
                     u64 *checked_out, double *hashrate_mhs_out) {
    if (!header || !target_be || !nonce_out || !checked_out || !hashrate_mhs_out) return -1;
    if (variant < 0 || variant > 4 || threads < 1 || threads > 256 || count < 1) return -2;
    if ((u64)start_nonce + count > 0x100000000ULL) return -3;
    if (!nexus_variant_supported(variant)) return -4;
    Job j; job_init_header(&j, header);
    memcpy(j.target, target_be, 32);
    Result result;
    double rate = run(&j, variant, threads, start_nonce, count, &result);
    *nonce_out = result.found ? result.nonce : 0;
    *checked_out = count;
    *hashrate_mhs_out = rate;
    return result.found ? 1 : 0;
}

/* antetul real al blocului genesis Bitcoin; nonce-ul corect: 2083236893 */
static const char *GENESIS =
    "0100000000000000000000000000000000000000000000000000000000000000000000003ba3edfd7a7b12b27ac72c3e67768f617fc81bc3888a51323a9fb8aa4b1e5e4a29ab5f49ffff001d1dac2b7c";
#define GENESIS_NONCE 2083236893u

#ifndef NEXUS_LIBRARY
int main(int argc, char **argv) {
    if (argc < 2) { fprintf(stderr, "uz: %s bench [N] | run <v> <threads> <N>\n", argv[0]); return 1; }
    if (!cpu_has_avx2()) printf("INFO: AVX2 indisponibil; varianta 3 este dezactivata.\n");
    Job j;
    job_init(&j, GENESIS);
    u64 start = GENESIS_NONCE - 1000000ULL;
    if (!strcmp(argv[1], "bench")) {
        u64 N = 20000000ULL;
        if (argc > 2) {
            char *end = NULL; errno = 0;
            unsigned long long parsed = strtoull(argv[2], &end, 10);
            if (errno || !end || end == argv[2] || *end || argv[2][0] == '-') {
                fprintf(stderr, "N invalid.\n"); return 2;
            }
            N = (u64)parsed;
        }
        if (N == 0 || N > (0x100000000ULL - start)) { fprintf(stderr, "N invalid: intervalul trebuie sa ramana in uint32.\n"); return 2; }
        printf("CPU dispatch: AVX2=%s AVX512F=%s\n", cpu_has_avx2() ? "yes" : "no", cpu_has_avx512() ? "yes" : "no");
        printf("Fereastra: %llu nonce-uri in jurul nonce-ului real al blocului genesis (%u)\n\n", (unsigned long long)N, GENESIS_NONCE);
        printf("%-34s %10s  %s\n", "varianta (1 thread)", "MH/s", "validare");
        double base = 0;
        for (int v = 0; v < 5; v++) {
            if ((v == 3 && !cpu_has_avx2()) || (v == 4 && !cpu_has_avx512())) { printf("%-34s %10s\n", NAMES[v], "indisponibil pe acest CPU"); continue; }
            u64 n = (v == 0 && N > 3000000ULL) ? 3000000ULL : N;  /* v0 e lenta */
            Result r;
            double mh = run(&j, v, 1, start, n, &r);
            if (v == 0) base = mh;
            printf("%-34s %10.2f  %s (x%.2f fata de naiv)\n", NAMES[v], mh,
                   r.found && r.nonce == GENESIS_NONCE ? "OK: a gasit nonce-ul genesis" : "NU a gasit nonce-ul!", mh / base);
        }
    } else if (!strcmp(argv[1], "run") && argc >= 5) {
        char *e1 = NULL, *e2 = NULL, *e3 = NULL;
        long v = strtol(argv[2], &e1, 10), th = strtol(argv[3], &e2, 10);
        unsigned long long N = strtoull(argv[4], &e3, 10);
        if (!e1 || *e1 || !e2 || *e2 || !e3 || *e3 || v < 0 || v > 4 || th < 1 || th > 256 || N == 0 || start + (u64)N > 0x100000000ULL) {
            fprintf(stderr, "Parametri invalizi: variant 0..4, threads 1..256, N>0 si interval uint32 valid.\n"); return 2;
        }
        if (!nexus_variant_supported((int)v)) { fprintf(stderr, "Varianta SIMD solicitata nu este suportata de CPU.\n"); return 3; }
        Result r;
        double mh = run(&j, (int)v, (int)th, start, (u64)N, &r);
        printf("%s, %ld thread-uri: %.2f MH/s, found=%d nonce=%u\n", NAMES[v], th, mh, r.found, r.nonce);
    } else {
        fprintf(stderr, "Comanda invalida. Folosire: %s bench [N] | run <v> <threads> <N>\n", argv[0]); return 2;
    }
    return 0;
}
#endif
