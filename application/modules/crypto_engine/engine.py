from __future__ import annotations

import hashlib
import hmac
import time
from dataclasses import dataclass
from typing import Any


class CryptoInputError(ValueError):
    """Invalid request parameters for a cryptographic operation."""


class AlgorithmUnavailable(RuntimeError):
    """Requested algorithm is not available in this Python/OpenSSL build."""


@dataclass(frozen=True)
class AlgorithmInfo:
    name: str
    family: str
    digest_bits: int | None
    variable_output: bool
    security_status: str
    notes: str


# Only algorithms supplied by hashlib are enabled automatically. This avoids
# silently substituting a different implementation or algorithm.
_FIXED: dict[str, tuple[str, str, int, str]] = {
    "sha224": ("sha2", "sha224", 224, "SHA-2 fixed-output digest"),
    "sha256": ("sha2", "sha256", 256, "SHA-2 fixed-output digest"),
    "sha384": ("sha2", "sha384", 384, "SHA-2 fixed-output digest"),
    "sha512": ("sha2", "sha512", 512, "SHA-2 fixed-output digest"),
    "sha512_256": ("sha2", "sha512_256", 256, "SHA-512/256 where supported"),
    "sha3_224": ("sha3", "sha3_224", 224, "Keccak-derived standardized SHA-3"),
    "sha3_256": ("sha3", "sha3_256", 256, "Keccak-derived standardized SHA-3"),
    "sha3_384": ("sha3", "sha3_384", 384, "Keccak-derived standardized SHA-3"),
    "sha3_512": ("sha3", "sha3_512", 512, "Keccak-derived standardized SHA-3"),
    "blake2b_256": ("blake2", "blake2b", 256, "BLAKE2b configured for 256-bit output"),
    "blake2b_512": ("blake2", "blake2b", 512, "BLAKE2b configured for 512-bit output"),
    "blake2s_256": ("blake2", "blake2s", 256, "BLAKE2s configured for 256-bit output"),
}
_SHAKE = {"shake128": ("shake", "shake_128"), "shake256": ("shake", "shake_256")}


