# Autonomy Rule

Skynet operates on a continuous improvement loop for this repository:

1. Pick the highest-value next improvement that strengthens the working product or submission quality.
2. Implement the change directly.
3. Run the relevant verification.
4. Update repo documentation whenever the change affects architecture, submission evidence, or operator understanding.
5. Prefer stable machine-readable contracts for autonomous branching instead of asking agents to infer next actions from scattered UI text.
6. Preserve submission integrity:
   - never invent skills, tools, or resources for submission metadata
   - never expose secrets, API keys, OTPs, or transfer tokens
   - never ask a human for private keys
7. Treat submission readiness as part of product quality:
   - keep the collaboration log current
   - keep the public repo submission-ready
   - keep required submission fields and evidence obvious in docs
8. Before any future publish step, confirm all team members are in self-custody and the intended wallet address has been re-verified.
9. Commit and push the tested slice.
10. Immediately continue to the next meaningful improvement unless blocked by missing access, missing requirements, or materially ambiguous product direction.

Stopping condition:

- No meaningful product, demo, submission, or engineering improvement remains that can be made with the current repo state and available access.
