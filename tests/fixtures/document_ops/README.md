# Document Ops Spike Fixtures

These fixtures are synthetic contractor invoice reconciliation samples for
GitHub issue #44.

- Source: manually generated synthetic data for NeedRadar development.
- Generated date: 2026-06-26.
- Privacy: no real customer documents, personal data, bank details, invoices, or
  commercially sensitive materials are included.
- Network policy: automated tests must read these local files only and must not
  download live samples.

Each case contains:

- `reference.csv`: fictional contract / schedule of rates baseline.
- `invoice.csv`: fictional contractor invoice / payment application to review.

The rows intentionally contain missing items and rate, quantity, or amount
differences so the spike can prove deterministic exception handling.
