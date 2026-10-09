# Test into Dev merge resolution

Baseline: Dev `f4bfb9b`. Source: Test `7337f86`.

The working Dev application takes precedence where Test changes overlap its newer behavior.

- Keep Dev's query gateway, authentication, conversation threads, routing, audit metadata, and Digital Twin commands unchanged.
- Keep every existing frontend file unchanged, including App, shared chat components, artifact panel, animations, global styles, and package manifests.
- Retain Test's new fulfillment dashboard, scene, parser, card, toast, and image as standalone assets. They are deliberately not connected to current navigation, so existing screens keep their behavior and appearance.
- Retain additive order item compatibility accessors and nullable delay tracking fields with startup column migrations. Preserve Dev's chat models.
- Retain recorded delay explanations and structured inventory checks. Match inventory by SKU and preserve Dev's text fallback when a quantity is missing; never infer zero stock from an unrelated zero in response text.
- Preserve Dev's seed script, existing coordinator/integration tests, and all tracked Chroma database files. Do not run migrations or seed scripts against the user's database during validation.

Recovery branch: `backup/dev-before-test-merge-20261009`.

Validation uses isolated SQLite and Chroma data. The backend suite passes with 445 tests passed and 17 skipped. Frontend production build and 73 frontend tests pass. New standalone frontend components also bundle successfully.
