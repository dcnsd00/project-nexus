// MULTIMINER X v0.2.0 - SHA-256d header benchmark / regtest-style PoW simulator
// Educational reference implementation. It does NOT connect to Bitcoin mainnet or a pool.
// Build: g++ -O3 -march=native -std=c++17 src/btc_sha256d.cpp -o mmx_btc -pthread

#include <array>
#include <atomic>
#include <chrono>
#include <cstdint>
#include <cstring>
#include <iomanip>
#include <iostream>
#include <mutex>
#include <sstream>
#include <string>
#include <thread>
#include <vector>
#include <algorithm>
#include <stdexcept>

using U32 = uint32_t;
using U64 = uint64_t;
using State = std::array<U32, 8>;
using Block = std::array<U32, 16>;
using Header = std::array<uint8_t, 80>;
using Digest = std::array<uint8_t, 32>;

static constexpr U32 IV[8] = {
    0x6a09e667u, 0xbb67ae85u, 0x3c6ef372u, 0xa54ff53au,
    0x510e527fu, 0x9b05688cu, 0x1f83d9abu, 0x5be0cd19u
};
static constexpr U32 K[64] = {
  0x428a2f98u,0x71374491u,0xb5c0fbcfu,0xe9b5dba5u,0x3956c25bu,0x59f111f1u,0x923f82a4u,0xab1c5ed5u,
  0xd807aa98u,0x12835b01u,0x243185beu,0x550c7dc3u,0x72be5d74u,0x80deb1feu,0x9bdc06a7u,0xc19bf174u,
  0xe49b69c1u,0xefbe4786u,0x0fc19dc6u,0x240ca1ccu,0x2de92c6fu,0x4a7484aau,0x5cb0a9dcu,0x76f988dau,
  0x983e5152u,0xa831c66du,0xb00327c8u,0xbf597fc7u,0xc6e00bf3u,0xd5a79147u,0x06ca6351u,0x14292967u,
  0x27b70a85u,0x2e1b2138u,0x4d2c6dfcu,0x53380d13u,0x650a7354u,0x766a0abbu,0x81c2c92eu,0x92722c85u,
  0xa2bfe8a1u,0xa81a664bu,0xc24b8b70u,0xc76c51a3u,0xd192e819u,0xd6990624u,0xf40e3585u,0x106aa070u,
  0x19a4c116u,0x1e376c08u,0x2748774cu,0x34b0bcb5u,0x391c0cb3u,0x4ed8aa4au,0x5b9cca4fu,0x682e6ff3u,
  0x748f82eeu,0x78a5636fu,0x84c87814u,0x8cc70208u,0x90befffau,0xa4506cebu,0xbef9a3f7u,0xc67178f2u
};

static inline U32 rotr(U32 x, unsigned n) { return (x >> n) | (x << (32 - n)); }
static inline U32 Ch(U32 x,U32 y,U32 z) { return (x & y) ^ (~x & z); }
static inline U32 Maj(U32 x,U32 y,U32 z) { return (x & y) ^ (x & z) ^ (y & z); }
static inline U32 BS0(U32 x) { return rotr(x,2) ^ rotr(x,13) ^ rotr(x,22); }
static inline U32 BS1(U32 x) { return rotr(x,6) ^ rotr(x,11) ^ rotr(x,25); }
static inline U32 SS0(U32 x) { return rotr(x,7) ^ rotr(x,18) ^ (x >> 3); }
static inline U32 SS1(U32 x) { return rotr(x,17) ^ rotr(x,19) ^ (x >> 10); }
static inline U32 load_be32(const uint8_t* p) {
    return (U32(p[0]) << 24) | (U32(p[1]) << 16) | (U32(p[2]) << 8) | U32(p[3]);
}
static inline U32 load_le32(const uint8_t* p) {
    return U32(p[0]) | (U32(p[1]) << 8) | (U32(p[2]) << 16) | (U32(p[3]) << 24);
}
static inline U32 bswap32(U32 x) {
    return (x >> 24) | ((x >> 8) & 0x0000ff00u) | ((x << 8) & 0x00ff0000u) | (x << 24);
}
static inline void store_be32(uint8_t* p, U32 x) {
    p[0] = uint8_t(x >> 24); p[1] = uint8_t(x >> 16); p[2] = uint8_t(x >> 8); p[3] = uint8_t(x);
}
static inline void store_le32(uint8_t* p, U32 x) {
    p[0] = uint8_t(x); p[1] = uint8_t(x >> 8); p[2] = uint8_t(x >> 16); p[3] = uint8_t(x >> 24);
}

