# Agent Participation Test Plan

Manual and e2e coverage for PR #6826: who can chat, approve tool calls and
continue triggered conversations, asking others to approve in a private
conversation, and who can stop a reply. It builds on #6793 (sharing).

Automated browser coverage lives in `e2e-tests/tests/agent/`. The plan run
(`Run` column) executed every case on the e2e stack with the model stub.

## Setup

- A workspace with an Enterprise licence (Advanced behaves the same), unless a
  case says "no licence".
- Members: **Admin** (workspace admin, owns the agent), **Builder**, **Editor A**,
  **Editor B**, **Viewer**. A team **Support** with Editor A.
- An agent with a model. For tool approvals: a run-as identity with the Builder
  role, and **Create database** allowed with Ask first.
- An HTTP trigger whose message is the request body's `subject`.

## Rule values

| Setting                                  | Default            | Options                                                |
| ---------------------------------------- | ------------------ | ------------------------------------------------------ |
| Who can chat                             | Editors and higher | Editors, Builders, Admins and higher; Specific; Nobody |
| Who can approve tool calls               | Editors and higher | Same, without Nobody                                   |
| Who can continue triggered conversations | Nobody             | Same as chat                                           |

"Specific users or teams" still needs the Editor role: a named Viewer stays
denied.

## 1. Permissions section

| ID  | Case                                | Steps                                                                                          | Expected                                                                                       | Run  |
| --- | ----------------------------------- | ---------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------- | ---- |
| 1.1 | Defaults                            | Open the agent's configuration as Admin, then Permissions.                                     | Chat and approve show "Editors and higher", continue shows "Nobody". Approve offers no Nobody. | Pass |
| 1.2 | Saving the default removes the rule | Set chat to Builders, then back to Editors.                                                    | The API returns no stored rule for chat after the second save.                                 | Pass |
| 1.3 | Specific people: count and modal    | Set approve to Specific, add the Support team and Editor B in the modal, close it.             | The setting shows "Manage people and teams (2)". Reopening lists both.                         | Pass |
| 1.4 | Specific without people is refused  | `PUT .../permissions/approve/` with role `CUSTOM` and no subjects.                             | 400. The stored rule doesn't change.                                                           | Pass |
| 1.5 | Approve can't be Nobody             | `PUT .../permissions/approve/` with role `NOBODY`.                                             | 400 "Someone must be able to approve tool calls."                                              | Pass |
| 1.6 | Subjects from another workspace     | `PUT` a Specific rule naming a user who isn't a member.                                        | 400. Nothing is stored.                                                                        | Pass |
| 1.7 | Nobody left warning                 | Approve = Specific with only Editor B. Remove Editor B from the workspace. Reload the section. | The setting warns that nobody is left.                                                         | Pass |
| 1.8 | Who may edit the rules              | `PUT` a rule as Builder, then as Editor A.                                                     | Builder: 200. Editor: refused.                                                                 | Pass |

## 2. Who can chat

| ID  | Case                       | Steps                                                                                         | Expected                                                                                                             | Run  |
| --- | -------------------------- | --------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------- | ---- |
| 2.1 | Default                    | Editor A starts a conversation. Viewer tries.                                                 | Editor A: the agent answers. Viewer: refused, the page shows no composer.                                            | Pass |
| 2.2 | Builders and higher        | Set chat to Builders. Editor A sends in their own existing conversation and starts a new one. | Both refused. Their conversation shows "you can read this conversation, but not send messages". Builder still chats. | Pass |
| 2.3 | Specific person            | Chat = Specific with Editor B.                                                                | Editor B chats; Editor A is refused.                                                                                 | Pass |
| 2.4 | Specific team              | Chat = Specific with the Support team. Then remove Editor A from the team.                    | Editor A chats while in the team, and is refused after leaving it.                                                   | Pass |
| 2.5 | Named Viewer               | Chat = Specific with the Viewer.                                                              | Still refused.                                                                                                       | Pass |
| 2.6 | Nobody, triggers still run | Chat = Nobody. Admin tries to chat. Call the trigger's webhook.                               | Admin refused. The trigger starts a conversation and the agent answers it.                                           | Pass |

## 3. Who can approve tool calls

| ID  | Case                        | Steps                                                                                        | Expected                                                                                                     | Run      |
| --- | --------------------------- | -------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------ | -------- |
| 3.1 | Approver narrower than chat | Approve = Admins. Editor A asks for a database in a shared conversation.                     | The reply waits. Editor A sees no Approve and the API refuses their decision. Admin approves and it resumes. | Pass, O1 |
| 3.2 | Approve without chat        | Chat = Admins, approve = Editors. Editor A opens a shared conversation waiting for approval. | Editor A approves, though they can't send messages.                                                          | Pass     |

## 4. Who can continue triggered conversations

