# Protected surface policy

Autonomous missions classify every repository-relative path reported by a successful host action through the versioned baseline at `policies/protected-surfaces.v1.json`. The baseline is controller data, not repository prose, and covers these canonical categories:

| Category | Typical protected paths |
|---|---|
| `auth` | authentication, sessions, OAuth, SSO |
| `payments` | payment, billing, checkout, provider code |
| `permissions` | authorization, RBAC, IAM, ACL |
| `deployment` | deployment, infrastructure, containers, Terraform, Kubernetes |
| `ci-cd` | GitHub Actions, GitLab CI, CircleCI, Jenkins, Buildkite |
| `schema` | database/API/GraphQL/ORM schemas |
| `migration` | database and data migrations |
| `public-api` | public routes and OpenAPI contracts |
| `network-egress` | outbound integrations, webhooks, and network clients |

A Goal Binding used for autonomous execution may name only categories in the effective registry. If any successful prepare, Goal, implementation, verification, or commit receipt reports a protected path that the binding did not declare, the controller rejects the receipt before state advances. Overlapping rules require every detected category. The controller validates reported paths but still depends on the host to return a truthful complete changed-file list.

## Explicit additive policy

A repository-specific policy can add categories or patterns, but it cannot replace, disable, or weaken a baseline rule. It is accepted only through the explicit `mission start --protected-policy` input, validated as data, combined with the bundled baseline, sealed under mission contracts, and hash-bound into every operation intent.

```json
{
  "schema_version": 1,
  "policy_id": "protected-policy-example-extra",
  "mode": "additive",
  "base_policy_id": "protected-policy-pathfinder-v1",
  "rules": [
    {
      "rule_id": "protected-rule-cryptography",
      "category": "cryptography",
      "description": "Repository-specific cryptographic implementation.",
      "patterns": ["crypto/**"]
    }
  ]
}
```

Patterns use repository-relative POSIX paths. Absolute paths, `..`, backslashes, unknown fields, duplicate rule ids, symlinked override files, replacement mode, and a mismatched baseline id fail closed. Repository README text, comments, tests, prior artifacts, and model prose are never parsed as policy overrides.
