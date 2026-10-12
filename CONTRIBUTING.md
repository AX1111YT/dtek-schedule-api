<!-- Copyright 2026 AX1111YT | SPDX-License-Identifier: Apache-2.0 -->

# Contributing

Thanks for helping improve DTEK Schedule API. Bug reports, documentation fixes, and focused code changes are welcome.

## Questions and issue reports

Search existing [issues](https://github.com/AX1111YT/dtek-schedule-api/issues) before opening a new one. For a bug report, include:

- The release or commit, and whether you ran it with Python or Docker.
- Your operating system and Python version when relevant.
- Steps to reproduce, expected behavior, and actual behavior.
- Relevant sanitized logs or responses.

Do not post API keys, credentials, or a full private address in a public issue. When reporting an upstream DTEK change, include the affected endpoint or page and the time you observed it; remove tokens and personal details from any captured response.

For feature proposals, describe the user need and how the change would fit the API's existing behavior. Use the issue tracker for both bug reports and feature requests.

## Development

Use Python 3.11 or newer and `uv`. Follow the Python setup in the [README](README.md), and copy `.env.example` to `.env` before starting the service.

Keep changes focused and the runtime lightweight. Upstream requests belong in `dtek_client.py`, response parsing in `normalization.py`, schedule orchestration in `service.py`, and HTTP behavior in `routes.py` and `main.py`. Update the README or environment example when a change affects API behavior or configuration.

There is not currently an automated test suite. For behavior changes, include focused regression coverage where practical. In your pull request, describe the checks or manual steps you used to verify the change; do not include real credentials or private addresses in fixtures.

## Pull requests

Use a descriptive branch name and keep the pull request limited to one topic. Explain the reason for the change, summarize its user-visible effects, and link related issues. Call out any API or configuration changes and include the verification performed.

By submitting a contribution, you confirm that you have the right to submit it. Contributions intentionally submitted for inclusion are provided under the project's Apache License 2.0, consistent with its terms.

## Security reports

Do not report security vulnerabilities in a public issue. Send them to [AX1111YT@proton.me](mailto:AX1111YT@proton.me) with enough detail to reproduce the issue. Avoid including live credentials or personal address information.

Participation in the project is subject to the [Code of Conduct](CODE_OF_CONDUCT.md).
