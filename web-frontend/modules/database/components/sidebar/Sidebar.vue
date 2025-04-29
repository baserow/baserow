<template>
  <SidebarApplication
    :workspace="workspace"
    :application="application"
    @selected="selected"
  >
    <template #context>
      <li class="context__menu-item">
        <nuxt-link
          :to="{
            name: 'database-api-docs-detail',
            params: {
              databaseId: application.id,
            },
          }"
          class="context__menu-item-link"
        >
          <i class="context__menu-item-icon iconoir-book"></i>
          {{ $t('sidebar.viewAPI') }}
        </nuxt-link>
      </li>
    </template>
    <template v-if="isAppSelected(application)" #body>
      <ul class="tree__subs">
        <SidebarItem
          v-for="table in orderedTables"
          :key="table.id"
          v-sortable="{
            id: table.id,
            update: orderTables,
            marginTop: -1.5,
            enabled: $hasPermission(
              'database.order_tables',
              application,
              application.workspace.id
            ),
          }"
          :database="application"
          :table="table"
        ></SidebarItem>
      </ul>
      <ul v-if="pendingJobs.length" class="tree__subs">
        <component
          :is="getPendingJobComponent(job)"
          v-for="job in pendingJobs"
          :key="job.id"
          :job="job"
        >
        </component>
      </ul>
      <a
        v-if="
          $hasPermission(
            'database.create_table',
            application,
            application.workspace.id
          )
        "
        class="tree__sub-add"
        data-highlight="create-table"
        @click="$refs.createTableModal.show()"
      >
        <i class="tree__sub-add-icon iconoir-plus"></i>
        {{ $t('sidebar.createTable') }}
      </a>
      <CreateTableModal ref="createTableModal" :database="application" />
    </template>
  </SidebarApplication>
</template>

<script>
import { mapGetters } from 'vuex'
import { notifyIf } from '@baserow/modules/core/utils/error'
import SidebarItem from '@baserow/modules/database/components/sidebar/SidebarItem'
import SidebarApplication from '@baserow/modules/core/components/sidebar/SidebarApplication'
import CreateTableModal from '@baserow/modules/database/components/table/CreateTableModal'

export default {
  name: 'Sidebar',
  components: {
    CreateTableModal,
    SidebarApplication,
    SidebarItem,
  },
  props: {
    application: {
      type: Object,
      required: true,
    },
    workspace: {
      type: Object,
      required: true,
    },
  },
  computed: {
    orderedTables() {
      return this.application.tables
        .map((table) => table)
        .sort((a, b) => a.order - b.order)
    },
    pendingJobs() {
      return this.$store.getters['job/getAll'].filter((job) =>
        this.$registry
          .get('job', job.type)
          .isJobPartOfApplication(job, this.application)
      )
    },
    ...mapGetters({ isAppSelected: 'application/isSelected' }),
  },
  methods: {
    async selected(application) {
      try {
        await this.$store.dispatch('application/select', application)
      } catch (error) {
        notifyIf(error, 'workspace')
      }
    },
    async orderTables(order, oldOrder) {
      try {
        await this.$store.dispatch('table/order', {
          database: this.application,
          order,
          oldOrder,
        })
      } catch (error) {
        notifyIf(error, 'table')
      }
    },
    getPendingJobComponent(job) {
      return this.$registry.get('job', job.type).getSidebarComponent()
    },
  },
}
</script>
