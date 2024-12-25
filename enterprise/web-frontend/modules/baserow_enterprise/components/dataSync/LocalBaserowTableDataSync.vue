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
      <div class="col col-4">
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
      <div class="col col-4">
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
      <div class="col col-4">
        <FormGroup
          :error="fieldHasErrors('source_table_id')"
          small-label
          :label="$t('localBaserowTableDataSync.table')"
          required
        >
          <Dropdown
            v-model="values.source_table_id"
            :error="fieldHasErrors('source_table_id')"
            :disabled="disabled"
            @input="$v.values.source_table_id.$touch()"
          >
            <DropdownItem
              v-for="table in tables"
              :key="table.id"
              :name="table.name"
              :value="table.id"
            ></DropdownItem>
          </Dropdown>
          <template #error>
            <div
              v-if="
                $v.values.source_table_id.$dirty &&
                !$v.values.source_table_id.required
              "
            >
              {{ $t('error.requiredField') }}
            </div>
          </template>
        </FormGroup>
      </div>
    </div>
  </form>
</template>

<script>
import { mapGetters, mapState } from 'vuex'
import { required, numeric } from 'vuelidate/lib/validators'

import form from '@baserow/modules/core/mixins/form'
import { DatabaseApplicationType } from '@baserow/modules/database/applicationTypes'

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
  data() {
    return {
      allowedValues: ['source_table_id'],
      values: {
        source_table_id: '',
      },
      selectedWorkspaceId:
        this.$store.getters['workspace/getSelected'].id || null,
      selectedDatabaseId: null,
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
  validations: {
    values: {
      source_table_id: { required, numeric },
    },
  },
  methods: {
    workspaceChanged(value) {
      if (this.selectedWorkspaceId === value) {
        return
      }
      this.selectedWorkspaceId = value
      this.selectedDatabaseId = null
      this.values.source_table_id = null
    },
    databaseChanged(value) {
      if (this.selectedDatabaseId === value) {
        return
      }
      this.selectedDatabaseId = value
      this.values.source_table_id = null
    },
  },
}
</script>