| ID  | Case                    | Steps                                                                          | Expected                                                                               | Run  |
| --- | ----------------------- | ------------------------------------------------------------------------------ | -------------------------------------------------------------------------------------- | ---- |
| 4.1 | Default Nobody          | The trigger starts a conversation. Admin and Editor A open it and try to send. | Everyone, Admin included, sees "Started by a trigger" and the API refuses the message. | Pass |
| 4.2 | Editors and higher      | Continue = Editors. Editor A sends, Viewer tries.                              | Editor A's message is answered and named as theirs. The Viewer is refused.             | Pass |
| 4.3 | Specific person         | Continue = Specific with Editor B.                                             | Editor B continues; Editor A and Admin are refused.                                    | Pass |
| 4.4 | Continuing doesn't chat | Continue = Editors, chat = Admins.                                             | Editor A continues a triggered conversation but can't start their own.                 | Pass |

## 5. Ask for approval in a private conversation

| ID   | Case                                | Steps                                                                                         | Expected                                                                                                              | Run             |
| ---- | ----------------------------------- | --------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------- | --------------- |
| 5.1  | Only while waiting                  | Editor A's private conversation has a finished reply.                                         | No "Ask for approval". The API refuses a request.                                                                     | Pass            |
| 5.2  | Candidates                          | A reply waits. Open Ask for approval.                                                         | Lists members who may approve, by name, without the owner, the agent's identity, or people the approve rule excludes. | Pass            |
| 5.3  | Asking                              | Ask Editor B.                                                                                 | The bar reads "Private · " with both names. Editor B sees the conversation; the Viewer and Builder don't.             | Pass            |
| 5.4  | Not a candidate                     | `POST .../approvers/` naming the Viewer, or a non-member.                                     | 400. Nobody is added.                                                                                                 | Pass            |
| 5.5  | Only the owner asks                 | Editor B, now in it, calls `.../approvers/`.                                                  | Refused.                                                                                                              | Pass            |
| 5.6  | The approver decides                | Editor B approves.                                                                            | The reply resumes and the database is created.                                                                        | Pass            |
| 5.7  | What an approver may change         | As Editor B: open the conversation's options, share it, rename it, delete it through the API. | The options menu offers only Delete for me. Share answers not found, rename and delete are refused.                   | Pass            |
| 5.8  | The approver writes                 | Editor B sends a message.                                                                     | Accepted. The model sees each person's message named.                                                                 | Pass, F4        |
| 5.9  | Delete for me                       | The owner deletes and chooses Delete for me.                                                  | It leaves the owner's list. Editor B keeps it.                                                                        | Pass            |
| 5.10 | Delete for everyone                 | In another such conversation, the owner chooses Delete for everyone.                          | It's gone for everyone.                                                                                               | Pass            |
| 5.11 | Alone, delete only trashes          | The owner of a conversation nobody else is in deletes it.                                     | It goes to the trash at once, with no "for me" choice.                                                                | Pass            |
| 5.12 | After the owner left                | After 5.9, Editor B chooses Delete for me.                                                    | It warns that the conversation is deleted for good, then it is gone for everyone. Delete for everyone stays refused.  | Pass (F1 fixed) |
| 5.13 | Approver removed from the workspace | Remove Editor B from the workspace.                                                           | Editor B no longer reads it; the owner's bar lists only themselves.                                                   | Pass (F2 fixed) |
| 5.14 | Sharing after asking                | The owner shares a conversation they asked Editor B to approve in.                            | It becomes shared, visible to every reader, and the approvers bar is gone.                                            | Pass            |
| 5.15 | An approver leaves                  | Editor B, asked to approve, chooses Delete for me while the owner is still in it.             | It leaves Editor B's list; the owner keeps it and the bar drops Editor B.                                             | Pass (unit)     |

## 6. Stopping a reply

| ID  | Case                                  | Steps                                                                                             | Expected                                                                                   | Run         |
| --- | ------------------------------------- | ------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------ | ----------- |
| 6.1 | Own reply in a shared conversation    | Editor A sends a long request in a shared conversation.                                           | Editor A sees Stop and stops it.                                                           | Pass        |
| 6.2 | Another person's reply                | Editor B watches Editor A's running reply.                                                        | No Stop for Editor B; the API refuses their cancel. Builder may stop it.                   | Pass        |
| 6.3 | Own reply in a triggered conversation | Continue = Editors. Editor A sends a long request in a triggered conversation.                    | Editor A sees Stop and stops it.                                                           | Pass        |
| 6.4 | Owner's reply, seen by an approver    | Editor B, asked to approve, watches the owner's running reply.                                    | No Stop for Editor B; the API refuses their cancel.                                        | Pass        |
| 6.5 | Who stopped it                        | Builder stops Editor A's running reply while Editor A watches it.                                 | Editor A sees "Stopped by" and the builder's name at once; their own stop shows "Stopped." | Pass        |
| 6.6 | Resumed by someone else               | Editor B approves Editor A's waiting reply in a shared conversation, which then runs as Editor B. | Editor A can still stop it; Editor B can't without updating the agent.                     | Pass (unit) |

