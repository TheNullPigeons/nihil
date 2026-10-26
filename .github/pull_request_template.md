<!--
Thanks for contributing to nihil!
PRs target `dev`, not `main`. Fill in every section; write "N/A" when one does not apply.
Unfilled PRs, or bug fixes without a reproduced root cause, may be closed without review.
-->

## Summary

<!-- What does this PR change, and why? One or two sentences. -->

Closes #

## Type of change

- [ ] Bug fix
- [ ] New feature
- [ ] Refactor (no behavior change)
- [ ] Docs / CI / tooling
- [ ] Breaking change (existing containers, configs, CLI flags or images behave differently)

## Problem and root cause

<!--
Bug fixes: this section is mandatory.
- How to reproduce it (commands, image, host OS, Docker engine).
- The root cause, and how you confirmed it (logs, inspect output, a minimal repro).
- Why it is a nihil problem and not a local one: you reproduced it on a clean setup
  (fresh container, default config, no other containers or VPN sessions involved)
  and ruled out host-specific settings (MTU, firewall, Docker daemon config, ...).
Features: the use case, and why it belongs in nihil.
-->

**Reproduction:**

**Root cause:**

**Ruled out:**

## Solution

<!-- How does the change fix the problem? Mention alternatives you considered and why you rejected them. -->

## Impact

<!--
- Which commands / code paths are affected (start, restart, upgrade, exec, VPN, X11/Wayland, browser UI, ...)?
- Existing containers: does anything need to be recreated or migrated?
- Hardcoded values (ports, sizes, paths, timeouts): why this value, and does it hold on other setups?
-->

## Testing

<!-- Paste commands and relevant output. "Works on my machine" is not a test plan. -->

- [ ] `pytest` passes locally
- [ ] Tests added or updated for the change (or explained why not)
- [ ] Tested manually with a real container. Image: <!-- e.g. full -->
- [ ] For a bug fix: reproduced the bug before the change and confirmed it is gone after

<details>
<summary>Environment (`nihil doctor --report`)</summary>

<!-- Paste the output of `nihil doctor --report` here. Container, VPN config, user and host names are masked. -->

</details>

<details>
<summary>Output / logs</summary>

```
```

</details>

## Checklist

- [ ] Branch is up to date with `dev`
- [ ] One concern per PR: unrelated changes go in their own PR
- [ ] Commits follow the `type(scope): description` convention (`feat`, `fix`, `chore`, ...)
- [ ] User-facing changes (new flags, behavior, messages) are documented in the README or `--help`
- [ ] No secrets, VPN configs, credentials or personal paths committed
