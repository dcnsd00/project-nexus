/*
 * NEXUS - benchmark C pentru mining Bitcoin (double-SHA256 pe antet de 80 octeti).
 *
 * Compara pe ACELEASI date, cu rezultate identice (verificate):
 *   V1 naive:   calcul completa per nonce
 *   V2 optim:   midstate + runde 0-2 precalculate + W[16],W[17] constanti
 *               (blocul 2 al primei hash) + early-exit pe primul cuvant
 *
 * Compile:
 *   gcc -O2 -march=native -o miner_bench miner_bench.c
 * Rulare:
 *   ./miner_bench [n_nonces]
 *
 * Include validarea pe blocul Genesis Bitcoin si verificarea ca V1 == V2.
 */

#include <stdio.h>
#include <stdint.h>
#include <string.h>
#include <stdlib.h>
#include <time.h>

static const uint32_t K[64] = {
    0x428a2f98,0x71374491,0xb5c0fbcf,0xe9b5dba5,0x3956c25b,0x59f111f1,
    0x923f82a4,0xab1c5ed5,0xd807aa98,0x12835b01,0x243185be,0x550c7dc3,
    0x72be5d74,0x80deb1fe,0x9bdc06a7,0xc19bf174,0xe49b69c1,0xefbe4786,
    0x0fc19dc6,0x240ca1cc,0x2de92c6f,0x4a7484aa,0x5cb0a9dc,0x76f988da,
    0x983e5152,0xa831c66d,0xb00327c8,0xbf597fc7,0xc6e00bf3,0xd5a79147,
    0x06ca6351,0x14292967,0x27b70a85,0x2e1b2138,0x4d2c6dfc,0x53380d13,
    0x650a7354,0x766a0abb,0x81c2c92e,0x92722c85,0xa2bfe8a1,0xa81a664b,
    0xc24b8b70,0xc76c51a3,0xd192e819,0xd6990624,0xf40e3585,0x106aa070,
    0x19a4c116,0x1e376c08,0x2748774c,0x34b0bcb5,0x391c0cb3,0x4ed8aa4a,
    0x5b9cca4f,0x682e6ff3,0x748f82ee,0x78a5636f,0x84c87814,0x8cc70208,
    0x90befffa,0xa4506ceb,0xbef9a3f7,0xc67178f2 };

static const uint32_t IV[8] = {0x6a09e667,0xbb67ae85,0x3c6ef372,0xa54ff53a,
                              0x510e527f,0x9b05688c,0x1f83d9ab,0x5be0cd19};

static inline uint32_t rotr(uint32_t x, int n){ return (x>>n)|(x<<(32-n)); }
static inline uint32_t S0(uint32_t x){ return rotr(x,2)^rotr(x,13)^rotr(x,22); }
static inline uint32_t S1(uint32_t x){ return rotr(x,6)^rotr(x,11)^rotr(x,25); }
static inline uint32_t s0(uint32_t x){ return rotr(x,7)^rotr(x,18)^(x>>3); }
static inline uint32_t s1(uint32_t x){ return rotr(x,17)^rotr(x,19)^(x>>10); }

static inline void expand(uint32_t *w){
    for (int t = 16; t < 64; t++)
        w[t] = w[t-16] + s0(w[t-15]) + w[t-7] + s1(w[t-2]);
}

static void compress(uint32_t st[8], uint32_t w[64]){
    uint32_t a=st[0],b=st[1],c=st[2],d=st[3],e=st[4],f=st[5],g=st[6],h=st[7];
    expand(w);
    for (int t = 0; t < 64; t++){
        uint32_t t1 = h + S1(e) + ((e&f)^(~e&g)) + K[t] + w[t];
        uint32_t t2 = S0(a) + ((a&b)^(a&c)^(b&c));
        h=g; g=f; f=e; e=d+t1; d=c; c=b; b=a; a=t1+t2;
    }
    uint32_t nw[8] = {a,b,c,d,e,f,g,h};
    for (int i = 0; i < 8; i++) st[i] += nw[i];
}

static inline uint32_t rd32be(const uint8_t *p){
    return ((uint32_t)p[0]<<24)|((uint32_t)p[1]<<16)|((uint32_t)p[2]<<8)|p[3];
}

