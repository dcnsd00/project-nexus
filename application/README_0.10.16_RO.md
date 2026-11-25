# NEXUS MASTER 0.10.16

Versiune incrementală construită peste 0.10.15.

- Wallet EVM: fluxul de decriptare existent este testat; parola se introduce local prin endpoint-ul de unlock. Cheia privată nu este returnată.
- Matematică: `bitvector_xor` are acum fallback nativ exact, fără dependență obligatorie de Z3 pentru ecuația XOR neconstrânsă.
- SAT redus SHA-256, conectorii DePIN și transferurile blockchain rămân explicit nevalidate/în așteptare acolo unde lipsesc dependențe, contracte API sau noduri locale.

Rulează `./run_full_audit.sh` pentru auditul offline complet.
