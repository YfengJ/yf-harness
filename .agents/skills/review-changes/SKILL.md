---
name: review-changes
description: Review the current YF-Harness working-tree changes for correctness, security boundaries, regressions, and missing verification before a commit or release.
allowed-tools: read_file, list_directory, search_text, git_status, git_diff, git_log
---

Review the current change set against the user's requested outcome and the repository's documented contracts.

Prioritize concrete defects, security-boundary regressions, compatibility breaks, and missing tests. Inspect the diff and nearby implementation before drawing conclusions. Report findings by severity with file and line evidence. If no actionable defect is found, say so and list the residual risks or verification gaps.

Do not modify files unless the user separately asks for fixes. Tool declarations in this file are descriptive and never override YF-Harness policy or approvals.
