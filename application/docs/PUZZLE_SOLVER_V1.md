# NEXUS Puzzle Solver v1

The Multi-Method Puzzle Solver is integrated into the existing NEXUS FastAPI control plane. It is a local, bounded utility, not a universal natural-language puzzle solver.

## API

- `GET /api/puzzles/capabilities` — available strategies and limits.
- `POST /api/puzzles/solve` — execute one explicitly typed problem.

Request envelope:

```json
{
  "problem": {
    "kind": "modular_congruence",
    "a": 14,
    "b": 30,
    "modulus": 100
  }
}
```

## Supported strategies

| Kind | Function |
|---|---|
| `text_decode` / `auto_text` | Local candidate generation: hex, Base64/Base64URL, Base32, Base85, Base58, binary/decimal bytes, URL percent, Caesar shifts, Morse and reverse |
| `modular_congruence` | Exact solution of (a x = b pmod m), through the existing Hybrid Solver |
| `linear_system` | Exact rational solution for square systems, through SymPy and the existing Hybrid Solver |
| `bitvector_xor` | Exact constructive XOR solution with independent XOR verification |
| `finite_csp` | Bounded finite-domain constraints: relations, sum, product, XOR and all-different |
| `phy_challenge` | Offline PHY structural analysis: Unicode 18.0, geometric antipodal pairs, candidate spatial orderings, ECDSA-s positional selectors and supplied secp256k1 public-point validation |
| `vigenere` | Vigenère decrypt when the owner supplies the key |
| `rail_fence` | Rail Fence decrypt when the rail count is supplied (2–12) |
| `affine_substitution` | Affine cipher decrypt with supplied coprime parameters |
| `text_decode` additions | Atbash and A1Z26 candidate decoders |

Example finite-domain puzzle:

```json
{
  "problem": {
    "kind": "finite_csp",
    "variables": {"x": [1, 2, 3], "y": [1, 2, 3]},
    "constraints": [
      {"type": "all_different", "variables": ["x", "y"]},
      {"type": "sum_eq", "variables": ["x", "y"], "target": 4}
    ]
  }
}
```

## Limits and interpretation

- CSP is capped at 16 variables, 16 integer values per domain, 100,000 visited assignments and 10 returned solutions.
- Text inputs are capped at 4,096 characters.
- Text decoding returns candidate interpretations; it does not claim a candidate is semantically correct.
- The reverse-word + ROT13 text transform is retained only as an exploratory test; the author later rejected ROT13.\n- The analyzer automatically tests eight simple Unicode-only bit features against `s`; no exact match is treated as a failed hypothesis, not a proof against pixel-derived tone rules.\n- `phy_challenge` accepts optional `bit_values_by_id` (256 explicit 0/1 assignments) and checks whether the first/last 72 bits match the public ECDSA `s` bytes under candidate order/orientation variants. The visual bit-assignment rule is not inferred automatically.
- Linear systems require SymPy. The route reports an explicit dependency/runtime error if it is unavailable.
- The existing SHA-256 SAT and differential work remains an isolated reduced-round research experiment. It is not advertised as a backend that can solve full SHA-256 or arbitrary SHA puzzles.
- Natural-language logic-grid parsing and external AI-worker execution are not included in this slice. A logic puzzle can be represented as finite-domain variables and constraints.

No Python evaluation, network calls, wallet/key/seed/password search, wallet unlocking, mining launch, transaction or automatic action is performed by this solver.
