## Summary

-

## Why

-

## Checks run

- [ ] `bash scripts/check-all.sh`
- [ ] `bash scripts/check-skill-consistency.sh`
- [ ] `bash scripts/check-manifests.sh`
- [ ] `bash scripts/check-portability.sh`
- [ ] `git diff --check`
- [ ] `git diff --cached --check`
- [ ] Not applicable, because:

## Security and compatibility

- [ ] No plugin runtime API, skill invocation syntax, manifest schema, or `/goal`
      behavior changed.
- [ ] Changes to workflows, plugin manifests, validation scripts, or
      `skills/pathfinder/` behavior contracts are called out for reviewer
      attention.
- [ ] No secrets, private paths, `.agent-work/`, or `.agent-workspace/`
      artifacts are included.
- [ ] Security-sensitive files changed and maintainer review is expected.
- [ ] Not applicable, because:

## Notes for reviewers

-