## 7. Without a licence

| ID  | Case                        | Steps                                                                                        | Expected                                                               | Run  |
| --- | --------------------------- | -------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------- | ---- |
| 7.1 | Locked settings             | Remove the licence and open Permissions.                                                     | Each setting is locked with the explanation; the rules API is refused. | Pass |
| 7.2 | Stored rules aren't applied | With chat = Admins stored, Editor A chats and approves.                                      | Both work.                                                             | Pass |
| 7.3 | Nobody continues            | With continue = Editors stored, Editor A and Admin try to continue a triggered conversation. | Both refused.                                                          | Pass |
| 7.4 | Rules come back             | Add the licence again.                                                                       | The stored rules apply again.                                          | Pass |

## Findings

| ID  | Severity | Status    | Finding                                                                                                                                                                                                                                                                 |
| --- | -------- | --------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| F1  | Bug      | Fixed     | An approver couldn't remove a conversation they were asked into, and once the owner chose Delete for me nobody could delete it. Now everyone in it can Delete for me; once the owner has left, the last one out deletes it for good (ADR 014).                          |
| F2  | Minor    | Fixed     | A member removed from the workspace stayed a participant and saw the conversation again if invited back. Leaving a workspace now takes them out of the conversations they were asked into, and deletes those nobody is left in.                                         |
| F3  | Bug      | Fixed     | A reply resumed by someone else's approval runs as that person, but the stop rule read the run's creator as "the person the reply answers". In a shared conversation its author saw Stop and the API refused it. The rule now reads the reply's sender.                 |
| F4  | Bug      | Fixed     | After the rebase, senders were named to the model only in shared conversations a person started. A private conversation with approvers, or a triggered one people continue, has several writers too. Covered by `test_senders_are_named_once_several_people_can_write`. |
| O1  | UX note  | Unchanged | People who may not approve see Approve and Reject disabled, without a reason. Same pattern as before this PR.                                                                                                                                                           |
| F5  | Bug      | Fixed     | Found in review: a trigger's opening message reached the model as written by a "Deleted user". Only a person's message names its sender now.                                                                                                                            |
| F6  | Bug      | Fixed     | Found in review: someone who may continue a triggered conversation was told they can't send messages while the agent's configuration was incomplete.                                                                                                                    |
| F7  | Bug      | Fixed     | Found in review: a rule change could be saved without its audit log entry. Both now happen in one transaction.                                                                                                                                                          |

## Security review

One reviewer pass over the whole PR, by role, licence, endpoint and realtime channel.

| ID  | Severity | Status         | Finding                                                                                                                                                                                                                |
| --- | -------- | -------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| M1  | Medium   | Fixed in #6793 | A message or a name could pass for another sender. Each person's message now reaches the model as a JSON object.                                                                                                       |
| M2  | Medium   | Fixed          | A person continuing a triggered conversation lost the instruction that its opening message is outside data.                                                                                                            |
| M3  | Medium   | Fixed          | Rule changes weren't in the audit log. They now go through `update_agent_participation_rule`.                                                                                                                          |
| L1  | Low      | Fixed          | Resuming a reply whose sender was deleted crashed the run; it now runs without naming anyone.                                                                                                                          |
| L2  | Low      | Fixed          | The approver picker checked members in batches, so few approvers in a large workspace cost hundreds of queries. It checks every member at once, with a fixed number of queries; a faster list is a follow-up in #6626. |
| L3  | Low      | Fixed          | People asked to approve kept receiving run events after losing read access.                                                                                                                                            |
| L4  | Low      | Fixed          | An owner who may no longer chat could still list members and ask them to approve.                                                                                                                                      |
| L5  | Low      | Fixed          | Someone named in a "specific people" rule who left and was invited back was allowed again. Leaving the workspace now removes them from the rules.                                                                      |
| L6  | Low      | Fixed          | The permissions object listed agent ids to non-members and included trashed agents.                                                                                                                                    |
| L7  | Low      | Follow-up      | The owner can't remove someone they asked to approve.                                                                                                                                                                  |
| L8  | Low      | Fixed          | A "specific people" approve rule naming only viewers left nobody able to approve. Saving one is refused.                                                                                                               |
| L9  | Low      | Known          | Unconfirmed race: deleting a user while the last other person leaves can leave a conversation nobody sees.                                                                                                             |

## How it ran

- The plan run used throwaway Playwright specs, not part of the repository. Each test made its own workspace, members and agent, so the licensed cases ran in parallel; the no-licence cases removed the licence and ran alone.
- The model stub reads a shared conversation's JSON message envelope. The stop cases used a local stub script that streams a long answer without tools.
- Trigger cases are slow under parallel load: the e2e stack's single Celery worker drains about 1–2 tasks a second, so trigger starts can queue behind hundreds of broadcast and email tasks. Run them serially on a fresh stack.
