import { h, reactive, ref } from 'vue'
import CrudTable from '@baserow/modules/core/components/crudTable/CrudTable'
import CrudTableColumn from '@baserow/modules/core/crudTable/crudTableColumn'
import SimpleField from '@baserow/modules/core/components/crudTable/fields/SimpleField'
import MoreField from '@baserow/modules/core/components/crudTable/fields/MoreField'
import Avatar from '@baserow/modules/core/components/Avatar'
import Button from '@baserow/modules/core/components/Button'
import Context from '@baserow/modules/core/components/Context'
import './crudTable.scss'

// Interactive fixtures only: role edits stay in this story's in-memory service.
const RolePicker = {
  components: { Button, Context },
  props: ['modelValue'],
  emits: ['update:modelValue'],
  setup() {
    return {
      roles: ['Admin', 'Builder', 'Editor', 'Commenter', 'Viewer'],
      roleIcons: {
        Admin: 'iconoir-crown',
        Builder: 'iconoir-tools',
        Editor: 'iconoir-edit-pencil',
        Commenter: 'iconoir-chat-bubble',
        Viewer: 'iconoir-eye-empty',
      },
    }
  },
  template: `<div>
    <Button type="secondary" button-type="button" class="crud-table-story__role"
      :icon="roleIcons[modelValue]" append-icon="iconoir-nav-arrow-down" aria-haspopup="true"
      @click="$refs.menu.toggle($event.currentTarget)">{{ modelValue }}</Button>
    <Context ref="menu">
      <ul class="context__menu">
        <li v-for="role in roles" :key="role" class="context__menu-item">
          <a href="#" class="context__menu-item-link" @click.prevent="$emit('update:modelValue', role); $refs.menu.hide()">
            <i class="context__menu-item-icon" :class="roleIcons[role]" />{{ role }}
          </a>
        </li>
      </ul>
    </Context>
  </div>`,
}

const RoleField = {
  components: { RolePicker },
  props: ['row'],
  emits: ['row-update'],
  template: `<RolePicker :model-value="row.role" @update:model-value="$emit('row-update', { ...row, role: $event })" />`,
}

const NameField = {
  props: ['row'],
  setup: (props) => () =>
    h('div', { class: 'flex align-items-center' }, [
      h(Avatar, {
        initials: props.row.name[0],
        size: 'medium',
        rounded: true,
        class: 'margin-right-2',
      }),
      h('span', props.row.name),
    ]),
}

const rows = [
  {
    id: 1,
    name: 'Arlene McCoy',
    email: 'a.mccoy@outlook.com',
    role: 'Editor',
    team: 'Front-End Team',
    assignments: [
      {
        id: 1,
        name: 'Projects',
        scope: 'Database in Widelab',
        icon: 'iconoir-db',
        role: 'Builder',
      },
      {
        id: 2,
        name: 'Tasks',
        scope: 'Table in Projects',
        icon: 'iconoir-table',
        role: 'Builder',
      },
      {
        id: 3,
        name: 'Kanban - Q3',
        scope: 'View in Projects / Tasks',
        icon: 'baserow-icon-kanban',
        role: 'Editor',
      },
    ],
  },
  {
    id: 2,
    name: 'Sam Rivera',
    email: 'sam@example.com',
    role: 'Editor',
    team: 'Engineering',
    assignments: [
      {
        id: 1,
        name: 'Projects',
        scope: 'Database in Widelab',
        icon: 'iconoir-db',
        role: 'Builder',
      },
      {
        id: 2,
        name: 'Tasks',
        scope: 'Table in Projects',
        icon: 'iconoir-table',
        role: 'Editor',
      },
    ],
  },
  {
    id: 3,
    name: 'Charlie Lee',
    email: 'charlie@example.com',
    role: 'Viewer',
    team: 'Support',
  },
  {
    id: 4,
    name: 'Robin Patel',
    email: 'robin@example.com',
    role: 'Editor',
    team: 'Design',
    assignments: [
      {
        id: 1,
        name: 'Kanban - Q3',
        scope: 'View in Projects / Tasks',
        icon: 'baserow-icon-kanban',
        role: 'Editor',
      },
    ],
  },
]

const columns = [
  new CrudTableColumn('name', 'Name', NameField, true),
  new CrudTableColumn('email', 'Email', SimpleField, true),
  new CrudTableColumn('role', 'Role', RoleField),
  new CrudTableColumn('team', 'Team', SimpleField),
  new CrudTableColumn('more', '', MoreField, false, false, true),
]