class CryptoEngine:
    """Small, auditable hashing API. Experimental composites are not consensus algorithms."""

    MAX_INPUT_BYTES = 8 * 1024 * 1024
    MAX_OUTPUT_BYTES = 4096

    @staticmethod
    def _normalise(name: str) -> str:
        if not isinstance(name, str) or not name.strip():
            raise CryptoInputError("algorithm must be a non-empty string")
        return name.strip().lower().replace("-", "_")

    def algorithms(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        available = hashlib.algorithms_available
        for public, (family, impl, bits, note) in _FIXED.items():
            if impl in available:
                rows.append(AlgorithmInfo(public, family, bits, False, "standardized_primitive_not_a_consensus_profile", note).__dict__)
        for public, (family, impl) in _SHAKE.items():
            if impl in available:
                rows.append(AlgorithmInfo(public, family, None, True, "standardized_primitive_not_a_consensus_profile",
                                          "SHAKE XOF; caller selects output length").__dict__)
        rows.append(AlgorithmInfo("sha256d", "composite", 256, False, "bitcoin_header_hash_only",
                                  "Bitcoin-style double SHA-256; use only where the Bitcoin protocol specifies it").__dict__)
        rows.append(AlgorithmInfo("hybrid_sha256_blake2b", "experimental", 256, False, "experimental_do_not_use_for_consensus",
                                  "Domain-separated research composite; not suitable for consensus, signatures, or key derivation").__dict__)
        try:
            import blake3  # type: ignore  # noqa: F401
            rows.append(AlgorithmInfo("blake3", "blake3", None, True, "standardized_primitive_not_a_consensus_profile",
                                      "Optional BLAKE3 package; output length is configurable").__dict__)
        except ImportError:
            pass
        return rows

    def digest(self, algorithm: str, data: bytes, output_bytes: int | None = None) -> bytes:
        name = self._normalise(algorithm)
        if not isinstance(data, (bytes, bytearray, memoryview)):
            raise CryptoInputError("data must be bytes")
        payload = bytes(data)
        if len(payload) > self.MAX_INPUT_BYTES:
            raise CryptoInputError("input exceeds 8 MiB safety limit")
        if name == "sha256d":
            if output_bytes not in (None, 32):
                raise CryptoInputError("sha256d output is fixed at 32 bytes")
            return hashlib.sha256(hashlib.sha256(payload).digest()).digest()
        if name == "hybrid_sha256_blake2b":
            if output_bytes not in (None, 32):
                raise CryptoInputError("experimental composite output is fixed at 32 bytes")
            # Length/domain separation prevents ambiguous concatenation.
            first = hashlib.sha256(b"NEXUS-HYBRID-v1\x00" + len(payload).to_bytes(8, "big") + payload).digest()
            return hashlib.blake2b(b"NEXUS-HYBRID-v1\x01" + first, digest_size=32).digest()
        if name in _SHAKE:
            size = 32 if output_bytes is None else output_bytes
            self._validate_output(size)
            return hashlib.new(_SHAKE[name][1], payload).digest(size)
        if name == "blake3":
            size = 32 if output_bytes is None else output_bytes
            self._validate_output(size)
            try:
                import blake3  # type: ignore
            except ImportError as exc:
                raise AlgorithmUnavailable("optional dependency 'blake3' is not installed") from exc
            return blake3.blake3(payload).digest(length=size)
        if name in _FIXED:
            family, impl, bits, _ = _FIXED[name]
            expected = bits // 8
            if output_bytes not in (None, expected):
                raise CryptoInputError(f"{name} output is fixed at {expected} bytes")
            try:
                if impl == "blake2b":
                    return hashlib.blake2b(payload, digest_size=expected).digest()
                if impl == "blake2s":
                    return hashlib.blake2s(payload, digest_size=expected).digest()
                return hashlib.new(impl, payload).digest()
            except (ValueError, TypeError) as exc:
                raise AlgorithmUnavailable(f"{name} is not supported by this runtime") from exc
        raise CryptoInputError(f"unsupported algorithm: {name}")

    @classmethod
    def _validate_output(cls, size: int) -> None:
        if not isinstance(size, int) or isinstance(size, bool) or not 1 <= size <= cls.MAX_OUTPUT_BYTES:
            raise CryptoInputError(f"output_bytes must be an integer from 1 to {cls.MAX_OUTPUT_BYTES}")

    def digest_hex(self, algorithm: str, data: bytes, output_bytes: int | None = None) -> str:
        return self.digest(algorithm, data, output_bytes).hex()

    def hmac_sha256(self, key: bytes, data: bytes) -> bytes:
        if not isinstance(key, bytes) or not isinstance(data, bytes):
            raise CryptoInputError("key and data must be bytes")
        if len(key) > self.MAX_INPUT_BYTES or len(data) > self.MAX_INPUT_BYTES:
            raise CryptoInputError("key or data exceeds 8 MiB safety limit")
        return hmac.new(key, data, hashlib.sha256).digest()

    def benchmark(self, algorithm: str, payload_bytes: int = 1024, iterations: int = 1000,
                  output_bytes: int | None = None) -> dict[str, Any]:
        if not isinstance(payload_bytes, int) or not 0 <= payload_bytes <= self.MAX_INPUT_BYTES:
            raise CryptoInputError("payload_bytes must be from 0 to 8 MiB")
        if not isinstance(iterations, int) or not 1 <= iterations <= 1_000_000:
            raise CryptoInputError("iterations must be from 1 to 1,000,000")
        payload = b"\xA5" * payload_bytes
        # Warm-up is deliberately excluded from measured time.
        self.digest(algorithm, payload, output_bytes)
        started = time.perf_counter()
        checksum = b""
        for _ in range(iterations):
            checksum = self.digest(algorithm, payload, output_bytes)
        elapsed = max(time.perf_counter() - started, 1e-12)
        total = payload_bytes * iterations
        return {
            "algorithm": self._normalise(algorithm), "payload_bytes": payload_bytes,
            "iterations": iterations, "elapsed_seconds": elapsed,
            "hashes_per_second": iterations / elapsed,
            "mib_per_second": (total / (1024 * 1024)) / elapsed,
            "output_hex": checksum.hex(), "measurement": "local microbenchmark; not a PoW hashrate",
        }
