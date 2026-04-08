# Copilot Review & Auto-Apply Policy

Purpose
- Ensure GitHub Copilot's pull request review suggestions are considered and, when safe, automatically applied to speed up review and maintain quality.

Policy
- All PRs should consider suggestions made by GitHub Copilot for Pull Requests.
- The repository will attempt to automatically apply Copilot 'suggestion' blocks to the PR branch via a GitHub Action. This action:
  - Runs on PR open/synchronize events
  - Attempts to apply ` ```suggestion ... ``` ` blocks authored by Copilot or present in PR review comments
  - Commits and pushes applied changes back to the PR branch
  - Posts a comment summarizing applied/skipped suggestions
- If any suggestions cannot be applied automatically, the Action will post a comment listing the skipped suggestions and fail the verification step. Maintainers or the PR author must address remaining suggestions.

Exceptions
- Suggestions that conflict with explicit project specifications or tests should NOT be applied. The automation will skip ambiguous cases and surface them for manual review.

Enforcement
- A GitHub Action (`.github/workflows/copilot-auto-apply.yml`) implements the automation and verification. Make this check required in branch protection rules if you want strict enforcement.

Notes
- Enabling Copilot for the repository is done via the GitHub repository settings (administrators only). This automation does not enable Copilot itself.

If you have questions or want to change the behavior (e.g., more/less aggressive heuristics), open an Issue or discuss in the PR.