import { mountSuspended } from '@nuxt/test-utils/runtime'

import MemberSelectionList from '@baserow/modules/core/components/workspace/MemberSelectionList'
import SubjectSampleField from '@baserow_enterprise/components/crudTable/fields/SubjectSampleField'
import ManageTeamForm from '@baserow_enterprise/components/teams/ManageTeamForm'
import {
  getTeamSubjectKey,
  makeTeamSubject,
} from '@baserow_enterprise/utils/teamSubjects'
import {
  AgentSubjectType,
  UserSubjectType,
} from '@baserow/modules/core/subjectTypes'

const userSubjectType = new UserSubjectType()
const agentSubjectType = new AgentSubjectType()

describe('teamSubjects', () => {
  test('normalizes users and agents with collision-safe selection IDs', () => {
    const user = makeTeamSubject(
      {
        id: 10,
        user_id: 1,
        name: 'Ada',
        email: 'ada@example.com',
      },
      userSubjectType
    )
    const agent = makeTeamSubject(
      { id: 1, name: 'Writer' },
      agentSubjectType,
      'Agent'
    )

    expect(user).toEqual({
      id: 'auth.User:1',
      user_id: 1,
      subject_id: 1,
      subject_type: 'auth.User',
      name: 'Ada',
      email: 'ada@example.com',
    })
    expect(agent).toEqual({
      id: 'core.Agent:1',
      subject_id: 1,
      subject_type: 'core.Agent',
      name: 'Writer',
      email: 'Agent',
    })
    expect(getTeamSubjectKey(user)).not.toBe(getTeamSubjectKey(agent))
  })

  test('shows agents in the member selector with purple initials', async () => {
    const agent = makeTeamSubject(
      { id: 1, name: 'Writer' },
      agentSubjectType,
      'Agent'
    )
    const wrapper = await mountSuspended(MemberSelectionList, {
      props: { members: [agent] },
    })

    expect(wrapper.html()).toMatchSnapshot()
  })

  test('shows users and agents at the same size in the teams table', async () => {
    const wrapper = await mountSuspended(SubjectSampleField, {
      props: {
        row: {
          subject_count: 2,
          subject_sample: [
            {
              subject_id: 1,
              subject_type: 'auth.User',
              subject_label: 'Ada',
            },
            {
              subject_id: 2,
              subject_type: 'core.Agent',
              subject_label: 'Writer',
            },
          ],
        },
        column: { key: 'subject_sample' },
      },
    })

    expect(wrapper.html()).toMatchSnapshot()
  })

  test('removing an agent does not submit the team form', async () => {
    const agent = makeTeamSubject(
      { id: 1, name: 'Writer' },
      agentSubjectType,
      'Agent'
    )
    const wrapper = await mountSuspended(ManageTeamForm, {
      props: {
        workspace: {
          id: 1,
          _: {
            roles: [
              {
                uid: 'MEMBER',
                name: 'Member',
                description: '',
                isVisible: true,
                allowedScopeTypes: ['workspace'],
                allowedSubjectTypes: ['baserow_enterprise.Team'],
              },
            ],
          },
        },
        loading: false,
        invitedSubjects: [agent],
        defaultValues: { name: 'Writers', default_role: 'MEMBER' },
      },
    })

    await wrapper.find('.button-icon').trigger('click')

    expect(wrapper.emitted('remove-subject')).toEqual([[agent]])
    expect(wrapper.emitted('submitted')).toBeUndefined()
  })
})
