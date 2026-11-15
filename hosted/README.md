# LocalRSI hosted workspace

A private, invitation-only Sites frontend with a D1-backed outbound RPC queue. The installed backend remains on the owner's compute server and initiates HTTPS connections; no public SSH or inference port is required.

## Data boundaries

- Sites handles sign-in and the invite allowlist. Application routes require the injected user identity.
- Queue records are keyed by the authenticated site user ID. Browser-supplied user IDs are never trusted.
- Each compute-side member gets a separate backend process, task database and workspace. These processes share an OS account; they are not OS sandboxes.
- Shared hosting disables shell execution, test execution, desktop/browser control and arbitrary MCP servers. The private local version retains those capabilities.
- RPC results expire from the queue after 24 hours when subsequent requests run cleanup. Durable files and task records remain on the compute server.
- Claims are atomic. Timed-out actions are not replayed automatically. Publishing a result is idempotent.

## Runtime

`BRIDGE_KEY` is a Sites runtime secret. The compute connector also needs the Site's service-access token; neither credential belongs in source or browser bundles. The connector checks in through `/relay/heartbeat` and claims `/relay/claim` jobs. `/relay/health` is a privileged transport health endpoint.

The shared model is a pre-existing inference service. The JSON tool adapter avoids restarting services that lack native tool-parser flags. Image input is supported only when the backend vision endpoint is configured.

## Validation

- Hosted build succeeds with the Sites Vinext integration preserved.
- Local gateway checks: anonymous denial, wrong worker key denial, authenticated result retrieval, atomic claim, idempotent completion, CSRF rejection.
- Two distinct compute members: separate notes and task IDs; cross-member task lookup returns 404.
- Real existing GPU service: tool-grounded arithmetic returned 391; image inference correctly identified the red square and blue circle in the test image.

Invite additions must be made using the Sites access controls. Keep the site private until the owner supplies the intended members. Test runtime files and credentials are ignored.
