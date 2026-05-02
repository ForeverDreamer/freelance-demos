# Sample invoices (placeholder)

This sketch does not ship sample PDFs. To exercise the parser locally
once you build out the runtime, use one of these public sources:

- **[DocILE](https://docile.rossum.ai/)** — research dataset of European
  business invoices, useful for English / German / Czech / Slovak
  layouts. License: CC BY-NC-SA 4.0 (research / internal evaluation
  only; not for redistribution as a product).
- **[CORD](https://huggingface.co/datasets/naver-clova-ix/cord-v2)** —
  receipts (not invoices) but useful for low-quality OCR routing tests.
  License: CC BY 4.0.
- **Self-generated mocks** — LibreOffice or any invoice template tool
  can produce a multilingual mock (Latvian / Russian diacritics, etc.)
  without licensing concerns.

## Why no PDFs in the repo

This is a public sketch. Bundling third-party invoices, even from
permissive datasets, raises license-compliance questions for downstream
users who fork. Easier to point at the source.

## What the paid build ships

The paid build comes with a curated golden set covering: 6 EU languages,
3 quality tiers (clean PDF / scanned / handwritten field), and 4
doctypes (invoice / receipt / contract / purchase order). Each example
has a hand-checked expected JSON for regression testing.
