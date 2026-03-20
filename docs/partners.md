# Partner Integration Notes

## Active in MVP

### Base

- Used as a supported network label in transaction metadata and report summaries.
- Useful for wallet-origin tax activity because Base documentation includes chain, AI agent, and app-building resources.

Docs: https://docs.base.org/

### Celo

- Supported as a network label in transaction metadata and report summaries.
- Useful for cross-network tax handling and future real-world payment flows.

Docs: https://docs.celo.org/

### MetaMask

- Supported as a wallet-provider signal in imported transaction data.
- This prepares the app for a future wallet connection flow while already improving audit context for CSV imports.

Docs: https://docs.metamask.io/

### Uniswap

- Supported as a protocol signal in imported transaction data.
- Transactions tagged with Uniswap metadata are classified more confidently as swaps.
- LP deposit and LP withdrawal flows are also recognized in the MVP normalization layer.

Docs: https://docs.uniswap.org/

## Planned

### Self

- Deferred for a later UI phase.
- Intended use: identity verification for compliance-sensitive exports or onboarding.
- The current MVP records this as a planned integration and exposes it through the `/partners` catalog.

Docs: https://docs.self.xyz/frontend-integration/qrcode-sdk

## Evidence Layer

- Rule packs now support citation links so official tax authority sources can travel with report output.
- Current MVP citations point at official IRS and HMRC materials where the sample rules make explicit assumptions.
