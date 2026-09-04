# Report template

Copy this structure. Omit empty sections except "Verification". Number findings within a section and order them by impact. Every finding names the exact line, so the comment can be pasted there as is. A finding without a natural line (PR description, missing test, missing doc) anchors to the file that should hold the change, or to the PR description, and says so in **Where**.

---

# Review: PR #<N> <title>

**Problem and change.** <Three sentences: the problem, the intended behaviour, how the diff solves it.>

**Feature flag:** `<flag>` or none. **Scope:** <backend, frontend, migrations, public API, import/export, premium, enterprise>.

**Verdict:** <Approve | Approve with follow-ups | Request changes>. <One sentence applying the merge policy, for example "mergeable behind the flag once an issue tracks finding 2 before flag removal", or "not mergeable alone: stack the fix for finding 1 on top of this branch and merge them together".>

## Blocking / High

### 1. <Short title>

- **Where:** `backend/src/baserow/.../handler.py:123`
- **Issue:** <What is wrong and who is affected, in two sentences.>
- **Why:** <The consequence: what breaks, for whom, when.>
- **Repro:** <Numbered UI steps, or a code block with a pytest snippet, a request, or a shell command.>
- **Alternative:** <The smaller or safer design, when one exists. Omit otherwise.>
- **Comment:**
  > <The text to paste on that line. One to four sentences, polite, concrete, simple words.>

## Blocking / Medium

## Minor / Low

## Nits

## Non-blocking

## Follow-up candidates

- <Item>: <why it can wait, and under which policy: "behind the flag, before flag removal" or "stacked PR, base not merged alone">.

## Pre-existing (not caused by this PR)

- <Item>: <how it was verified on `develop`>. Suggest a separate issue.

## Verification

- **Ran:** `just b test tests/baserow/...` (12 passed), `just f test ...` (passed).
- **Manual:** <what was exercised in the browser, with the flag on and off>.
- **Not run:** <what, and why>.
- **Residual uncertainty:** <what could not be verified>.

---

## Example finding

Adapted from a real review (#5786). Paths are illustrative.

### 1. Missing row id turns an update into a create

- **Where:** `backend/src/baserow/contrib/database/api/rows/serializers.py:214`
- **Issue:** `row_id` is optional in the update serializer, so a payload without it takes the create branch. A client that loses the id duplicates the row instead of getting an error.
- **Why:** Silent duplicate rows in the user's table, with nothing in the response to notice.
- **Repro:**

  ```python
  response = api_client.patch(
      url, {"field_1": "x"}, format="json", HTTP_AUTHORIZATION=f"JWT {token}"
  )
  assert response.status_code == 400  # currently 200, and a new row exists
  ```

- **Alternative:** Make `row_id` required and let DRF return the 400.
- **Comment:**
  > Should `row_id` be required here? Without it the payload falls into the create branch, so a client that loses the id ends up with a duplicate row instead of an error. Making it required lets DRF return a 400.