function createService(state, records) {
  return {
    options: { isPaginated: true, baseUrl: '/storybook/rows/' },
    async fetch(_url, _page, search, sorts) {
      if (state === 'loading') {
        return new Promise(() => {})
      }
      let results = state === 'empty' ? [] : [...records]
      if (search) {
        results = results.filter((row) =>
          `${row.name} ${row.email}`
            .toLowerCase()
            .includes(search.toLowerCase())
        )
      }
      results.sort((a, b) => {
        for (const { key, direction } of sorts) {
          const comparison = a[key].localeCompare(b[key])
          if (comparison) return direction === 'asc' ? comparison : -comparison
        }
        return 0
      })
      return { data: { count: results.length, results } }
    },
  }
}

const renderTable =
  (state = 'populated', width = '100%', expandable = false) =>
  (args) => ({
    components: { CrudTable, Button, Context, Avatar, RolePicker },
    setup() {
      const records = reactive(structuredClone(rows))
      const count = ref(0)
      const context = ref(null)
      const selectedRow = ref(null)
      const openContext = ({ row, event }) => {
        event.preventDefault()
        selectedRow.value = row
        context.value.toggle(event.currentTarget)
      }
      return {
        args,
        columns,
        count,
        context,
        selectedRow,
        openContext,
        width,
        expandable,
        service: createService(state, records),
      }
    },
    template: `
    <div :style="{ position: 'relative', height: '640px', width, maxWidth: '100%' }">
      <CrudTable v-bind="args" :service="service" :columns="columns" row-id-key="id"
        :expand-column-key="expandable ? 'role' : null"
        :row-expandable="row => Boolean(row.assignments?.length)"
        @total-count-update="count = $event" @row-context="openContext">
        <template #title>{{ count }} members</template>
        <template #primary-action>
          <Button type="primary" size="large" icon="iconoir-plus">Invite members</Button>
        </template>
        <template #empty>
          <div class="placeholder">
            <div class="placeholder__icon">
              <i class="iconoir-group" aria-hidden="true"></i>
            </div>
            <h2 class="placeholder__header">{{ $t('membersSettings.membersTable.emptyTitle') }}</h2>
            <p class="placeholder__content">{{ $t('membersSettings.membersTable.emptyDescription') }}</p>
          </div>
        </template>
        <template v-if="expandable" #row-expansion-toggle="{ row }">+{{ row.assignments.length }}</template>
        <template v-if="expandable" #expanded-row="{ row }">
          <tr v-for="detail in row.assignments" :key="detail.id" class="data-table__table-row">
            <td colspan="2" class="data-table__table-cell">
              <div class="data-table__table-cell-content crud-table-story__resource">
                <Avatar :icon="detail.icon" color="neutral" size="large" rounded class="crud-table-story__resource-icon" />
                <span>{{ detail.name }}</span>
                <span class="crud-table-story__separator" aria-hidden="true">·</span>
                <span class="crud-table-story__scope">{{ detail.scope }}</span>
              </div>
            </td>
            <td class="data-table__table-cell">
              <div class="data-table__table-cell-content"><RolePicker v-model="detail.role" /></div>
            </td>
            <td class="data-table__table-cell">
              <div class="data-table__table-cell-content"></div>
            </td>
            <td class="data-table__table-cell data-table__table-cell--sticky-right">
              <div class="data-table__table-cell-content"></div>
            </td>
          </tr>
        </template>
        <template #menus>
          <Context ref="context">
            <ul class="context__menu">
              <li class="context__menu-item">
                <a class="context__menu-item-link" @click="context.hide()">
                  View {{ selectedRow?.name }}
                </a>
              </li>
            </ul>
          </Context>
        </template>
      </CrudTable>
    </div>
  `,
  })

export default {
  title: 'Baserow/CrudTable',
  component: CrudTable,
  parameters: {
    layout: 'fullscreen',
    design: {
      type: 'figma',
      url: 'https://www.figma.com/design/nINWJ2KPHfg2Aes5kleK4n?node-id=2199-48386',
    },
  },
}

export const Populated = { render: renderTable() }
export const Empty = { render: renderTable('empty') }
export const Loading = { render: renderTable('loading') }

const openFirstRow = async ({ canvas, userEvent }) => {
  const buttons = await canvas.findAllByRole('button', {
    name: 'Expand row details',
  })
  await userEvent.click(buttons[0])
}

export const ExpandableRows = {
  render: renderTable('populated', '100%', true),
  play: openFirstRow,
}

export const NarrowViewport = {
  render: renderTable('populated', '390px', true),
  play: openFirstRow,
}
