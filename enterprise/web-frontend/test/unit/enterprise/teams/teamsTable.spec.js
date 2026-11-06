import { mountSuspended } from '@nuxt/test-utils/runtime'
import { flushPromises } from '@vue/test-utils'
import { vi } from 'vitest'

import TeamsTable from '@baserow_enterprise/components/teams/TeamsTable'

const showContext = vi.fn()

const CrudTableStub = {
  name: 'CrudTable',
  emits: ['row-context'],
  template: `
    <div>
      <button
        class="more-button"
        @click="$emit('row-context', {
          row: { id: 1, name: 'Writers' },
          event: $event,
          target: $event.currentTarget,
        })"
      />
      <slot name="menus" :delete-row="() => {}" />
    </div>
  `,
}

const EditTeamContextStub = {
  name: 'EditTeamContext',
  methods: {
    show(...args) {
      showContext(...args)
    },
    toggle(...args) {
      showContext(...args)
    },
  },
  template: '<div />',
}

describe('TeamsTable', () => {
  test('aligns the edit context with the right edge of the more button', async () => {
    showContext.mockClear()
    const wrapper = await mountSuspended(TeamsTable, {
      props: {
        workspace: { id: 1, name: 'Workspace', _: { roles: [] } },
      },
      global: {
        stubs: {
          CrudTable: CrudTableStub,
          EditTeamContext: EditTeamContextStub,
          CreateTeamModal: true,
          UpdateTeamModal: true,
        },
      },
    })
    const button = wrapper.find('.more-button')

    await button.trigger('click')

    expect(showContext).toHaveBeenCalledWith(
      button.element,
      'bottom',
      'right',
      4
    )
  })
})

describe('TeamsTable role assignments', () => {
  test('expands the teams with roles into their roles', async () => {
    const team = { id: 3, name: 'Sales', role_assignment_count: 2 }
    // Renders what the table asks of the expandable rows, for one team with
    // roles and one without.
    const ExpandingCrudTableStub = {
      name: 'CrudTable',
      props: ['rowExpandable', 'expandColumnKey'],
      data: () => ({ rows: [team, { id: 4, role_assignment_count: 0 }] }),
      template: `
        <div>
          <div class="expand-column">{{ expandColumnKey }}</div>
          <div class="expandable">{{ rows.map(rowExpandable).join(',') }}</div>
          <div class="toggle">
            <slot name="row-expansion-toggle" :row="rows[0]" />
          </div>
          <table>
            <slot
              name="expanded-row"
              :row="rows[0]"
              :columns="[]"
              :update-row="() => {}"
            />
          </table>
        </div>
      `,
    }
    const wrapper = await mountSuspended(TeamsTable, {
      props: {
        workspace: { id: 1, name: 'Workspace', _: { roles: [] } },
      },
      global: {
        stubs: {
          CrudTable: ExpandingCrudTableStub,
          CreateTeamModal: true,
          UpdateTeamModal: true,
          SubjectRoleAssignmentRows: {
            props: ['subjectType', 'subjectId', 'roleColumnKey', 'readOnly'],
            template:
              '<tr class="rows"><td>{{ subjectType }}:{{ subjectId }}:{{ roleColumnKey }}:{{ readOnly }}</td></tr>',
          },
        },
      },
    })

    expect(wrapper.get('.expand-column').text()).toBe('default_role')
    expect(wrapper.get('.expandable').text()).toBe('true,false')
    expect(wrapper.get('.toggle').text()).toBe('+2')
    expect(wrapper.get('.rows').text()).toBe(
      'baserow_enterprise.Team:3:default_role:false'
    )
  })
})

describe('TeamsTable members', () => {
  const team = { id: 3, name: 'Sales', subject_count: 1 }
  const shownTargets = []
  const updatedRows = []
  const MembersCrudTableStub = {
    name: 'CrudTable',
    emits: ['manage-members'],
    data: () => ({ rows: [team] }),
    methods: {
      updateRow(row) {
        updatedRows.push(row)
      },
    },
    template: `
      <div>
        <button class="sample" @click="$emit('manage-members', rows[0])" />
        <slot name="menus" :delete-row="() => {}" />
      </div>
    `,
  }
  const InviteModalStub = {
    name: 'InviteModal',
    props: ['workspace', 'target'],
    methods: {
      show() {
        shownTargets.push(this.target)
      },
    },
    template: '<div />',
  }

  async function mountTable(client, bus) {
    shownTargets.length = 0
    updatedRows.length = 0
    return await mountSuspended(TeamsTable, {
      props: {
        workspace: { id: 1, name: 'Workspace', _: { roles: [] } },
      },
      global: {
        mocks: { $client: client, $bus: bus },
        stubs: {
          CrudTable: MembersCrudTableStub,
          EditTeamContext: true,
          CreateTeamModal: true,
          UpdateTeamModal: true,
          InviteModal: InviteModalStub,
        },
      },
    })
  }

  test('opens the members of a team in the invite modal', async () => {
    const bus = { $on: vi.fn(), $off: vi.fn() }
    const wrapper = await mountTable({ get: vi.fn() }, bus)

    await wrapper.find('.sample').trigger('click')
    await flushPromises()

    expect(shownTargets).toEqual([{ type: 'team', team }])
  })

  test('refreshes a team after its members changed', async () => {
    const listeners = {}
    const bus = {
      $on: (event, listener) => {
        listeners[event] = listener
      },
      $off: vi.fn(),
    }
    const refreshed = { ...team, subject_count: 2 }
    const client = { get: vi.fn().mockResolvedValue({ data: refreshed }) }
    const wrapper = await mountTable(client, bus)

    await listeners['team-members-updated'](3)
    await listeners['team-members-updated'](99)
    await flushPromises()

    expect(client.get.mock.calls).toEqual([['/teams/3/']])
    expect(updatedRows).toEqual([refreshed])
    wrapper.unmount()
    expect(bus.$off).toHaveBeenCalledWith(
      'team-members-updated',
      listeners['team-members-updated']
    )
  })
})
