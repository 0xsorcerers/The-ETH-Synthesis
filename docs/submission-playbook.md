# Submission Playbook

This file distills the official Synthesis submission skill into a repo-local checklist and procedure for Skynet.

For a prefilled operator handoff with recovered registration context and command-ready API flow, use `docs/synthesis-publish-pack.md`.

Sources used: [The Synthesis submission skill](https://synthesis.md/submission/skill.md) (redirects to `synthesis.devfolio.co`) and the Synthesis Builder Guide (shared 2026-03-20 in operator chat).

## Non-Negotiable Rules

1. A team can submit up to 3 projects (updated builder-guide policy).
2. Draft projects can be created and edited before self-custody, but publishing requires self-custody for every team member.
   For a solo team, this reduces to verifying the single owner wallet already holds the required participation NFT and remains the intended publish owner.
3. The repository must be public by the deadline.
4. The conversation log is judged and must reflect the real human-agent build process.
5. Submission metadata must be honest:
   - list only skills the agent actually had loaded
   - list only concrete tools actually used
   - list only documentation URLs actually opened and read
6. Never ask anyone to share private keys.
7. Never print, log, or commit API keys, transfer tokens, OTPs, or other secrets.
8. Before confirming self-custody transfer, verify the returned `targetOwnerAddress` exactly matches the intended wallet address.
9. Treat publishing as the final state even though minor edits are allowed until the hackathon ends.

## Submission Flow

Cloudflare note: if API calls are blocked, prefer `https://synthesis.md/skill.md` URLs/workflow per builder guide guidance.

1. Discover tracks with `GET /catalog` and save the selected `trackUUIDs`.
2. Confirm the current team and whether a project already exists with `GET /teams/:teamUUID`.
3. Create or update a draft project.
4. Publish a Moltbook post announcing the project and save the post URL.
5. Ensure every team member completes self-custody transfer.
6. Re-check required fields and evidence.
7. Publish with `POST /projects/:projectUUID/publish`.
8. Verify the published status and public listing.

## Required Draft Fields

The draft submission must include:

- `teamUUID`
- `name`
- `description`
- `problemStatement`
- `repoURL`
- `trackUUIDs`
- `conversationLog`
- `submissionMetadata`

Optional but valuable:

- `deployedURL`
- `videoURL`
- `pictures`
- `coverImageURL`

## Required `submissionMetadata`

The full object is required during create and on any update that changes metadata.

- `agentFramework`
- `agentFrameworkOther` when `agentFramework` is `other`
- `agentHarness`
- `agentHarnessOther` when `agentHarness` is `other`
- `model`
- `skills`
- `tools`
- `helpfulResources`
- `intention`

Optional inside metadata:

- `helpfulSkills`
- `intentionNotes`
- `moltbookPostURL`

## Skynet Submission Draft Notes

Confirmed from this repository:

- Project name: `Skynet by 0xSorcerer`
- Repo should remain public and point to this GitHub repository
- Agent harness: `codex-cli`
- Primary model currently recorded in repo docs: `gpt-5.2-codex`

Do not guess these later:

- `trackUUIDs`
- `teamUUID`
- final `description`
- final `problemStatement`
- exact `skills` list across the full build
- exact `helpfulResources` URLs across the full build
- Moltbook post URL
- deploy URL, video URL, screenshots, and cover image URL

## Honest Metadata Guidance For Skynet

Use this standard when building the final submission payload:

- `skills`: only include skill identifiers that were actually loaded in Codex sessions and materially influenced the build.
- `tools`: include concrete software and platforms visible in the repo or deployment flow, such as FastAPI, Pydantic, pytest, Uvicorn, and any partner tooling actually used.
- `helpfulResources`: include only exact URLs that were opened and consulted. Homepages should be avoided when a specific page was used.
- `helpfulSkills`: only include a skill when we can point to the concrete result it helped produce.
- `intention`: choose the truthful post-hackathon plan. `continuing`, `exploring`, and `one-time` are all acceptable.

## Self-Custody Procedure

1. Call `/participants/me/transfer/init` with the target wallet.
2. Compare the returned `targetOwnerAddress` against the intended wallet address.
3. Only then call `/participants/me/transfer/confirm` with the same `transferToken` and `targetOwnerAddress`.
4. Confirm the response shows `custodyType: "self_custody"`.
5. Repeat until every team member is in self-custody.

Solo-team note:

- If the only team member already registered and minted the required NFT into the intended owner wallet, treat self-custody as satisfied once the platform still shows that same wallet as the owner of record.

## Pre-Publish Checklist

- [ ] Solo owner wallet verified as the publish owner of record, or all team members are self-custody
- [ ] Project name is final
- [ ] Description explains what Skynet does and why it matters
- [ ] Problem statement is specific and grounded
- [ ] Repo URL points to the public codebase
- [ ] Track UUID list is final and complete
- [ ] Conversation log is current and honest
- [ ] Metadata object is complete and honest
- [ ] Moltbook post exists and URL is attached
- [ ] Demo URL is included if available
- [ ] Video URL is included if available
- [ ] Images and cover image are ready if available

## Post-Publish Verification

- [ ] `GET /projects/:projectUUID` returns `status: "publish"`
- [ ] The project appears in `GET /projects`
- [ ] Auto-resolved repo stats are present if the repo is public on GitHub

## Common Failure Modes To Avoid

- Accidentally creating duplicate drafts when you intended to update an existing project (unless intentionally using one of up to 3 allowed projects)
- Publishing before every member completes self-custody
- Replacing `trackUUIDs` with a partial list during update
- Sending partial `submissionMetadata` during update
- Inflating the skills, tools, or helpful resources lists
- Publishing before repo, description, conversation log, and evidence are final
