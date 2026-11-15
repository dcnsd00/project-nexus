from __future__ import annotations
import hashlib, json, os, platform, subprocess, tempfile, time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
SRC=ROOT/'research'/'legacy'/'btc_sha256d.cpp'
OUT=ROOT/'research'/'results'/'benchmark_report.json'

def run(cmd):
    return subprocess.run(cmd,capture_output=True,text=True,check=True).stdout

def main():
    compiler=os.environ.get('CXX','g++')
    exe=Path(tempfile.gettempdir())/'mmx_sha256d_bench'
    build=run([compiler,'-O3','-march=native','-std=c++17','-pthread',str(SRC),'-o',str(exe)])
    checks=run([str(exe),'--self-test','--verify-genesis'])
    optimized_runs=[run([str(exe),'--bench','--iterations','1000000','--threads','4']) for _ in range(3)]
    baseline_runs=[run([str(exe),'--bench-baseline','--iterations','1000000','--threads','4']) for _ in range(3)]
    # SHA-512 digest throughput on 64 MiB payload; this is hash throughput, not mining.
    payload=b'MULTIMINER-X-SHA512-BENCHMARK\0'*2_000_000
    sha512_runs=[]
    for _ in range(3):
        start=time.perf_counter(); digest=hashlib.sha512(payload).hexdigest(); elapsed=time.perf_counter()-start
        sha512_runs.append({'elapsed_seconds':elapsed,'throughput_mib_s':len(payload)/elapsed/(1024**2)})
    sha512={'bytes':len(payload),'runs':sha512_runs,'median_throughput_mib_s':sorted(x['throughput_mib_s'] for x in sha512_runs)[1],'digest_prefix':digest[:16]}
    def parse(s):
        return {k:v for line in s.splitlines() if '=' in line for k,v in [line.split('=',1)]}
    opt_runs=[parse(x) for x in optimized_runs]; base_runs=[parse(x) for x in baseline_runs]
    opt_rates=[float(x['HASHRATE_HS']) for x in opt_runs]; base_rates=[float(x['HASHRATE_HS']) for x in base_runs]
    opt,base=opt_runs[opt_rates.index(sorted(opt_rates)[1])],base_runs[base_rates.index(sorted(base_rates)[1])]
    oh=sorted(opt_rates)[1]; bh=sorted(base_rates)[1]
    report={'environment':{'platform':platform.platform(),'processor':platform.processor(),'logical_cpus':os.cpu_count(),'compiler':compiler,'flags':'-O3 -march=native -std=c++17 -pthread'},
      'correctness':{'cpp_self_test':'PASS' if 'SELF_TEST=PASS' in checks else 'FAIL','genesis_pow':'PASS' if 'GENESIS_POW_VERIFICATION=PASS' in checks else 'FAIL','output':checks},
      'sha256d_benchmark':{'optimized_median':opt,'optimized_runs':opt_runs,'full_header_baseline_median':base,'baseline_runs':base_runs,'relative_speedup':oh/bh,'interpretation':'Synthetic 80-byte header throughput only; no pool, no live block job, no Bitcoin payout.'},
      'sha512_benchmark':sha512,
      'limits':['Container benchmark, not Asus TUF measurement.','SHA-512 benchmark is digest throughput, not a PoW mining rate.','No power meter; joules/hash not measured.','SHA-256d cannot be decrypted; only known-candidate digest verification is implemented.']}
    OUT.write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report,indent=2))
if __name__=='__main__': main()
