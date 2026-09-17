# Dependency and framework upgrade review

Use this reference for Python or JavaScript dependency changes, lockfile updates,
runtime/framework upgrades, and dependency security fixes.

## Establish the real change

- Read primary release notes, migration guides, and security advisories for every
  intervening version, not only the target release. Record changed defaults, removed
  or deprecated APIs, runtime requirements, and behavior outside the motivating fix.
- Search the monorepo for affected imports, configuration, extension points, private
  APIs, and transitive packages. A dependency can be used indirectly by plugins,
  generated code, optional images, Storybook, workers, or enterprise modules.
- Verify Python/Node, Django/Nuxt/Vue, browser, database, and deployment-image support
  against the repository's actual versions. Do not infer compatibility from a broad
  semver range alone.
- Inspect the resolved graph: lockfiles contain the intended version and hashes,
  peer/optional dependencies are satisfiable, and unrelated packages did not drift.
  Generate lockfiles with the owning package manager rather than editing them.

## Verify the claimed effect

- Reproduce the old behavior and exercise the upgraded code path through Baserow.
  For a security advisory, model the real attacker and confirm the configured
  application now enforces the boundary; installing a patched version is not proof
  when a permissive Baserow setting can disable its protection.
- Check whether the new default changes public endpoints, parsing, serialization,
  authentication, retries/timeouts, query generation, memory use, or error payloads.
  Load the security, data-performance, or compatibility references when it does.
- Run focused tests plus the smallest startup/build/import smoke test that exercises
  dependency initialization. For frontend frameworks, build the affected Nuxt or
  Storybook target when compile-time behavior changed.
- Confirm production and development images install the same supported dependency
  path, including system libraries or optional extras required only at runtime.

## Keep the PR reviewable

Separate an unrelated bug fix or configuration change unless it is required to make
the upgrade safe. Explain unavoidable lockfile churn and verify licenses or package
sources when a new transitive dependency enters a distributed Baserow artifact.