static Block parse_block(const uint8_t* p) {
    Block w{};
    for (int i=0;i<16;i++) w[i] = load_be32(p + 4*i);
    return w;
}

static void compress(State& s, const Block& in) {
    U32 w[64];
    for (int i=0;i<16;i++) w[i] = in[i];
    for (int i=16;i<64;i++) w[i] = SS1(w[i-2]) + w[i-7] + SS0(w[i-15]) + w[i-16];

    U32 a=s[0], b=s[1], c=s[2], d=s[3], e=s[4], f=s[5], g=s[6], h=s[7];
    for (int i=0;i<64;i++) {
        const U32 t1 = h + BS1(e) + Ch(e,f,g) + K[i] + w[i];
        const U32 t2 = BS0(a) + Maj(a,b,c);
        h=g; g=f; f=e; e=d+t1; d=c; c=b; b=a; a=t1+t2;
    }
    s[0]+=a; s[1]+=b; s[2]+=c; s[3]+=d;
    s[4]+=e; s[5]+=f; s[6]+=g; s[7]+=h;
}

struct PreparedJob {
    State midstate{};
    Block block1_template{}; // bytes 64..75 predecoded; word 3 is the nonce
    Header header_template{};
};

static PreparedJob prepare_job(const Header& header) {
    PreparedJob job{};
    job.header_template=header;
    std::copy(std::begin(IV), std::end(IV), job.midstate.begin());
    compress(job.midstate, parse_block(header.data())); // first 64 bytes, once per job
    for (int i=0;i<3;i++) job.block1_template[i]=load_be32(header.data()+64+4*i);
    job.block1_template[4]=0x80000000u;
    job.block1_template[15]=640u; // 80-byte header * 8 bits
    return job;
}

// Return the final 8-word SHA-256d state without serializing it to 32 digest bytes.
// This lets the PoW target comparator inspect the state directly on misses.
static State sha256d_state_for_nonce(const PreparedJob& job, U32 nonce) {
    Block b1=job.block1_template;
    b1[3]=bswap32(nonce); // nonce is serialized little-endian in the 80-byte header
    State first=job.midstate;
    compress(first,b1);

    Block b2{};
    for (int i=0;i<8;i++) b2[i]=first[i];
    b2[8]=0x80000000u;
    b2[15]=256u; // first digest is 32 bytes
    State second; std::copy(std::begin(IV),std::end(IV),second.begin());
    compress(second,b2);
    return second;
}

static Digest digest_from_state(const State& state) {
    Digest out{};
    for (int i=0;i<8;i++) store_be32(out.data()+4*i,state[i]);
    return out;
}

static Digest sha256d_from_prepared_job(const PreparedJob& job, U32 nonce) {
    return digest_from_state(sha256d_state_for_nonce(job,nonce));
}

static Digest sha256_full(const uint8_t* msg, size_t len) {
    State s; std::copy(std::begin(IV), std::end(IV), s.begin());
    size_t off=0;
    while (len-off >= 64) { compress(s, parse_block(msg+off)); off += 64; }
    uint8_t tail[128]{};
    size_t rem=len-off;
    if (rem) std::memcpy(tail,msg+off,rem);
    tail[rem]=0x80;
    size_t blocks=(rem >= 56) ? 2 : 1;
    U64 bitlen=U64(len)*8;
    for (int i=0;i<8;i++) tail[blocks*64-1-i]=uint8_t(bitlen>>(8*i));
    for (size_t i=0;i<blocks;i++) compress(s,parse_block(tail+64*i));
    Digest out{};
    for (int i=0;i<8;i++) store_be32(out.data()+4*i,s[i]);
    return out;
}

