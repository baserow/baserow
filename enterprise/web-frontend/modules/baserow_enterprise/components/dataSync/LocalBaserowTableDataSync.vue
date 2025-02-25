<template>
  <form @submit.prevent="submit">
    <div class="margin-top-3 margin-bottom-3">
      <Presentation
        :title="userName"
        :subtitle="$t('localBaserowTableDataSync.authorizing')"
        :initials="userName | nameAbbreviation"
        avatar-color="blue"
      />
    </div>
    <div class="row margin-bottom-3">
      <div class="col col-6 margin-bottom-2">
        <FormGroup
          small-label
          :label="$t('localBaserowTableDataSync.workspace')"
          required
        >
          <Dropdown
            :value="selectedWorkspaceId"
            :disabled="disabled"
            @input="workspaceChanged"
          >
            <DropdownItem
              v-for="workspace in workspaces"
              :key="workspace.id"
              :name="workspace.name"
              :value="workspace.id"
            ></DropdownItem>
          </Dropdown>
        </FormGroup>
      </div>
      <div class="col col-6 margin-bottom-2">
        <FormGroup
          small-label
          :label="$t('localBaserowTableDataSync.database')"
          required
        >
          <Dropdown
            :value="selectedDatabaseId"
            :disabled="disabled"
            @input="databaseChanged"
          >
            <DropdownItem
              v-for="database in databases"
              :key="database.id"
              :name="database.name"
              :value="database.id"
            ></DropdownItem>
          </Dropdown>
        </FormGroup>
      </div>
      <div class="col col-6">
        <FormGroup
          :error="fieldHasErrors('source_table_id')"
          small-label
          :label="$t('localBaserowTableDataSync.table')"
          required
        >
          <Dropdown
            v-model="v$.values.source_table_id.$model"
            :error="fieldHasErrors('source_table_id')"
            :disabled="disabled"
            @input="tableChanged"
          >
            <DropdownItem
              v-for="table in tables"
              :key="table.id"
              :name="table.name"
              :value="table.id"
            ></DropdownItem>
          </Dropdown>
          <template #error>
            {{ v$.values.source_table_id.$errors[0]?.$message }}
          </template>
        </FormGroup>
      </div>
      <div class="col col-6">
        <FormGroup
          :error="fieldHasErrors('source_table_view_id')"
          small-label
          :label="$t('localBaserowTableDataSync.view')"
          :help-icon-tooltip="$t('localBaserowTableDataSync.viewHelper')"
          required
        >
          <div v-if="viewsLoading" class="loading"></div>
          <Dropdown
            v-else
            v-model="v$.values.source_table_view_id.$model"
            :error="fieldHasErrors('source_table_view_id')"
            :disabled="disabled"
            @input="v$.values.source_table_view_id.$touch"
          >
            <DropdownItem
              v-for="view in views"
              :key="view.id"
              :name="view.name"
              :value="view.id"
              :icon="view._.type.iconClass"
            ></DropdownItem>
          </Dropdown>
        </FormGroup>
      </div>
    </div>
  </form>
</template>

<script>
import { useVuelidate } from '@vuelidate/core'
import { mapGetters, mapState } from 'vuex'
import { required, numeric, helpers } from '@vuelidate/validators'

import form from '@baserow/modules/core/mixins/form'
import { DatabaseApplicationType } from '@baserow/modules/database/applicationTypes'
import ViewService from '@baserow/modules/database/services/view'

export default {
  name: 'LocalBaserowTableDataSync',
  mixins: [form],
  props: {
    update: {
      type: Boolean,
      required: false,
      default: false,
    },
    disabled: {
      type: Boolean,
      required: false,
      default: false,
    },
  },
  setup() {
    return { v$: useVuelidate({ $lazy: true }) }
  },
  data() {
    return {
      allowedValues: ['source_table_id', 'source_table_view_id'],
      values: {
        source_table_id: '',
        source_table_view_id: null,
      },
      selectedWorkspaceId:
        this.$store.getters['workspace/getSelected'].id || null,
      selectedDatabaseId: null,
      views: [],
      viewsLoading: false,
    }
  },
  computed: {
    databases() {
      return this.applications
        .filter(
          (application) =>
            application.type === DatabaseApplicationType.getType()
        )
        .filter(
          (application) => application.workspace.id === this.selectedWorkspaceId
        )
    },
    tables() {
      const database = this.databases.find(
        (database) => database.id === this.selectedDatabaseId
      )
      if (database) {
        return database.tables
      }
      return []
    },
    // It's okay to use the local state of workspaces, databases and tables because it
    // gives a representation of what the user has access to. When creating or updating
    // the data sync, it will set the `authorized_user` to the one authenticated user,
    // so that that should always match to which tables the user has access to.
    ...mapState({
      workspaces: (state) => state.workspace.items,
    }),
    ...mapGetters({
      applications: 'application/getAll',
      userName: 'auth/getName',
    }),
  },
  watch: {
    'values.source_table_id'(newValueType, oldValue) {
      if (newValueType !== oldValue) {
        this.loadViewsIfNeeded()
      }
    },
  },
  mounted() {
    // If the source table id is set, the database and workspace ID must be selected
    // in the dropdown.
    if (this.values.source_table_id) {
      const databaseType = DatabaseApplicationType.getType()
      for (const application of this.$store.getters['application/getAll']) {
        if (application.type !== databaseType) {
          continue
        }

        const foundTable = application.tables.find(
          ({ id }) => id === this.values.source_table_id
        )

        if (foundTable) {
          this.selectedWorkspaceId = application.workspace.id
          this.selectedDatabaseId = application.id
          break
        }
      }
    }
  },
  validations() {
    return {
      values: {
        source_table_id: {
          required: helpers.withMessage(
            this.$t('error.requiredField'),
            required
          ),
          numeric,
        },
        source_table_view_id: { numeric },
      },
    }
  },
  methods: {
    workspaceChanged(value) {
      if (this.selectedWorkspaceId === value) {
        return
      }
      this.selectedWorkspaceId = value
      this.selectedDatabaseId = null
      this.values.source_table_id = null
      this.values.source_table_view_id = null
    },
    databaseChanged(value) {
      if (this.selectedDatabaseId === value) {
        return
      }
      this.selectedDatabaseId = value
      this.values.source_table_id = null
      this.values.source_table_view_id = null
    },
    tableChanged(value) {
      this.v$.values.source_table_id.$touch()
      if (this.values.source_table_id === value) {
        return
      }
      this.values.source_table_id = value
      this.values.source_table_view_id = null
    },
    async loadViewsIfNeeded() {
      if (this.values.source_table_id === null) {
        return
      }

      this.viewsLoading = true

      try {
        // Because the authorized user changes when a view is created or updated, it's
        // fine to just fetch all the views that the user has access to.
        const { data } = await ViewService(this.$client).fetchAll(
          this.values.source_table_id,
          false,
          false,
          false,
          false
        )
        this.views = data
          .filter((view) => {
            const viewType = this.$registry.get('view', view.type)
            return viewType.canFilter
          })
          .map((view) => {
            const viewType = this.$registry.get('view', view.type)
            view._ = { type: viewType.serialize() }
            return view
          })
          .sort((a, b) => {
            return a.order - b.order
          })
      } finally {
        this.viewsLoading = false
      }
    },
  },
}
</script>
