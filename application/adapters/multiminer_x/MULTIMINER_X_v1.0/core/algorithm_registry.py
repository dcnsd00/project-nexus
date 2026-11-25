"""Algorithm/payout registry. Only the two backend profiles below are live-tested.
Other entries are research-only until an operator supplies and validates a pool.
"""
from dataclasses import dataclass

@dataclass(frozen=True)
class MiningProfile:
    profile_id: str
    label: str
    device: str
    algorithm: str
    backend: str
    pool_url: str | None
    status: str
    notes: str

PROFILES = {
    "cpu_randomx": MiningProfile("cpu_randomx", "CPU · RandomX", "CPU", "rx/0", "XMRig", "stratum+ssl://rx.unmineable.com:443", "LIVE_BACKEND", "Pool endpoint must be confirmed for selected payout coin."),
    "gpu_pearlhash": MiningProfile("gpu_pearlhash", "GPU · PearlHash/PearlPow", "GPU", "pearlhash", "SRBMiner-MULTI", "stratum+ssl://pearlpow.unmineable.com:4444", "LIVE_BACKEND", "NVIDIA/CUDA support depends on driver and miner build."),
    "sha256d_lab": MiningProfile("sha256d_lab", "SHA-256d · Bitcoin research", "CPU", "sha256d", "MULTIMINER-X research C++", None, "RESEARCH_ONLY", "Offline benchmark/synthetic target only; not connected to Bitcoin mainnet or pool."),
    "sha512_lab": MiningProfile("sha512_lab", "SHA-512 · cryptographic research", "CPU", "sha512", "Python hashlib/OpenSSL", None, "RESEARCH_ONLY", "Digest benchmark and test vectors; SHA-512 is not a PoW pool profile."),
}

# A user may choose a payout asset only after checking that it is currently listed
# and supported in their own unMineable account. This is not a claim of support.
PAYOUT_ASSET_CANDIDATES = ("BTC", "LTC", "DOGE", "XMR", "RVN", "ETC", "ERG", "KAS", "BONK")

def get_profile(profile_id: str) -> MiningProfile:
    try:
        return PROFILES[profile_id]
    except KeyError as exc:
        raise ValueError(f"Unknown mining profile: {profile_id}") from exc

def format_payout_identity(identity_with_worker: str, payout_ticker: str) -> str:
    """Prefix an unMineable payout ticker unless caller supplied COIN:ADDRESS."""
    import re
    identity = identity_with_worker.strip()
    coin = payout_ticker.strip().upper()
    if not identity:
        raise ValueError('Wallet/alias is required')
    if ':' in identity:
        return identity
    if not re.fullmatch(r'[A-Z0-9]{2,12}', coin):
        raise ValueError('Invalid payout ticker')
    return f'{coin}:{identity}'
