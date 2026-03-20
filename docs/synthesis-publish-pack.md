# Synthesis Publish Pack (Prepared 2026-03-20)

This file compiles all non-sensitive registration/submission data currently available in this repository and your latest message, then maps it to the official publish flow.

## Confirmed Data (Recovered)

- Registration transaction: `https://basescan.org/tx/0x3be69aa1e843e835e794ed5a7bb1b46e91793c411e50c33e366cabf36970e02c`
- Team mode: solo team (single owner wallet controls the required NFT)
- Mint/registration owner wallet seen on-chain in tx logs: `0x6FFa1e00509d8B625c2F061D7dB07893B37199BC`
- Project name: `Skynet by 0xSorcerer`
- Agent harness: `codex-cli`
- Model: `gpt-5.2-codex`
- Human profile (from registration payload):
  - Name: `Tejiri Nuvie Chiedu Odu`
  - Email: `0xsorcerer@gmail.com`
  - Social handle: `@0xsorcerers`
  - Background: `Builder`
  - Crypto experience: `yes`
  - AI agent experience: `yes`
  - Coding comfort: `9`
  - Problem to solve: crypto-native tax compliance assistant for global users

## Security-Protected Data (Not in Repo by Design)

The following are intentionally excluded from git history/docs and are still required to complete the live publish call:

- `SYNTH_API_KEY` (format: `sk-synth-...`)
- `TEAM_UUID`
- `PROJECT_UUID` (if draft already exists)
- Owner wallet address currently recognized by Synthesis for your participant
- Selected `TRACK_UUIDS`
- `MOLTBOOK_POST_URL`
- Final public GitHub `REPO_URL`

## Official API Flow (Create/Update + Publish)

Base URL: `https://synthesis.devfolio.co`

1. Verify tracks: `GET /catalog`
2. Verify team and existing project: `GET /teams/:teamUUID`
3. Create draft (`POST /projects`) or update existing draft (`POST /projects/:projectUUID`)
4. (If needed) complete/verify self-custody transfer
5. Publish: `POST /projects/:projectUUID/publish`
6. Verify final state with:
   - `GET /projects/:projectUUID`
   - `GET /projects?page=1&limit=20`

## Ready-to-Use Command Runner

Use `scripts/publish_synthesis.sh` with environment variables (kept out of git).

Example:

```bash
export SYNTH_API_KEY='sk-synth-...'
export TEAM_UUID='...'
export TRACK_UUIDS='["track-uuid-1"]'
export OWNER_WALLET='0x...'
export REPO_URL='https://github.com/<owner>/<repo>'
export MOLTBOOK_POST_URL='https://www.moltbook.com/posts/...'

## discover + cache identifiers first:
scripts/publish_synthesis.sh cache-session
source tmp/synthesis_session.env

# if no project exists yet:
scripts/publish_synthesis.sh create

# if draft already exists:
export PROJECT_UUID='...'
scripts/publish_synthesis.sh update

# final publish:
scripts/publish_synthesis.sh publish
```

## Notes

- This repository deliberately does not store the API key or OTP/transfer tokens.
- Keep all secrets in shell env vars or a local untracked `.env`.
- If your solo participant is already in self-custody and owner wallet is unchanged, publish can proceed once draft completeness is confirmed.

## Wallet Mismatch Check

- Provided owner wallet in latest message: `0x8B40FC00D483b8A6A31539BbB399B14e1d36E454`
- Mint tx owner from registration event: `0x6FFa1e00509d8B625c2F061D7dB07893B37199BC`
- Treat this as a **must-verify** mismatch before publish. If the platform participant owner is now `0x8B40...E454`, run transfer verification first.
