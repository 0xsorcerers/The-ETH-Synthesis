# AGENTS.md (Repo Operator Guide)

Scope: entire repository.

## Submission workflow rule

1. Register
2. Create/Edit draft project
3. Verify or complete ERC-8004 transfer to intended owner wallet
4. Publish

Team policy update: a team can submit up to 3 projects in Synthesis.

## Local state persistence rule

- Persist all non-sensitive submission/session values into a local env file before and after each API step.
- Preferred command:

```bash
scripts/publish_synthesis.sh save-env
```

- Default output file: `.env.synthesis.local`
- This file is local-only and must remain git-ignored.

## Security rule

- Never commit API keys, transfer tokens, OTPs, or private keys.
- Keep secret-bearing values in local env files only.

## Project framing rule

When drafting submission/project copy, reflect the core problem faithfully:

- Crypto users across jurisdictions struggle to produce compliant, auditable tax records.
- Skynet addresses this by classifying on-chain/CSV activity and applying jurisdiction-aware tax logic with transparent assumptions.


## Builder-guide note

- Submission deadline: March 22, 2026 11:59 PM PST.
- Keep deployment live for judging window (March 23–25).