static Digest sha256d_reference(const Header& h) {
    Digest one=sha256_full(h.data(), h.size());
    return sha256_full(one.data(), one.size());
}

static bool equal_digest(const Digest& a, const Digest& b) { return a==b; }
static std::string hex_bytes(const uint8_t* p, size_t n, bool reverse=false) {
    std::ostringstream os; os << std::hex << std::setfill('0');
    for (size_t k=0;k<n;k++) { size_t i=reverse ? n-1-k : k; os << std::setw(2) << unsigned(p[i]); }
    return os.str();
}
static std::vector<uint8_t> parse_hex(const std::string& s) {
    if (s.size()%2) throw std::runtime_error("Hex string must have an even number of characters");
    std::vector<uint8_t> out; out.reserve(s.size()/2);
    for (size_t i=0;i<s.size();i+=2) out.push_back(uint8_t(std::stoul(s.substr(i,2),nullptr,16)));
    return out;
}
static U32 parse_u32(const std::string& s) { return U32(std::stoull(s,nullptr,0)); }

// Decode Bitcoin compact target. Output is 32-byte little-endian integer representation.
static std::array<uint8_t,32> decode_compact_target(U32 compact) {
    const unsigned size = compact >> 24;
    const U32 word = compact & 0x007fffffu;
    const bool negative = word != 0 && (compact & 0x00800000u);
    const bool overflow = word != 0 && (size > 34 || (word > 0xffu && size > 33) || (word > 0xffffu && size > 32));
    if (negative || overflow || word == 0) throw std::runtime_error("Invalid compact target (negative, zero, or overflow)");
    std::array<uint8_t,32> out{};
    // Build as a 256-bit little-endian integer without external big-integer dependencies.
    if (size <= 3) {
        U32 v = word >> (8*(3-size));
        for (int i=0;i<4 && i<32;i++) out[i]=uint8_t(v>>(8*i));
    } else {
        const unsigned shift=(size-3)*8;
        for (unsigned i=0;i<3;i++) {
            unsigned bitpos=shift + i*8;
            if (bitpos/8 < 32) out[bitpos/8] |= uint8_t(word>>(8*i));
        }
    }
    return out;
}

// Digest bytes are SHA output byte order. Bitcoin's uint256 numeric comparison
// interprets the serialized digest as a little-endian integer; compare from byte 31 down.
static bool meets_target(const Digest& digest, const std::array<uint8_t,32>& target_le) {
    for (int i=31;i>=0;i--) {
        if (digest[size_t(i)] < target_le[size_t(i)]) return true;
        if (digest[size_t(i)] > target_le[size_t(i)]) return false;
    }
    return true; // equality is accepted
}

// Same numeric comparison, but skip writing the 32-byte digest for unsuccessful candidates.
// SHA output words are big-endian; Bitcoin uint256 compares the digest bytes as a little-endian integer.
static bool meets_target_state(const State& final_state, const std::array<uint8_t,32>& target_le) {
    for (int word=7; word>=0; --word) {
        for (int byte=0; byte<4; ++byte) {
            const uint8_t hash_byte=uint8_t(final_state[size_t(word)] >> (8*byte));
            const uint8_t target_byte=target_le[size_t(4*word+3-byte)];
            if (hash_byte < target_byte) return true;
            if (hash_byte > target_byte) return false;
        }
    }
    return true;
}

