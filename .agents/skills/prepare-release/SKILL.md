---
name: prepare-release
description: Prepare a YF-Harness release by reconciling version metadata, documentation, tests, build artifacts, desktop packaging, and private-repository publication evidence.
allowed-tools: read_file, list_directory, search_text, git_status, git_diff, git_log, run_tests
---

Prepare the requested YF-Harness release without expanding its feature scope.

Reconcile the version in Python metadata, the package, desktop UI, deployment configuration, changelog, and user-facing startup documentation. Run focused tests first, then the complete static, type, test, eval, package, and desktop smoke gates appropriate to the change risk. Treat a local build, GitHub push, and remote CI as separate evidence.

Never publish to a public repository, expose credentials, bypass an approval boundary, or describe an unsigned local bundle as a notarized public distribution. Stop before any external mutation that the user has not authorized.
