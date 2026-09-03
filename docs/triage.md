# Issue triage

The desired label taxonomy is tracked in `.github/labels.yml`; it must be
applied and verified in GitHub before cutover. New reports begin with
`needs: triage`. Maintainers reproduce and classify them, request missing safe
evidence, then remove that label.

- `type: bug` is observed incorrect behavior.
- `type: proposal` changes player experience or direction.
- `area: accessibility`, `area: content-pack`, and `area: art-audio` route
  specialist review.
- `good first issue` is used only after direction is accepted, scope is bounded,
  dependencies are identified, and acceptance evidence is written.
- `needs: maintainer-decision` marks canon, compatibility, rights, release, or
  architecture choices that contributors cannot settle by vote.

Security reports never enter public triage. Duplicate issues retain a link to
the canonical report. Closing a proposal means only that it is not accepted for
the current direction; it is not a judgment on the contributor.
