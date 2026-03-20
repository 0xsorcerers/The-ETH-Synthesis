# Submission Recovery Audit (2026-03-20)

This audit records where we searched for previously issued Synthesis credentials/IDs and what was recoverable.

## Search Scope

- Full git history (`git rev-list --all`, `git grep` across all revisions)
- Current working tree (`rg` for Synthesis/API/team/project/token patterns)
- Shell history files (`~/.bash_history`, `~/.zsh_history` if present)
- Current process environment (`env` filtered for Synthesis/API variables)

## Recoverable Values Found

- Registration transaction hash:
  - `0x3be69aa1e843e835e794ed5a7bb1b46e91793c411e50c33e366cabf36970e02c`
- On-chain owner address from the mint tx event logs:
  - `0x6FFa1e00509d8B625c2F061D7dB07893B37199BC`
- Contract interacted with during registration:
  - `0x8004A169FB4a3325136EB29fA0ceB6D2e539a432` (Identity Registry)
- Agent token ID:
  - `34803`

## Sensitive Values Not Recoverable

No trace of the following was found in repo history, local shell history, or current environment:

- `SYNTH_API_KEY`
- `TEAM_UUID`
- `PROJECT_UUID`
- transfer tokens / OTPs

## Why This Matters

- We can prove the registration/mint transaction and owner wallet derived from on-chain data.
- We **cannot** execute authenticated publish endpoints without re-obtaining the API key and IDs from your Synthesis account session.

## Next Action

Use `scripts/publish_synthesis.sh` once credentials are available again:

1. `catalog`
2. `whoami` and `cache-session`
3. `create` / `update`
4. `publish`
5. `verify`


## Persistence Policy Update

To prevent this issue going forward, the publish CLI now includes `cache-session`, which can persist discovered `TEAM_UUID` and `PROJECT_UUID` into `tmp/synthesis_session.env` (git-ignored) after authenticated API discovery.
