# User Templates Test Plan

User templates move through many states: private, in review, rejected, public,
blocked, marked for deletion, and combinations of those across their revisions.
The rules of publishing, review and access depend on that state. Areas 1 to 6
each have one table test that runs every row of its table and checks what
happens, from the rows of the templates after the action. Areas 1 and 4 also
check that the user was told what would happen. The rest of the feature is
tested per case, see [Other Coverage](#other-coverage).

A row id is `<area>.<revision states>`. The test param id adds the columns that
pick the cell, like `test_admin_is_shown_what_a_review_does[4.public+rejected-reject]`:

| Area | Param id                                   | Example                        |
| ---- | ------------------------------------------ | ------------------------------ |
| 1    | `<row>-<make_public or update>-<approval>` | `1.public-update-approval_on`  |
| 2, 5 | `<row>`                                    | `2.public+in_review`           |
| 3    | `<row>-<owner, user, anonymous or admin>`  | `3.public+in_review-owner`     |
| 4    | `<row>-<approve or reject>`                | `4.public+rejected-reject`     |
| 6    | `<row>-<case>-<the review>`                | `6.private-seen_public-reject` |

When a rule changes, change the row here, in the test, and in the web-frontend
specs of area 7 that copy it. Each area runs the states its rule depends on,
see the line under its heading. When a new state is added, add it to every
area whose line it falls under.

## Areas

| Area | Domain                             | Test                                                                                                                                                                                                                                                                    |
| ---- | ---------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1    | Owner makes public or updates      | `test_owner_is_told_whether_a_change_goes_to_review` in `backend/tests/baserow/core/user_templates/test_user_template_publishing.py`                                                                                                                                    |
| 2    | Owner makes private                | `test_make_private_withdraws_from_review` in `backend/tests/baserow/core/user_templates/test_user_template_publishing.py`                                                                                                                                               |
| 3    | Who opens, installs and downloads  | `test_actor_gets_what_it_is_shown` in `backend/tests/baserow/core/user_templates/test_user_template_access.py`                                                                                                                                                          |
| 4    | Admin review page                  | `test_admin_is_shown_what_a_review_does` in `backend/tests/baserow/api/admin/templates/test_templates_admin_views.py`                                                                                                                                                   |
| 5    | Admin switches approval off        | `test_switching_approval_off_approves_like_an_admin` in `backend/tests/baserow/core/user_templates/test_user_template_review.py`                                                                                                                                        |
| 6    | Stale views and concurrency        | `test_refused_review` in `backend/tests/baserow/core/user_templates/test_user_template_review.py`, and the tests listed in the area, also in `test_user_template_publishing.py` and `test_settings_views.py`                                                            |
| 7    | What the web-frontend shows        | The specs listed in the area                                                                                                                                                                                                                                            |
| 8    | Private link                       | `test_allow_if_template_permission_manager_allows_openable_templates` in `backend/tests/baserow/core/test_basic_permissions.py`, `test_user_template_private_link.py`, and the private link tests in `backend/tests/baserow/api/templates/test_user_templates_views.py` |
| 9    | Admin management of every template | Not built yet, #6322                                                                                                                                                                                                                                                    |
| 10   | Blocking a template                | Not built yet, #6324. Blocked rows set `blocked_at` in the database, there's no Block action yet                                                                                                                                                                        |

## Revision States

The states of the revisions of a template, oldest first, joined by `+`. The
first revision is the template itself. `public+in_review` is a listed template
with an edit in review.

| State                | Meaning                                                                                              |
| -------------------- | ---------------------------------------------------------------------------------------------------- |
| `private`            | Never submitted.                                                                                     |
| `shared`             | Has a shared revision, which opens with the token of its private link only, see area 8.              |
| `public`             | Approved and listed for everybody.                                                                   |
| `in_review`          | Submitted, waiting for an admin. `rejected+in_review` is a new revision submitted after a rejection. |
| `rejected`           | Rejected by an admin, with a reason.                                                                 |
| `resubmitted`        | The rejected revision itself submitted again. Its rejection stays open until it's approved.          |
| `withdrawn_rejected` | Rejected, then withdrawn by its owner by making it private.                                          |
| `blocked`            | Blocked by an admin. Set in the database, there's no Block action yet.                               |
| `public_blocked`     | Listed, then blocked.                                                                                |
| `marked`             | Marked for deletion by its owner, purged after the grace period.                                     |
| `pruned`             | Not a revision: the previous revision's content was pruned.                                          |

`blocked`, `public_blocked` and `marked` apply to the whole template. After the
first revision, `blocked` and `marked` add an unsubmitted revision, so `rejected+blocked` is a
rejected revision, then an edit, of a blocked template.

An actor **opens** a revision when they can see it on the template page or in
the admin preview. Install and download also need the actor to own the
template or the revision to be listed: the admin preview only opens.

## What Every Row Checks

These hold in every row, so a row only states its outcome.

- **Area 1:**
    - At most one revision of a template is in review: its latest.
    - Earlier revisions are at most withdrawn from review.
    - Reject reasons are kept, because they keep a rejection open.
    - The listed revision stays listed while an edit is in review.
    - A listed revision is approved.
    - The answer the owner is told ("goes to review") is the same from the
      annotated list query and from a single row.
- **Area 2:** nothing is listed afterwards.
- **Area 3:**
    - The template page only shows a revision the actor opens.
    - An install only copies a revision the actor opens.
    - A download is refused exactly when an install is.
    - Install and download jobs requested earlier check again when they start,
      with the same answer. Not for anonymous users, who can't request them.
- **Area 4:**
    - A template is on at most one tab, and the counts equal the tab lengths.
    - The admin opens exactly the listed revision and the revision of its row.
    - A review only changes the reviewed revision and the listing of its
      template.
    - The review response is the template's row in its new tab.
- **Area 5:** switching approval off changes a template exactly as an admin
  approving it would.

## 1. Owner Makes Public Or Updates

Runs the states of area 3 but those marked for deletion, which the owner can't
change since they're deleted, plus more edits in review and a blocked
rejection.

Outcomes: `listed` at once, sent to `review`, an unsubmitted `draft`, or
`unchanged`. The owner is told it goes to review exactly when the outcome is
`review`, and is offered to make it public (`can_make_public`) exactly when the
make public outcome isn't `unchanged`.

| Id                   | Make public, approval off | Make public, approval on | Update, approval off | Update, approval on |
| -------------------- | ------------------------- | ------------------------ | -------------------- | ------------------- |
| 1.private            | listed                    | review                   | draft                | draft               |
| 1.shared             | listed                    | review                   | draft                | draft               |
| 1.in_review          | unchanged                 | unchanged                | review               | review              |
| 1.resubmitted        | unchanged                 | unchanged                | review               | review              |
| 1.private+in_review  | unchanged                 | unchanged                | review               | review              |
| 1.rejected           | review                    | review                   | draft                | draft               |
| 1.rejected+private   | review                    | review                   | draft                | draft               |
| 1.withdrawn_rejected | review                    | review                   | draft                | draft               |
| 1.public             | unchanged                 | unchanged                | listed               | review              |
| 1.public+private     | listed                    | review                   | listed               | review              |
| 1.rejected+public    | unchanged                 | unchanged                | listed               | review              |
| 1.public+in_review   | unchanged                 | unchanged                | listed               | review              |
| 1.public+rejected    | review                    | review                   | review               | review              |
| 1.public+resubmitted | unchanged                 | unchanged                | review               | review              |
| 1.blocked            | unchanged                 | unchanged                | draft                | draft               |
| 1.public_blocked     | unchanged                 | unchanged                | draft                | draft               |
| 1.rejected+blocked   | unchanged                 | unchanged                | draft                | draft               |
| 1.blocked+in_review  | unchanged                 | unchanged                | review               | review              |

- A rejection is reviewed again, even with approval off.
- An update of a template in review moves the review to the new revision.
- A blocked template in review stays in review, for when it's unblocked.

## 2. Owner Makes Private

Runs `private`, `public`, `public+private`, `rejected+public`, `in_review`,
`rejected`, `rejected+private`, `withdrawn_rejected`, `public+in_review` and
`public+rejected`: a listing, a review and a rejection to withdraw, alone and
together. Nothing is listed afterwards.

| Id                   | Unlisted   | Withdrawn from review | Recorded in the audit log |
| -------------------- | ---------- | --------------------- | ------------------------- |
| 2.private            | none       | none                  | nothing                   |
| 2.public             | revision 0 | none                  | revision 0                |
| 2.public+private     | revision 0 | none                  | revision 0                |
| 2.rejected+public    | revision 1 | none                  | revision 1                |
| 2.in_review          | none       | revision 0            | revision 0                |
| 2.rejected           | none       | revision 0            | revision 0                |
| 2.rejected+private   | none       | revision 0            | revision 0                |
| 2.withdrawn_rejected | none       | none                  | nothing                   |
| 2.public+in_review   | revision 0 | revision 1            | revision 0                |
| 2.public+rejected    | revision 0 | revision 1            | revision 0                |

- The audit log records the listed revision, otherwise the withdrawn one.
- The author's edit since a rejection was never submitted, so
  `2.rejected+private` withdraws the rejected revision.

## 3. Who Opens, Installs And Downloads

Runs each single-revision state, and each edit after a revision that changes
what is opened, shown or installed.

Cells are `opens:shown:installs` by revision index, `-` for none:

- **opens:** the revisions the actor opens.
- **shown:** the revision the template page shows.
- **installs:** the revision an install copies.

Anonymous cells are `opens:shown`: an anonymous user can't install or download,
so no job is requested.

A download goes like an install. "Listed" is whether the template browser lists
it for everybody.

For example, `01:1:0` for the owner of `3.public+in_review` means: the owner
opens both revisions, the template page shows them their edit in review
(revision 1), and an install copies the listed revision (revision 0). `0:-:-`
for an admin of `3.in_review` means: the admin opens the revision in review
from the admin page, but the template page shows nothing and an install is
refused.

| Id                   | Owner  | Other user | Anonymous | Admin  | Listed |
| -------------------- | ------ | ---------- | --------- | ------ | :----: |
| 3.private            | 0:0:0  | -:-:-      | -:-       | -:-:-  |   ✗    |
| 3.shared             | 0:0:0  | -:-:-      | -:-       | -:-:-  |   ✗    |
| 3.public             | 0:0:0  | 0:0:0      | 0:0       | 0:0:0  |   ✓    |
| 3.in_review          | 0:0:0  | -:-:-      | -:-       | 0:-:-  |   ✗    |
| 3.rejected           | 0:0:0  | -:-:-      | -:-       | 0:-:-  |   ✗    |
| 3.resubmitted        | 0:0:0  | -:-:-      | -:-       | 0:-:-  |   ✗    |
| 3.withdrawn_rejected | 0:0:0  | -:-:-      | -:-       | -:-:-  |   ✗    |
| 3.rejected+private   | 01:1:1 | -:-:-      | -:-       | 0:-:-  |   ✗    |
| 3.rejected+in_review | 01:1:1 | -:-:-      | -:-       | 1:-:-  |   ✗    |
| 3.private+in_review  | 01:1:1 | -:-:-      | -:-       | 1:-:-  |   ✗    |
| 3.public+private     | 01:1:0 | 0:0:0      | 0:0       | 0:0:0  |   ✓    |
| 3.public+in_review   | 01:1:0 | 0:0:0      | 0:0       | 01:0:0 |   ✓    |
| 3.public+rejected    | 01:1:0 | 0:0:0      | 0:0       | 01:0:0 |   ✓    |
| 3.rejected+public    | 01:1:1 | 1:1:1      | 1:1       | 1:1:1  |   ✓    |
| 3.blocked            | 0:0:-  | -:-:-      | -:-       | -:-:-  |   ✗    |
| 3.public_blocked     | 0:0:-  | -:-:-      | -:-       | -:-:-  |   ✗    |
| 3.blocked+in_review  | 01:1:- | -:-:-      | -:-       | -:-:-  |   ✗    |
| 3.marked             | -:-:-  | -:-:-      | -:-       | -:-:-  |   ✗    |
| 3.public+marked      | -:-:-  | -:-:-      | -:-       | -:-:-  |   ✗    |
| 3.marked+in_review   | -:-:-  | -:-:-      | -:-       | -:-:-  |   ✗    |

- The owner is shown their edit, while an install copies the listed revision,
  or the latest one when none is listed. The owner installs their latest
  revision with `latest=true`.
- An admin previews the review queue from the admin page only. The template
  page shows them what everybody sees.
- Only its owner opens a blocked template, and they can't install it. Admins
  can't open it until blocking is built, see area 10.
- Nobody opens a template marked for deletion, not even its owner: it's
  deleted, only purged later.

## 4. Admin Review Page

Runs the states of area 3, plus `rejected+in_review`, `public+resubmitted`,
`public+rejected+private` and `in_review+pruned`, since those decide the tab and
what a review does. The tabs are
`in_review`, `rejected` and `public`.

- **Tab:** the tab of the admin page the template is on, and the index of the
  revision of its row. `—` means the template isn't on the admin page.
- **Approve and Reject:** what reviewing that row does. Outcomes are `listed`
  (the revision is approved and listed), `rejected` (the listing doesn't change: the listed revision stays
  listed), `unlisted` (rejected and taken out of the listing) and `refused`.
- **What the row tells:** `can_approve` is true exactly when approving lists
  the revision, `edited_since_submitted` exactly when approving is refused
  because the template was edited since, `can_reject` exactly when rejecting
  isn't refused, and `reject_unlists` exactly when rejecting unlists it. The
  web-frontend enables the Approve and Reject buttons, tells why Approve is
  disabled and shows the "takes it out of the listing" notice from them, see
  area 7.

| Id                        | Tab          | Approve | Reject   |
| ------------------------- | ------------ | ------- | -------- |
| 4.private                 | —            | —       | —        |
| 4.shared                  | —            | —       | —        |
| 4.in_review               | in_review, 0 | listed  | rejected |
| 4.resubmitted             | in_review, 0 | listed  | rejected |
| 4.in_review+pruned        | in_review, 0 | refused | rejected |
| 4.rejected                | rejected, 0  | listed  | refused  |
| 4.withdrawn_rejected      | —            | —       | —        |
| 4.rejected+private        | rejected, 0  | refused | refused  |
| 4.rejected+in_review      | in_review, 1 | listed  | rejected |
| 4.public                  | public, 0    | refused | unlisted |
| 4.public+private          | public, 0    | refused | unlisted |
| 4.public+in_review        | in_review, 1 | listed  | rejected |
| 4.public+resubmitted      | in_review, 1 | listed  | rejected |
| 4.public+rejected         | rejected, 1  | listed  | unlisted |
| 4.public+rejected+private | rejected, 1  | refused | unlisted |
| 4.rejected+public         | public, 1    | refused | unlisted |
| 4.blocked                 | —            | —       | —        |
| 4.public_blocked          | —            | —       | —        |
| 4.blocked+in_review       | —            | —       | —        |
| 4.marked                  | —            | —       | —        |
| 4.marked+in_review        | —            | —       | —        |
| 4.public+marked           | —            | —       | —        |

- A rejected template that was edited since isn't approved as reviewed, because
  the admin didn't see the edit.
- Rejecting an edit in review of a listed template keeps the approved revision
  listed. Rejecting a rejected edit again unlists it.
- A template without content can't be approved.

## 5. Admin Switches Approval Off

Whether switching approval off approves the template, as an admin approving it
would. Runs the states with a revision in review, and without one: `private`,
`public`, `rejected`, `withdrawn_rejected`, `public+rejected` and
`rejected+private`.

| Id                          | Approved |
| --------------------------- | :------: |
| 5.in_review                 |    ✓     |
| 5.public+in_review          |    ✓     |
| 5.rejected+public+in_review |    ✓     |
| 5.private+in_review         |    ✓     |
| 5.rejected+in_review        |    ✗     |
| 5.resubmitted               |    ✗     |
| 5.public+resubmitted        |    ✗     |
| 5.in_review+pruned          |    ✗     |
| 5.blocked+in_review         |    ✗     |
| 5.marked+in_review          |    ✗     |
| 5.private                   |    ✗     |
| 5.public                    |    ✗     |
| 5.rejected                  |    ✗     |
| 5.public+rejected           |    ✗     |
| 5.rejected+private          |    ✗     |
| 5.withdrawn_rejected        |    ✗     |

- A template rejected since it was last approved stays in review: an admin
  rejected it, so an admin reviews it again.
- A template without content, blocked or marked for deletion isn't approved,
  as an admin can't approve it either.

## 6. Stale Views And Concurrency

An admin reviews what the admin page showed them, which another admin or the
owner may have changed since. A refused review changes nothing and records
nothing in the audit log. Runs a state per reason a review is refused.

The Param id column is the whole test param id, since a state repeats with
another case.

- **Case:** what the admin saw and which revision they review. `latest`
  reviews the latest revision, in the state the template is in. `previous`
  reviews the first revision instead. `seen_in_review` saw it in review,
  `seen_public` saw it public, and `seen_listed` saw it listed while it isn't.
  `not_staff` is a reviewer who isn't staff, and saw the latest state.

| Param id                            | Case           | Refused because                         |
| ----------------------------------- | -------------- | --------------------------------------- |
| 6.private-latest-approve            | latest         | not in review                           |
| 6.private-latest-reject             | latest         | not in review                           |
| 6.rejected-latest-reject            | latest         | rejected already, and not listed        |
| 6.blocked+in_review-latest-approve  | latest         | blocked                                 |
| 6.in_review+pruned-latest-approve   | latest         | has no content                          |
| 6.in_review-not_staff-approve       | not_staff      | not an admin                            |
| 6.rejected+private-previous-approve | previous       | updated since, the edit isn't submitted |
| 6.rejected+private-latest-approve   | latest         | not the revision of its admin row       |
| 6.marked+in_review-latest-approve   | latest         | deleted by the owner                    |
| 6.public-seen_in_review-approve     | seen_in_review | approved already by another admin       |
| 6.rejected-seen_in_review-reject    | seen_in_review | rejected already by another admin       |
| 6.private-seen_public-reject        | seen_public    | made private by the owner since         |
| 6.rejected-seen_listed-approve      | seen_listed    | unlisted by another admin since         |

A reject without a reason is refused too: `test_reject_needs_a_reason` in
`test_user_template_review.py`, and `test_reject_reason_required` in
`backend/tests/baserow/api/admin/templates/test_templates_admin_views.py`.

Concurrent changes are tested per case:

- An approve after an update of the owner moved the review to a new revision
  is refused: `test_approve_refused_after_the_review_moved_to_a_new_revision`
  in `test_user_template_review.py`.
- A review locks the template before reading it:
  `test_review_locks_the_root` in `test_user_template_review.py`.
- Making public or updating reads the approval setting under a lock, so it
  can't miss a switch: `test_approval_is_read_from_the_locked_settings_row` in
  `test_user_template_publishing.py`.
- Switching approval off locks the settings before any template, and only the
  stored setting counts, not a stale cache:
  `test_switching_approval_off_approves_the_pending_templates` in
  `test_user_template_review.py`.
- A settings save that hits a deadlock is retried, then answers 409:
  `test_switching_approval_off_is_retried_after_a_deadlock` in
  `backend/tests/baserow/api/settings/test_settings_views.py`.
- Install and download jobs requested earlier check access again when they
  start: area 3.

## 7. What The Web-Frontend Shows

The web-frontend shows what the API returns. Its specs are tables over the
fields of the API:

- The update modal tells what an update does to the review, from
  `update_needs_review`, with `listed` picking the wording. Its rows
  are named by the area 1 ids, with the fields the API returns for them:
  `web-frontend/test/unit/core/components/updateUserTemplateModal.spec.js`.
- The make public modal tells whether it goes to review, from
  `make_public_needs_review`:
  `web-frontend/test/unit/core/components/makeTemplatePublicModal.spec.js`.
- The template page tells the owner that only they see it, and offers to make
  it public or submit it for review again, from `state`, `listed`,
  `can_make_public` and `make_public_needs_review`:
  `web-frontend/test/unit/core/components/templateDetails.spec.js`.
- The list of the owner's templates shows the state and whether it's still
  listed: `web-frontend/test/unit/core/components/userTemplateList.spec.js`.
- The admin page shows the tabs, counts, review buttons, why Approve is
  disabled and the "takes it out of the listing" notice from the admin rows:
  `web-frontend/test/unit/core/admin/templates/templatesAdmin.spec.js`. Its
  `REVIEW_FIELDS` copy `can_reject` and `reject_unlists` of area 4 per state
  and listing; `can_approve` and `edited_since_submitted` are set per test.

## Other Coverage

Tested per case, outside the tables:

- Create, update and delete of a template, and what its content keeps:
  `test_create_user_template_job.py`, `test_update_user_template_job.py`,
  `test_user_template_handler.py`.
- What state, reject reason and listing each combination of revisions shows,
  which areas 4 and 7 build on: `test_get_template_state` in
  `test_user_template_handler.py`.
- What an install copies: `test_install_user_template_job.py`.
- The download archive and its reuse: `test_user_template_archive.py`,
  `test_user_template_download.py`.
- Purge after the grace period, and deleted users:
  `test_user_template_purge.py`, `test_user_template_receivers.py`.
- Audit log entries: `test_review` in `test_user_template_review.py`,
  `test_make_visibility_actions_registered` in
  `test_user_template_publishing.py`.
- Admin page sorting, filters, permissions, query count, review error codes,
  and the reviewed row built in the review's transaction:
  `backend/tests/baserow/api/admin/templates/test_templates_admin_views.py`.
- API wiring and error codes: `backend/tests/baserow/api/templates/`.

The core tests are in `backend/tests/baserow/core/user_templates/`.

## TODO Coverage

- 7.x: name the other web-frontend tables by plan ids.
- e2e, #6329: create a template, make it public with approval on, approve it as
  an admin, then install it as another user.