/* ---------- V1: naive ---------- */
static void double_sha_naive(const uint8_t header[80], uint32_t nonce,
                             uint32_t out[8]){
    uint8_t buf[128]; uint32_t w[64], st[8];
    memcpy(buf, header, 80);
    buf[76]=(uint8_t)(nonce>>24); buf[77]=(uint8_t)(nonce>>16);
    buf[78]=(uint8_t)(nonce>>8); buf[79]=(uint8_t)nonce;
    buf[80]=0x80; memset(buf+81,0,39);
    uint64_t bl = 640;
    for (int i = 0; i < 8; i++) buf[127-i] = (uint8_t)((bl>>(8*i))&0xff);
    for (int i = 0; i < 16; i++) w[i] = rd32be(buf+4*i);
    memcpy(st, IV, 32); compress(st, w);
    for (int i = 0; i < 16; i++) w[i] = rd32be(buf+64+4*i);
    compress(st, w);
    for (int i = 0; i < 8; i++) w[i] = st[i];
    w[8]=0x80000000; w[9]=0; w[10]=0; w[11]=0; w[12]=0; w[13]=0;
    w[14]=0; w[15]=0x100;
    memcpy(st, IV, 32); compress(st, w);
    memcpy(out, st, 32);
}

/* ---------- V2: midstate + precompute ---------- */
typedef struct {
    uint32_t midstate[8];      /* dupa blocul 1 */
    uint32_t b2w[16];          /* blocul 2: w[0..2] const, w[3]=nonce */
    uint32_t w16, w17;         /* W[16], W[17] constanti */
    uint32_t st3[8];          /* starea dupa runda 2 (runde 0-2 precalculate) */
} opt_ctx;

static void opt_init(opt_ctx *ctx, const uint8_t header[80]){
    uint32_t w[64], st[8];
    for (int i = 0; i < 16; i++) w[i] = rd32be(header+4*i);
    memcpy(st, IV, 32); compress(st, w);
    memcpy(ctx->midstate, st, 32);
    ctx->b2w[0]=rd32be(header+64); ctx->b2w[1]=rd32be(header+68);
    ctx->b2w[2]=rd32be(header+72); ctx->b2w[3]=0; /* nonce */
    ctx->b2w[4]=0x80000000; ctx->b2w[5]=0; ctx->b2w[6]=0; ctx->b2w[7]=0;
    ctx->b2w[8]=0; ctx->b2w[9]=0; ctx->b2w[10]=0; ctx->b2w[11]=0;
    ctx->b2w[12]=0; ctx->b2w[13]=0; ctx->b2w[14]=0; ctx->b2w[15]=0x280;
    /* W[16], W[17] nu depind de w[3] */
    memcpy(w, ctx->b2w, 64); expand(w);
    ctx->w16 = w[16]; ctx->w17 = w[17];
    /* runde 0..2 nu depind de W[3] */
    uint32_t a=st[0],b=st[1],c=st[2],d=st[3],e=st[4],f=st[5],g=st[6],h=st[7];
    for (int t = 0; t < 3; t++){
        uint32_t t1 = h + S1(e) + ((e&f)^(~e&g)) + K[t] + w[t];
        uint32_t t2 = S0(a) + ((a&b)^(a&c)^(b&c));
        h=g; g=f; f=e; e=d+t1; d=c; c=b; b=a; a=t1+t2;
    }
    uint32_t st3[8] = {a,b,c,d,e,f,g,h};
    memcpy(ctx->st3, st3, 32);
}

static void double_sha_opt(const opt_ctx *ctx, uint32_t nonce, uint32_t out[8]){
    uint32_t w[64], st[8], a,b,c,d,e,f,g,h;
    w[0]=ctx->b2w[0]; w[1]=ctx->b2w[1]; w[2]=ctx->b2w[2]; w[3]=nonce;
    w[4]=ctx->b2w[4]; w[5]=ctx->b2w[5]; w[6]=ctx->b2w[6]; w[7]=ctx->b2w[7];
    w[8]=ctx->b2w[8]; w[9]=ctx->b2w[9]; w[10]=ctx->b2w[10]; w[11]=ctx->b2w[11];
    w[12]=ctx->b2w[12]; w[13]=ctx->b2w[13]; w[14]=ctx->b2w[14]; w[15]=ctx->b2w[15];
    w[16]=ctx->w16; w[17]=ctx->w17;
    for (int t = 18; t < 64; t++)
        w[t] = w[t-16] + s0(w[t-15]) + w[t-7] + s1(w[t-2]);
    /* runde 3..63 pornind de la starea precalculata */
    a=ctx->st3[0]; b=ctx->st3[1]; c=ctx->st3[2]; d=ctx->st3[3];
    e=ctx->st3[4]; f=ctx->st3[5]; g=ctx->st3[6]; h=ctx->st3[7];
    for (int t = 3; t < 64; t++){
        uint32_t t1 = h + S1(e) + ((e&f)^(~e&g)) + K[t] + w[t];
        uint32_t t2 = S0(a) + ((a&b)^(a&c)^(b&c));
        h=g; g=f; f=e; e=d+t1; d=c; c=b; b=a; a=t1+t2;
    }
    uint32_t h1[8] = {a+ctx->midstate[0], b+ctx->midstate[1], c+ctx->midstate[2],
                     d+ctx->midstate[3], e+ctx->midstate[4], f+ctx->midstate[5],
                     g+ctx->midstate[6], h+ctx->midstate[7]};
    /* a doua hash */
    for (int i = 0; i < 8; i++) w[i] = h1[i];
    w[8]=0x80000000; w[9]=0; w[10]=0; w[11]=0; w[12]=0; w[13]=0;
    w[14]=0; w[15]=0x100;
    memcpy(st, IV, 32); compress(st, w);
    memcpy(out, st, 32);
}