static Header make_demo_header(U32 bits) {
    Header h{};
    store_le32(h.data()+0, 0x20000000u);
    // Deterministic synthetic prevhash and Merkle root; not a real network job.
    for (int i=0;i<32;i++) h[4+i]=uint8_t((i*13+7)&0xff);
    for (int i=0;i<32;i++) h[36+i]=uint8_t((i*29+11)&0xff);
    store_le32(h.data()+68, 1700000000u);
    store_le32(h.data()+72, bits);
    store_le32(h.data()+76, 0u);
    return h;
}

static void run_self_test() {
    const std::string abc="abc";
    const Digest d=sha256_full(reinterpret_cast<const uint8_t*>(abc.data()),abc.size());
    const std::string expected="ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad";
    if (hex_bytes(d.data(),d.size()) != expected) throw std::runtime_error("SHA-256 abc KAT failed");
    Header h=make_demo_header(0x207fffffu);
    PreparedJob job=prepare_job(h);
    Digest optimized=sha256d_from_prepared_job(job,load_le32(h.data()+76));
    Digest reference=sha256d_reference(h);
    if (!equal_digest(optimized,reference)) throw std::runtime_error("SHA-256d midstate self-test failed");
    U32 rng=0x6d2b79f5u;
    for (int n=0;n<10000;n++) {
        State st{}; std::array<uint8_t,32> tgt{};
        for (auto& v:st) { rng=rng*1664525u+1013904223u; v=rng; }
        for (auto& v:tgt) { rng=rng*1664525u+1013904223u; v=uint8_t(rng>>24); }
        Digest dg=digest_from_state(st);
        if (meets_target_state(st,tgt) != meets_target(dg,tgt)) throw std::runtime_error("Direct target comparator self-test failed");
    }
    std::cout << "SELF_TEST=PASS\nTARGET_COMPARATOR_CROSSCHECKS=10000\nSHA256_ABC=" << hex_bytes(d.data(),d.size())
              << "\nSHA256D_HEADER=" << hex_bytes(optimized.data(),optimized.size()) << "\n";
}

static void print_usage() {
    std::cout << "MULTIMINER X v0.2.0\n"
      << "  --self-test\n"
      << "  --simulate [--threads N] [--max-nonces N] [--start-nonce N] [--bits 0x207fffff]\n"
      << "  --bench [--threads N] [--iterations N]  (midstate throughput, no target search)\n"
      << "  --bench-baseline [--threads N] [--iterations N]  (recompute full 80-byte header)\n"
      << "  --verify-genesis  (verify historic Bitcoin genesis header; no mining)\n"
      << "  --hash-header HEX160  (80-byte serialized header; prints raw SHA256d)\n"
      << "Notes: default simulator uses synthetic header + regtest-like easy target. Not mainnet mining.\n";
}

