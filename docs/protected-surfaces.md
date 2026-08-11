# Protected surface policy

Autonomous missions classify every repository-relative path reported by a successful host action through the versioned baseline at `policies/protected-surfaces.v1.json`. The baseline is controller data, not repository prose, and covers these canonical categories:

<!-- pathfinder:generated:protected-surfaces:v1:begin -->
<!-- Generated from policies/protected-surfaces.v1.json; run `python3 scripts/render_protected_surfaces.py .` to refresh. -->

| Category | Description | Canonical path patterns |
|---|---|---|
| <code>auth</code> | Authentication, session, SSO, and OAuth implementation. | <code>auth/**</code><br><code>authentication/**</code><br><code>oauth/**</code><br><code>sso/**</code><br><code>auth.py</code> |
| <code>payments</code> | Payment, billing, checkout, and payment-provider implementation. | <code>payment/**</code><br><code>payments/**</code><br><code>billing/**</code><br><code>checkout/**</code><br><code>stripe/**</code><br><code>paypal/**</code> |
| <code>permissions</code> | Authorization, permissions, role, and access-control implementation. | <code>authorization/**</code><br><code>permission/**</code><br><code>permissions/**</code><br><code>rbac/**</code><br><code>iam/**</code><br><code>acl/**</code> |
| <code>deployment</code> | Deployment and infrastructure configuration. | <code>deploy/**</code><br><code>deployment/**</code><br><code>infra/**</code><br><code>infrastructure/**</code><br><code>terraform/**</code><br><code>k8s/**</code><br><code>kubernetes/**</code><br><code>helm/**</code><br><code>Dockerfile*</code><br><code>docker-compose*.yml</code><br><code>docker-compose*.yaml</code><br><code>*.tf</code><br><code>*.tfvars</code> |
| <code>ci-cd</code> | Continuous integration and delivery configuration. | <code>.github/workflows/**</code><br><code>.circleci/**</code><br><code>.gitlab-ci.yml</code><br><code>Jenkinsfile</code><br><code>azure-pipelines.yml</code><br><code>.buildkite/**</code><br><code>buildkite/**</code> |
| <code>schema</code> | Database, API, GraphQL, and ORM schema definitions. | <code>schema/**</code><br><code>schemas/**</code><br><code>*.graphql</code><br><code>*.gql</code><br><code>*.prisma</code><br><code>openapi*.yaml</code><br><code>openapi*.yml</code> |
| <code>migration</code> | Database and data migration implementation. | <code>migration/**</code><br><code>migrations/**</code><br><code>alembic/**</code><br><code>db/migrate/**</code> |
| <code>public-api</code> | Public API routes and contracts. | <code>api/public/**</code><br><code>public-api/**</code><br><code>routes/public/**</code><br><code>openapi*.yaml</code><br><code>openapi*.yml</code> |
| <code>network-egress</code> | Outbound integrations, webhooks, and network clients. | <code>egress/**</code><br><code>outbound/**</code><br><code>http-client/**</code><br><code>integration/**</code><br><code>integrations/**</code><br><code>webhook/**</code><br><code>webhooks/**</code> |
<!-- pathfinder:generated:protected-surfaces:v1:end -->

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
