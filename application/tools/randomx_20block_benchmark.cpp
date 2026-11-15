
#include <randomx.h>
#include <atomic>
#include <array>
#include <vector>
#include <thread>
#include <chrono>
#include <iostream>
#include <iomanip>
#include <sstream>
#include <cstring>
#include <cstdint>
#include <cstdlib>
#include <algorithm>

struct Block {
    std::array<uint8_t, 80> blob{};
    unsigned target_bits=0;
    std::atomic<uint64_t> hashes{0};
    std::atomic<uint64_t> hits{0};
    std::atomic<uint64_t> first_nonce{UINT64_MAX};
    std::array<uint8_t,32> first_hash{};
};

static bool meets(const uint8_t* h, unsigned bits) {
    unsigned full=bits/8, rem=bits%8;
    for(unsigned i=0;i<full;i++) if(h[i]!=0) return false;
    if(rem && (h[full] >> (8-rem)) != 0) return false;
    return true;
}
static void set_nonce(uint8_t* p, uint32_t n) {
    p[76]=(uint8_t)n; p[77]=(uint8_t)(n>>8);
    p[78]=(uint8_t)(n>>16); p[79]=(uint8_t)(n>>24);
}
static std::string hex(const uint8_t* p,size_t n) {
    std::ostringstream s; s<<std::hex<<std::setfill('0');
    for(size_t i=0;i<n;i++) s<<std::setw(2)<<(unsigned)p[i];
    return s.str();
}
int main(int argc,char**argv) {
    unsigned threads=argc>1?std::stoul(argv[1]):4;
    uint32_t hashes_per_block=argc>2?std::stoul(argv[2]):12000;
    bool fast=argc>3?std::string(argv[3])!="light":true;
    if(threads<1 || threads>64 || hashes_per_block<1) return 2;
    const uint8_t seed[32]={
      0x4e,0x45,0x58,0x55,0x53,0x2d,0x52,0x58,0x2d,0x45,0x50,0x4f,0x43,0x48,0x2d,0x30,
      0x31,0x2d,0x32,0x30,0x32,0x36,0x2d,0x31,0x31,0x2d,0x31,0x31,0x00,0x00,0x00,0x01
    };
    randomx_flags flags=randomx_get_flags();
    if(fast) flags|=RANDOMX_FLAG_FULL_MEM;
    std::cout<<"mode="<<(fast?"fast":"light")<<" flags=0x"<<std::hex<<(unsigned)flags<<std::dec<<"\n";
    auto t0=std::chrono::steady_clock::now();
    randomx_cache* cache=randomx_alloc_cache(flags);
    if(!cache){std::cerr<<"cache allocation failed\n";return 3;}
    randomx_init_cache(cache,seed,sizeof(seed));
    randomx_dataset* dataset=nullptr;
    if(fast){
        dataset=randomx_alloc_dataset(flags);
        if(!dataset){std::cerr<<"dataset allocation failed\n";randomx_release_cache(cache);return 4;}
        uint32_t total=randomx_dataset_item_count();
        std::vector<std::thread> init;
        for(unsigned i=0;i<threads;i++){
            uint32_t start=(uint64_t)total*i/threads;
            uint32_t end=(uint64_t)total*(i+1)/threads;
            init.emplace_back(randomx_init_dataset,dataset,cache,start,end-start);
        }
        for(auto& t:init)t.join();
        randomx_release_cache(cache); cache=nullptr;
    }
    auto t1=std::chrono::steady_clock::now();
    std::vector<Block> blocks(20);
    for(unsigned b=0;b<blocks.size();b++){
        auto &x=blocks[b];
        for(unsigned j=0;j<x.blob.size();j++)
            x.blob[j]=(uint8_t)((b*29+j*17+(b*j)%251)&255);
        // Make a recognizable synthetic header: magic, height and id marker.
        x.blob[0]='N'; x.blob[1]='X'; x.blob[2]='R'; x.blob[3]='X';
        uint32_t height=500000+b;
        memcpy(&x.blob[4],&height,4);
        x.blob[8]=(uint8_t)b;
        x.target_bits=8+(b%7); // lab targets: 8..14 leading zero bits
        set_nonce(x.blob.data(),0);
    }
    std::vector<randomx_vm*> vms;
    for(unsigned i=0;i<threads;i++){
        randomx_vm* vm=randomx_create_vm(flags,cache,dataset);
        if(!vm){std::cerr<<"VM creation failed\n";return 5;}
        vms.push_back(vm);
    }
    std::atomic<uint64_t> next_index{0};
    auto run_start=std::chrono::steady_clock::now();
    std::vector<std::thread> workers;
    for(unsigned ti=0;ti<threads;ti++){
        workers.emplace_back([&,ti](){
            uint8_t out[32];
            while(true){
                uint64_t work_index=next_index.fetch_add(1);
                if(work_index >= (uint64_t)20*hashes_per_block) break;
                unsigned bi=(unsigned)(work_index%20);
                uint64_t nonce=work_index/20;
                blocks[bi].hashes.fetch_add(1);
                auto blob=blocks[bi].blob;
                set_nonce(blob.data(),(uint32_t)nonce);
                randomx_calculate_hash(vms[ti],blob.data(),blob.size(),out);
                if(meets(out,blocks[bi].target_bits)){
                    blocks[bi].hits.fetch_add(1);
                    uint64_t expected=UINT64_MAX;
                    if(blocks[bi].first_nonce.compare_exchange_strong(expected,nonce))
                        memcpy(blocks[bi].first_hash.data(),out,32);
                }
            }
        });
    }
    // The threads terminate after all per-block counters exceed quota.
    for(auto& t:workers)t.join();
    auto run_end=std::chrono::steady_clock::now();
    double init_s=std::chrono::duration<double>(t1-t0).count();
    double elapsed=std::chrono::duration<double>(run_end-run_start).count();
    uint64_t total_hashes=0,total_hits=0;
    for(unsigned b=0;b<20;b++){total_hashes+=blocks[b].hashes.load(); total_hits+=blocks[b].hits.load();}
    std::cout<<std::fixed<<std::setprecision(6);
    std::cout<<"init_seconds="<<init_s<<"\n";
    std::cout<<"benchmark_seconds="<<elapsed<<"\n";
    std::cout<<"threads="<<threads<<" blocks=20 hashes_per_block="<<hashes_per_block<<"\n";
    std::cout<<"total_hashes="<<total_hashes<<" total_hits="<<total_hits<<"\n";
    std::cout<<"hashrate_hs="<<(total_hashes/elapsed)<<"\n";
    for(unsigned b=0;b<20;b++){
        auto &x=blocks[b];
        std::cout<<"block="<<b<<" height="<<(500000+b)<<" target_zero_bits="<<x.target_bits
                 <<" hashes="<<x.hashes.load()<<" hits="<<x.hits.load()
                 <<" first_nonce=";
        if(x.first_nonce.load()==UINT64_MAX) std::cout<<"none";
        else std::cout<<x.first_nonce.load()<<" first_hash="<<hex(x.first_hash.data(),32);
        std::cout<<"\n";
    }
    for(auto vm:vms)randomx_destroy_vm(vm);
    if(dataset)randomx_release_dataset(dataset);
    if(cache)randomx_release_cache(cache);
}
