import { mountSuspended } from '@nuxt/test-utils/runtime'

import SubjectSampleField from '@baserow_enterprise/components/crudTable/fields/SubjectSampleField'
import { getTeamSubjectKey } from '@baserow_enterprise/utils/teamSubjects'

const row = {
  id: 3,
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
}

describe('teamSubjects', () => {
  test('tells users and agents with the same id apart', () => {
    expect(
      getTeamSubjectKey({ subject_id: 1, subject_type: 'auth.User' })
    ).not.toBe(getTeamSubjectKey({ subject_id: 1, subject_type: 'core.Agent' }))
  })

  test('shows users and agents at the same size in the teams table', async () => {
    const wrapper = await mountSuspended(SubjectSampleField, {
      props: { row, column: { key: 'subject_sample' } },
    })

    expect(wrapper.html()).toMatchSnapshot()
  })

  test('opens the members of the team when the column allows it', async () => {
    const wrapper = await mountSuspended(SubjectSampleField, {
      props: {
        row,
        column: {
          key: 'subject_sample',
          additionalProps: { canManageMembers: true },
        },
      },
    })

    await wrapper.trigger('click')
    await wrapper.trigger('keydown.enter')
    await wrapper.trigger('keydown.space')

    expect(wrapper.attributes('role')).toBe('button')
    expect(wrapper.attributes('tabindex')).toBe('0')
    expect(wrapper.attributes('aria-label')).toBe(
      'subjectSampleField.manageMembers'
    )
    expect(wrapper.emitted('manage-members')).toEqual([[row], [row], [row]])
  })

  test('does nothing on click when the column does not allow it', async () => {
    const wrapper = await mountSuspended(SubjectSampleField, {
      props: { row, column: { key: 'subject_sample' } },
    })

    await wrapper.trigger('click')
    await wrapper.trigger('keydown.space')

    expect(wrapper.attributes('role')).toBeUndefined()
    expect(wrapper.attributes('tabindex')).toBeUndefined()
    expect(wrapper.emitted('manage-members')).toBeUndefined()
  })
})
