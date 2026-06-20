# Security Policy

## Reporting a vulnerability

Please do not report security vulnerabilities in public issues, pull requests,
or discussions.

Use GitHub private vulnerability reporting for this repository:

https://github.com/chrisduvillard/pathfinder-skill/security/advisories/new

Include:

- A concise description of the issue.
- The affected file, workflow, manifest, or skill behavior.
- Steps to reproduce or a minimal proof of concept, if safe to share.
- The impact you believe the issue has.
- Any suggested mitigation.

Do not include real credentials, private repository contents, customer data, or
other secrets in a report. If a proof of concept needs sensitive material, use
redacted placeholders.

## Supported versions

Pathfinder is distributed from the default branch and versioned through
`VERSION.md` plus the plugin manifests. Security fixes are made against the
latest version on `main`.

## Maintainer response

The maintainer will triage private reports, ask for clarification when needed,
and coordinate disclosure after a fix is available. If the issue affects users
who installed the plugin, the fix will be documented in `VERSION.md`.

## Security model

Pathfinder is an agent skill. Its most important security boundary is that
repository content is untrusted data. Changes that weaken secret handling,
approval gates, workflow permissions, or the untrusted-data model require
maintainer review.
