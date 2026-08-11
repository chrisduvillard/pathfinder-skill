# Goal

/goal Fix the dashboard empty state with regression proof

# Implementation Goal

Fix the dashboard empty state with regression proof

# Goal Binding

- binding_id: binding_fixture01
- mission_id: mission_fixture01
- goal_id: goal_fixture0001
- objective_source: selected-candidate
- selected_candidate_ids: C1
- intent_snapshot:
  - charter: version 1, sha256 aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
  - roadmap: version 1, sha256 aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
  - doctrine: version 1, sha256 aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
- capability_profile:
  - controller: available
  - native_goal: available
- scope:
  - repository_id: fixture-repo
  - scoped_root: .
  - base_commit: bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb
  - dirty_policy: block
  - fingerprint: aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
- proof_requirements:
  - npm test exits 0
  - regression test fails before and passes after
- protected_surfaces: none
- runtime_boundary_required: false
- budgets:
  - max_goals: 1
  - max_attempts_per_goal: 2
  - max_wall_seconds: 3600
  - max_open_prs: 0
  - max_total_prs: 0
- created_at: 2026-08-10T12:02:00Z
