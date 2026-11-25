# Sample benchmark (container, not user's hardware)

CPU reported by the execution container: AMD EPYC 9V74, KVM virtualized, 5 visible logical CPUs. Compiler: GCC `-O3 -march=native`, C++17. Each run hashes 1,000,000 80-byte synthetic headers with a changing nonce. Three repetitions per setting; medians are in `benchmark_sandbox.csv`.

| Threads | Midstate median | Full-header baseline median | Relative gain | Midstate scaling efficiency vs 1 thread |
|---:|---:|---:|---:|---:|
| 1 | 1.925 MH/s | 1.466 MH/s | 1.31× | 100% |
| 2 | 3.097 MH/s | 2.202 MH/s | 1.41× | 80.5% |
| 4 | 6.082 MH/s | 3.855 MH/s | 1.58× | 79.0% |
| 8 | 7.807 MH/s | 4.014 MH/s | 1.95× | 50.7% |

These values are a reproducibility sample from a shared virtualized environment, not an estimate of the user's Asus or mini-PC performance. Eight worker threads oversubscribe the five visible vCPUs. Variation between repetitions is visible; repeat on the actual device under controlled thermal and power conditions.

No electrical power meter was connected, so **energy per hash and electricity savings were not measured**. The H/s increase is not evidence of reduced joules/hash.
