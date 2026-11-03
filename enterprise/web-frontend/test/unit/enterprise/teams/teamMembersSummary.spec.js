import { mountSuspended } from '@nuxt/test-utils/runtime'
import { describe, expect, test } from 'vitest'
import TeamMembersSummary from '@baserow_enterprise/components/teams/TeamMembersSummary'

const sample = (label) => ({ subject_type: 'auth.User', subject_label: label })

async function mountSummary(team, canManageMembers = true) {
  return await mountSuspended(TeamMembersSummary, {
    props: { team, canManageMembers },
    global: {
      mocks: {
        $t: (key, params) =>
          params ? `${key}:${JSON.stringify(params)}` : key,
      },
    },
  })
}

describe('TeamMembersSummary', () => {
  test('offers to add members to a team without any', async () => {
    const wrapper = await mountSummary({ subject_count: 0, subject_sample: [] })

    expect(wrapper.find('.team-members-summary--empty').exists()).toBe(true)
    expect(wrapper.find('.team-members-summary__names').text()).toBe(
      'teamMembersSummary.empty'
    )
    expect(wrapper.find('button').text()).toBe('teamMembersSummary.add')
  })

  test('names one or two members', async () => {
    const one = await mountSummary({
      subject_count: 1,
      subject_sample: [sample('Jeff')],
    })
    expect(one.find('.team-members-summary__names').text()).toBe('Jeff')

    const two = await mountSummary({
      subject_count: 2,
      subject_sample: [sample('Jeff'), sample('Maria')],
    })
    expect(two.find('.team-members-summary__names').text()).toBe(
      'teamMembersSummary.twoNames:{"first":"Jeff","second":"Maria"}'
    )
  })

  test('names two members and counts the rest, with three avatars', async () => {
    const wrapper = await mountSummary({
      subject_count: 12,
      subject_sample: ['Jeff', 'Maria', 'Ann', 'Bob'].map(sample),
    })

    expect(wrapper.find('.team-members-summary__names').text()).toBe(
      'teamMembersSummary.moreNames:{"first":"Jeff","second":"Maria","count":10}'
    )
    expect(wrapper.findAll('.team-members-summary__avatar')).toHaveLength(3)
    expect(wrapper.find('button').text()).toBe('teamMembersSummary.manage')
  })

  test('emits manage, and has no button without the permission', async () => {
    const wrapper = await mountSummary({
      subject_count: 1,
      subject_sample: [sample('Jeff')],
    })
    await wrapper.find('button').trigger('click')
    expect(wrapper.emitted('manage')).toHaveLength(1)

    const readOnly = await mountSummary(
      { subject_count: 1, subject_sample: [sample('Jeff')] },
      false
    )
    expect(readOnly.find('button').exists()).toBe(false)
  })
})
