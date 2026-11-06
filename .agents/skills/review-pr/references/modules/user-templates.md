# User templates module review

Use this reference for changes to user templates: their publishing, admin review,
access, install or download, under `backend/src/baserow/core/user_templates`, the
template models and views, `web-frontend/modules/core/components/template` and
`web-frontend/modules/core/components/admin/templates`, and their tests.

## Evidence that fits the change

Use the rows of the areas the change touches in
`docs/testing/user-templates-test-plan.md`; do not mechanically run its entire
matrix. A changed rule must change those rows and the tests named by their ids.
