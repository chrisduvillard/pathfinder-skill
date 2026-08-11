# Pathfinder Adaptive Strategies

Pathfinder adaptive strategies are default policies, not permanent claims about how a model must think.
They let Pathfinder benefit from future model improvements by turning fixed human taxonomies into
search, evaluation, and value-of-information decisions.

## Candidate search

- Treat the five scout domains and Top 5 list as defaults. A run may inspect fewer, more, or different
  domains when repo evidence supports that choice.
- Record selected and skipped domains once in the discovery map. Persist compact briefs only for
  selected domains; expanded scout narrative is optional and must earn its artifact cost.
- Candidate count is variable. Continue search while expected useful information is high; stop when
  additional candidates are low value, repetitive, unsafe, or outside the user's scope.
- Rank candidates by structured evidence, expected value, risk, proof availability, model uncertainty,
  and creator-model alignment. Evidence bands still prevent weakly grounded work from outranking
  confirmed high-value work.
- Record search decisions in `03-candidates.json` so future replay and eval layers can learn which
  routes were useful.

## Question policy

- Ask questions by value-of-information: ask only when the answer can change goal choice, scope,
  proof, safety classification, authorization, or stop conditions.
- The 8 to 12 Doctrine Interview screens and the 3 to 6 option rule are default UX bounds, not a
  requirement to ask low-value questions. A stronger model may use an adaptive-short-path when the
  artifacts still satisfy all contracts.
- Every skipped question must be justified in `04-question-funnel.md` and, when relevant, in the
  structured sidecar.

## Verification and review

- Use adaptive verifier depth. Low-risk, well-grounded interactive work may use cheap deterministic
  checks; autonomy-bound, protected, high-risk, contested, or low-confidence work uses the full
  adversarial panel and diff-grounded safety gates.
- Reviewer choice is capability-based. Cross-Model Review selects the best available capability
  profile for the review packet rather than assuming a fixed opposite-model pair.
- Any adaptive shortcut is invalid if it omits Goal Binding, Runtime Boundary, Binding Status,
  proof requirements, protected-area status, or safety-stop evidence.
