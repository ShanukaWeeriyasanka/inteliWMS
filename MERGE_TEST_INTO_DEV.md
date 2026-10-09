# Test into Dev merge resolution

Baseline: Dev `f4bfb9b`. Source: Test `7337f86`.

The working Dev application takes precedence where Test changes overlap its newer behavior.

- Keep Dev's query gateway, authentication, conversation threads, routing, audit metadata, and Digital Twin commands unchanged.
- Preserve Dev's conversation state, Markdown rendering, map commands, security controls, global styles, and package manifests when integrating the fulfillment UI.
- Connect Test's fulfillment dashboard and scene to the sidebar's Order Fulfillment entry and fulfillment chat replies. Keep the selected reply in the conversation URL so refresh and browser Back preserve navigation. Fulfillment details also survive saved history reloads.
- Retain additive order item compatibility accessors and nullable delay tracking fields with startup column migrations. Preserve Dev's chat models.
- Retain recorded delay explanations and structured inventory checks. Match inventory by SKU and preserve Dev's text fallback when a quantity is missing; never infer zero stock from an unrelated zero in response text.
- Preserve Dev's seed script, existing coordinator/integration tests, and all tracked Chroma database files. Do not run migrations or seed scripts against the user's database during validation.

Recovery branch: `backup/dev-before-test-merge-20261009`.

Merge validation used isolated SQLite and Chroma data: 445 backend tests passed and 17 skipped. After UI integration, the frontend production build and 76 frontend tests pass. Browser checks with mocked API responses verify the dashboard action, saved metadata, warehouse scene, refresh, Back, sidebar navigation, Escape, mobile layout, and preserved Markdown rendering without browser errors.
