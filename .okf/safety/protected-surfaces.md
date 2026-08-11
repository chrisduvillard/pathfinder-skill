---
type: Policy Registry
title: Protected surfaces
description: A versioned baseline classifies sensitive repository paths and permits explicit policy only to add protection.
resource: ../../policies/protected-surfaces.v1.json
tags: [pathfinder, policy, protected-surfaces, safety]
status: stable
generated: { by: codex/gpt-5, at: "2026-08-11T20:01:42Z" }
stale_after: "2026-11-09"
sources:
  - id: policy-json
    resource: https://github.com/chrisduvillard/pathfinder-skill/blob/26e7912ffcf690ef3f956fab7a098bbaffefddf0/policies/protected-surfaces.v1.json
    title: Protected-surface baseline policy
    author: human:chris-duvillard
    last_modified: "2026-08-11"
  - id: registry-source
    resource: https://github.com/chrisduvillard/pathfinder-skill/blob/26e7912ffcf690ef3f956fab7a098bbaffefddf0/pathfinder_core/protected_surfaces.py
    title: Protected-surface registry source
    author: human:chris-duvillard
    last_modified: "2026-08-11"
  - id: protected-doc
    resource: https://github.com/chrisduvillard/pathfinder-skill/blob/26e7912ffcf690ef3f956fab7a098bbaffefddf0/docs/protected-surfaces.md
    title: Protected-surface policy documentation
    author: human:chris-duvillard
    last_modified: "2026-08-11"
---

# Baseline Categories

The baseline registry protects nine categories using repository-relative glob rules.[^policy-json]

| Category | Covered examples |
|---|---|
| `auth` | Authentication, sessions, SSO, OAuth |
| `payments` | Billing, checkout, payment providers |
| `permissions` | Authorization, roles, access control |
| `deployment` | Infrastructure, containers, Terraform, Kubernetes |
| `ci-cd` | CI and delivery configuration |
| `schema` | Database, API, GraphQL, ORM schemas |
| `migration` | Database and data migrations |
| `public-api` | Public routes and API contracts |
| `network-egress` | Integrations, clients, webhooks, outbound traffic |

# Additive Policy

A repository-specific policy must declare additive mode and name the exact baseline policy id. The registry combines baseline and additive rules, rejects duplicate rule ids, validates the effective document, and derives a content hash. An override can add protection but cannot remove or weaken the baseline.[^registry-source]

# Runtime Use

Goal Bindings may name only known categories. After every successful host action, the [mission controller](/runtime/mission-controller.md) classifies receipt `changed_files`; touching a protected category absent from the binding stops the mission before the receipt is accepted as an advancing result.[^protected-doc]

This registry is one layer inside the broader [runtime trust boundary](/safety/trust-boundary.md).

[^policy-json]: Protected-surface baseline policy.
[^registry-source]: Protected-surface registry source.
[^protected-doc]: Protected-surface policy documentation.