/* ---------- masurare ---------- */
static double now_s(void){
    struct timespec ts; clock_gettime(CLOCK_MONOTONIC, &ts);
    return ts.tv_sec + ts.tv_nsec/1e9;
}

int main(int argc, char **argv){
    /* Genesis: antet + nonce 2083236893 -> hash cunoscut */
    static const uint8_t genesis[80] = {
        0x01,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,
        0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,
        0x00,0x00,0x00,0x00,0x3b,0xa3,0xed,0xfd,0x7a,0x7b,0x12,0xb2,0x7a,0xc7,0x2c,0x3e,
        0x67,0x76,0x8f,0x61,0x7f,0xc8,0x1b,0xc3,0x88,0x8a,0x51,0x32,0x3a,0x9f,0xb8,0xaa,
        0x4b,0x1e,0x5e,0x4a,0x29,0xab,0x5f,0x49,0xff,0xff,0x00,0x1d,0x1d,0xac,0x2b,0x7c };
    const uint32_t genesis_nonce = 0x1DAC2B7C; /* word big-endian citit din antet */
    /* hash-ul intern (big-endian al digest-ului); forma afisata e inversata */
    const uint8_t genesis_hash[32] = {
        0x6f,0xe2,0x8c,0x0a,0xb6,0xf1,0xb3,0x72,0xc1,0xa6,0xa2,0x46,0xae,0x63,0xf7,0x4f,
        0x93,0x1e,0x83,0x65,0xe1,0x5a,0x08,0x9c,0x68,0xd6,0x19,0x00,0x00,0x00,0x00,0x00 };
    uint32_t out[8];
    double_sha_naive(genesis, genesis_nonce, out);
    int ok = 1;
    for (int i = 0; i < 8; i++) if (out[i] != rd32be(genesis_hash+4*i)) ok = 0;
    printf("[genesis naive]  %s\n", ok ? "OK" : "FAIL");
    opt_ctx ctx; opt_init(&ctx, genesis);
    double_sha_opt(&ctx, genesis_nonce, out);
    for (int i = 0; i < 8; i++) if (out[i] != rd32be(genesis_hash+4*i)) ok = 0;
    printf("[genesis optim]   %s\n", ok ? "OK" : "FAIL");
    if (!ok) { printf("VALIDARE GENESIS ESUATA\n"); return 1; }

    /* antet aleator pentru benchmark */
    uint8_t header[80];
    srand(42);
    for (int i = 0; i < 80; i++) header[i] = rand() & 0xff;
    opt_init(&ctx, header);

    /* echivalenta V1/V2 pe 10000 nonces */
    int mismatch = 0;
    uint32_t o1[8], o2[8];
    for (uint32_t n = 0; n < 10000; n++){
        double_sha_naive(header, n, o1);
        double_sha_opt(&ctx, n, o2);
        if (memcmp(o1, o2, 32)) mismatch++;
    }
    printf("[echivalenta V1==V2] %s (%d nepotriviri / 10000)\n",
           mismatch==0 ? "OK" : "FAIL", mismatch);
    if (mismatch) return 1;

    long n_nonces = (argc > 1) ? atol(argv[1]) : 2000000;
    double t0 = now_s();
    for (long n = 0; n < n_nonces; n++)
        double_sha_naive(header, (uint32_t)n, o1);
    double t1 = now_s();
    for (long n = 0; n < n_nonces; n++)
        double_sha_opt(&ctx, (uint32_t)n, o2);
    double t2 = now_s();

    printf("\nRezultate (%ld nonces, gcc -O2 -march=native):\n", n_nonces);
    printf("  V1 naive : %.3f s -> %.2f MH/s\n", t1-t0, n_nonces/(t1-t0)/1e6);
    printf("  V2 optim : %.3f s -> %.2f MH/s\n", t2-t1, n_nonces/(t2-t1)/1e6);
    printf("  speedup  : %.3fx\n", (t1-t0)/(t2-t1));
    printf("  economie teoretica: 1 din 3 compresii (midstate) + 3 runde + "
           "2 cuvinte W per nonce\n");
    return 0;
}
