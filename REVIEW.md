# PR #5546 review follow-up

Proposed fixes for Paljor's September 11, 2026 review of
[PR #5546](https://github.com/baserow/baserow/pull/5546).
Completed items are checked below.

- [x] **Fix the Table crash when selecting a grouped data source.**
  [Review comment](https://github.com/baserow/baserow/pull/5546#discussion_r3986917706)

  `getDefaultCollectionFields()` exists only on
  `LocalBaserowListRowsServiceType`; the grouped service does not inherit it.
  Extract reusable schema-to-table-column logic and support it on the grouped
  service. Generate columns for grouping fields and aggregate results, excluding
  the synthetic `id`. Use aggregate result types rather than source-field types:
  counting a boolean field, for example, produces a number.

  Validate selecting this data source in a Table and the generated column formulas.

- [x] **Prevent editing one data source from temporarily replacing another.**
  [Review comment](https://github.com/baserow/baserow/pull/5546#discussion_r3987079496)

  The likely cause is `getFormValues()` flattening child series values into the
  parent payload, leaking a series' `id` into the data source's top-level `id`.
  The store also calls `splice(index, ...)` without guarding against
  `index === -1`, which replaces the last item.

  Keep series values exclusively inside `aggregation_series`, restrict the
  top-level payload to allowed service fields, and guard missing store entries.
  Reproduce the reviewer's three-source scenario in a regression test, including
  adding and editing a series.

- [x] **Fix the backend crash when grouping by a multiple-select field.**
  [Review comment](https://github.com/baserow/baserow/pull/5546#discussion_r3987126814)

  Temporary fix requested: disable Row ID grouping when the primary field is
  multi-valued. The shared Builder/Dashboard selector disables the option, and
  backend configuration and dispatch reject it with a controlled error.
  The broader grouping implementation was saved on a separate branch.

- [x] **Restore the Dashboard chart filter input.**
  [Review comment](https://github.com/baserow/baserow/pull/5546#discussion_r3987170590)

  Dashboard widget settings now provide `DashboardFormulaInput`, with shared
  runtime functions and no data providers (Dashboard has none registered).
  Regular filter inputs and formula mode are supported.

  Two passing regression tests cover opening standard/pie chart filters,
  editing values, saving/reloading through a mocked API, and switching modes.
  The backend update serializer receives Dashboard application context, with an
  empty provider registry. All 32 data-source API tests pass, including formula
  validation, saving/reloading, and aggregate/chart dispatch in each input mode.

- [x] **Correct the upgrade plan label and track pricing-copy follow-up.**
  [Review comment](https://github.com/baserow/baserow/pull/5546#discussion_r3987489628)

  The shared grouped-aggregation feature now displays Advanced, the minimum
  required plan. Enterprise also includes it through `COMMON_ADVANCED_FEATURES`.
  Existing shared Advanced labels and the SaaS paid-feature overrides confirm
  that no deployment-specific label override is needed.

  Modal tests cover the Advanced sidebar grouping and upgrade description with
  and without a workspace. These exercise the shared modal, not a running SaaS
  deployment. Separate SaaS integration and website follow-ups are tracked below.

- [x] **Remove duplicate result-property naming logic from Chart.vue.**
  [Review comment](https://github.com/baserow/baserow/pull/5546#discussion_r3987624839)

  Delegated `getResultPropertyName()` to
  `this.serviceType.getResultPropertyName(this.dataSource, propertyName)` so the
  service type owns the naming rules. All 9 existing Chart component tests pass,
  including chart-label coverage. Targeted frontend formatting and lint pass.

## Separate follow-ups

- [ ] **SaaS integration:** add `BUILDER_GROUPED_AGGREGATE_ROWS` to the SaaS
  `AdvancedLicenseType.features` list when integrating this branch, and verify
  Advanced/Enterprise access and the upgrade modal in a running SaaS deployment.
  The local SaaS checkout has its own explicit list and does not yet include it.
- [ ] **Website pricing content:** distinguish free/base data sources from grouped
  aggregation (Advanced and Enterprise). Suggested copy: “Base data sources” for
  Free and “Grouped aggregation data source” for Advanced/Enterprise. The live
  [pricing page](https://baserow.io/pricing) already says “Base data sources” as of
  September 14, 2026; confirm that both Cloud and Self-host comparisons explicitly
  communicate grouped aggregation availability. Website content was not edited.