int main(int argc,char** argv) try {
    if (argc==1) { print_usage(); return 0; }
    bool self=false, simulate=false, verify_genesis=false;
    bool benchmark=false, baseline_benchmark=false;
    U64 benchmark_iterations=1000000ull;
    int threads=int(std::max(1u,std::thread::hardware_concurrency()));
    U64 max_nonces=10000000ull;
    U32 start_nonce=0, bits=0x207fffffu;
    std::string hash_header;
    for (int i=1;i<argc;i++) {
        std::string a=argv[i];
        auto val=[&]() -> std::string { if (i+1>=argc) throw std::runtime_error("Missing value after "+a); return argv[++i]; };
        if (a=="--self-test") self=true;
        else if (a=="--simulate") simulate=true;
        else if (a=="--verify-genesis") verify_genesis=true;
        else if (a=="--bench") benchmark=true;
        else if (a=="--bench-baseline") baseline_benchmark=true;
        else if (a=="--iterations") benchmark_iterations=std::stoull(val());
        else if (a=="--threads") threads=std::max(1,int(std::stoul(val())));
        else if (a=="--max-nonces") max_nonces=std::stoull(val());
        else if (a=="--start-nonce") start_nonce=parse_u32(val());
        else if (a=="--bits") bits=parse_u32(val());
        else if (a=="--hash-header") hash_header=val();
        else if (a=="--help" || a=="-h") { print_usage(); return 0; }
        else throw std::runtime_error("Unknown option: "+a);
    }
    if (self) run_self_test();
    if (verify_genesis) {
        const std::string gh =
          "01000000"
          "0000000000000000000000000000000000000000000000000000000000000000"
          "3ba3edfd7a7b12b27ac72c3e67768f617fc81bc3888a51323a9fb8aa4b1e5e4a"
          "29ab5f49" "ffff001d" "1dac2b7c";
        auto bytes=parse_hex(gh);
        Header h{}; std::copy(bytes.begin(),bytes.end(),h.begin());
        PreparedJob job=prepare_job(h);
        Digest d=sha256d_from_prepared_job(job,load_le32(h.data()+76));
        const auto target=decode_compact_target(0x1d00ffffu);
        const std::string display=hex_bytes(d.data(),d.size(),true);
        const bool ok=(display=="000000000019d6689c085ae165831e934ff763ae46a2a6c172b3f1b60a8ce26f") && meets_target(d,target) && equal_digest(d,sha256d_reference(h));
        std::cout << "HISTORIC_HEADER=BITCOIN_GENESIS\n"
                  << "BITS=0x1d00ffff\n"
                  << "EXPECTED_DISPLAY_HASH=000000000019d6689c085ae165831e934ff763ae46a2a6c172b3f1b60a8ce26f\n"
                  << "ACTUAL_DISPLAY_HASH=" << display << "\n"
                  << "TARGET_CHECK=" << (meets_target(d,target)?"PASS":"FAIL") << "\n"
                  << "REFERENCE_RECHECK=" << (equal_digest(d,sha256d_reference(h))?"PASS":"FAIL") << "\n"
                  << "GENESIS_POW_VERIFICATION=" << (ok?"PASS":"FAIL") << "\n";
        if (!ok) return 2;
    }
    if (benchmark || baseline_benchmark) {
        Header base=make_demo_header(0x207fffffu);
        const PreparedJob job=prepare_job(base);
        std::atomic<U64> completed{0};
        std::atomic<U64> checksum{0};
        const auto t0=std::chrono::steady_clock::now();
        std::vector<std::thread> workers; workers.reserve(size_t(threads));
        for (int tid=0;tid<threads;tid++) {
            workers.emplace_back([&,tid]() {
                Header h=base;
                U64 local_sum=0;
                for (U64 index=U64(tid); index<benchmark_iterations; index+=U64(threads)) {
                    const U32 nonce=start_nonce+U32(index);
                    State final_state;
                    if (baseline_benchmark) {
                        store_le32(h.data()+76,nonce);
                        Digest d=sha256d_reference(h);
                        for (int w=0;w<8;w++) final_state[size_t(w)]=load_be32(d.data()+4*w);
                    } else {
                        final_state=sha256d_state_for_nonce(job,nonce);
                    }
                    local_sum += (U64(final_state[0])<<32) | U64(final_state[1]);
                }
                checksum.fetch_xor(local_sum,std::memory_order_relaxed);
            });
        }
        for (auto& th:workers) th.join();
        const auto t1=std::chrono::steady_clock::now();
        const double sec=std::chrono::duration<double>(t1-t0).count();
        std::cout << "MODE=" << (baseline_benchmark?"FULL_HEADER_RECOMPUTE_BASELINE":"MIDSTATE_OPTIMIZED") << "\n"
                  << "THREADS=" << threads << "\n"
                  << "HASHES=" << benchmark_iterations << "\n"
                  << std::fixed << std::setprecision(6)
                  << "ELAPSED_SECONDS=" << sec << "\n"
                  << "HASHRATE_HS=" << (sec>0 ? double(benchmark_iterations)/sec : 0.0) << "\n"
                  << "CHECKSUM=" << checksum.load() << "\n";
    }
    if (!hash_header.empty()) {
        auto bytes=parse_hex(hash_header);
        if (bytes.size()!=80) throw std::runtime_error("--hash-header needs exactly 80 bytes (160 hex characters)");
        Header h{}; std::copy(bytes.begin(),bytes.end(),h.begin());
        PreparedJob job=prepare_job(h);
        Digest got=sha256d_from_prepared_job(job,load_le32(h.data()+76)), ref=sha256d_reference(h);
        if (!equal_digest(got,ref)) throw std::runtime_error("Internal reference mismatch");
        std::cout << "RAW_SHA256D=" << hex_bytes(got.data(),got.size())
                  << "\nBITCOIN_DISPLAY_HASH=" << hex_bytes(got.data(),got.size(),true)
                  << "\nREFERENCE_CHECK=PASS\n";
        return 0;
    }
    if (simulate) {
        const auto target=decode_compact_target(bits);
        Header base=make_demo_header(bits);
        const PreparedJob job=prepare_job(base); // precompute invariant header fields once per job
        std::atomic<bool> found{false};
        std::atomic<U64> tried{0};
        std::mutex result_mutex;
        U32 found_nonce=0; Digest found_hash{};
        const auto t0=std::chrono::steady_clock::now();
        std::vector<std::thread> workers;
        workers.reserve(size_t(threads));
        for (int tid=0;tid<threads;tid++) {
            workers.emplace_back([&,tid]() {
                U64 local=0;
                while (!found.load(std::memory_order_relaxed)) {
                    U64 index=U64(tid)+local*U64(threads);
                    if (index>=max_nonces) break;
                    U32 nonce=start_nonce+U32(index);
                    State final_state=sha256d_state_for_nonce(job,nonce);
                    tried.fetch_add(1,std::memory_order_relaxed);
                    if (meets_target_state(final_state,target)) {
                        bool expected=false;
                        if (found.compare_exchange_strong(expected,true)) {
                            std::lock_guard<std::mutex> lock(result_mutex);
                            found_nonce=nonce; found_hash=digest_from_state(final_state);
                        }
                        break;
                    }
                    ++local;
                }
            });
        }
        for (auto& th:workers) th.join();
        const auto t1=std::chrono::steady_clock::now();
        const double sec=std::chrono::duration<double>(t1-t0).count();
        const U64 n=tried.load();
        std::cout << "MODE=SYNTHETIC_REGTEST_STYLE_SIMULATION\n"
                  << "WARNING=Not a real Bitcoin block, not a mainnet job, not pool mining\n"
                  << "BITS=0x" << std::hex << bits << std::dec << "\n"
                  << "THREADS=" << threads << "\n"
                  << "NONCES_TESTED=" << n << "\n"
                  << std::fixed << std::setprecision(6)
                  << "ELAPSED_SECONDS=" << sec << "\n"
                  << "HASHRATE_HS=" << (sec>0 ? double(n)/sec : 0.0) << "\n";
        if (found.load()) {
            Header h=job.header_template; store_le32(h.data()+76,found_nonce);
            Digest check=sha256d_reference(h);
            const bool valid=equal_digest(check,found_hash) && meets_target(check,target);
            std::cout << "RESULT=" << (valid ? "VALID_FOR_SYNTHETIC_TARGET" : "VALIDATION_FAILED")
                      << "\nNONCE_DEC=" << found_nonce
                      << "\nNONCE_HEX_LE=" << hex_bytes(h.data()+76,4)
                      << "\nRAW_SHA256D=" << hex_bytes(found_hash.data(),found_hash.size())
                      << "\nBITCOIN_DISPLAY_HASH=" << hex_bytes(found_hash.data(),found_hash.size(),true)
                      << "\nINDEPENDENT_RECHECK=" << (valid ? "PASS" : "FAIL") << "\n";
            return valid ? 0 : 2;
        }
        std::cout << "RESULT=NO_HIT_IN_SEARCH_LIMIT\n";
        return 1;
    }
    print_usage();
    return 0;
} catch (const std::exception& e) {
    std::cerr << "ERROR: " << e.what() << "\n";
    return 2;
}
