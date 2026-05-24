<template>
  <form @submit.prevent="submit">
    <FormGroup
      :label="$t('dataScanner.nameLabel')"
      required
      small-label
      class="margin-bottom-2"
      :error="v$.values.name.$error"
    >
      <FormInput
        v-model="v$.values.name.$model"
        :placeholder="$t('dataScanner.namePlaceholder')"
        :error="v$.values.name.$error"
        @blur="v$.values.name.$touch()"
      />
      <template #error>
        {{ v$.values.name.$errors[0]?.$message }}
      </template>
    </FormGroup>

    <FormGroup
      :label="$t('dataScanner.scanTypeLabel')"
      required
      small-label
      class="margin-bottom-2"
    >
      <Dropdown v-model="values.scan_type" :show-search="false">
        <DropdownItem
          :name="$t('dataScanner.scanTypePattern')"
          value="pattern"
        />
        <DropdownItem
          :name="$t('dataScanner.scanTypeListOfValues')"
          value="list_of_values"
        />
        <DropdownItem
          :name="$t('dataScanner.scanTypeListTable')"
          value="list_table"
        />
      </Dropdown>
    </FormGroup>

    <template v-if="values.scan_type === 'pattern'">
      <FormGroup
        :label="$t('dataScanner.patternLabel')"
        required
        small-label
        class="margin-bottom-2"
        :error="v$.values.pattern.$error"
      >
        <FormInput
          v-model="v$.values.pattern.$model"
          :placeholder="$t('dataScanner.patternPlaceholder')"
          :error="v$.values.pattern.$error"
          maxlength="100"
          @blur="v$.values.pattern.$touch()"
        />
        <template #error>
          {{ v$.values.pattern.$errors[0]?.$message }}
        </template>
        <template #helper>
          {{ $t('dataScanner.patternHelp') }}
        </template>
      </FormGroup>
    </template>

    <template v-if="values.scan_type === 'list_of_values'">
      <FormGroup
        :label="$t('dataScanner.listItemsLabel')"
        required
        small-label
        class="margin-bottom-2"
        :error="v$.values.list_items.$error"
      >
        <FormTextarea
          v-model="listItemsText"
          :placeholder="$t('dataScanner.listItemsPlaceholder')"
          rows="6"
        />
        <template #error>
          {{ v$.values.list_items.$errors[0]?.$message }}
        </template>
        <template #helper>
          {{ $t('dataScanner.listItemsHelp') }}
        </template>
      </FormGroup>
    </template>

    <template v-if="values.scan_type === 'list_table'">
      <FormGroup
        :label="$t('dataScanner.sourceTableLabel')"
        required
        small-label
        class="margin-bottom-2"
      >
        <div class="row margin-bottom-1">
          <div class="col col-6">
            <PaginatedDropdown
              :value="selectedWorkspaceId"
              :fetch-page="fetchWorkspaces"
              :empty-item-display-name="$t('dataScanner.selectWorkspace')"
              :not-selected-text="$t('dataScanner.selectWorkspace')"
              @input="onWorkspaceSelected"
            />
          </div>
          <div class="col col-6">
            <Dropdown
              v-model="selectedDatabaseId"
              :show-search="true"
              :placeholder="$t('dataScanner.selectDatabase')"
              :disabled="databases.length === 0"
            >
              <DropdownItem
                v-for="db in databases"
                :key="db.id"
                :name="db.name"
                :value="db.id"
              />
            </Dropdown>
          </div>
        </div>
        <div class="row">
          <div class="col col-6">
            <Dropdown
              v-model="values.source_table_id"
              :show-search="true"
              :placeholder="$t('dataScanner.selectTable')"
              :disabled="tables.length === 0"
            >
              <DropdownItem
                v-for="table in tables"
                :key="table.id"
                :name="table.name"
                :value="table.id"
              />
            </Dropdown>
          </div>
          <div class="col col-6">
            <Dropdown
              v-model="v$.values.source_field_id.$model"
              :show-search="true"
              :placeholder="$t('dataScanner.selectField')"
              :disabled="tableFields.length === 0"
              :error="v$.values.source_field_id.$error"
            >
              <DropdownItem
                v-for="field in tableFields"
                :key="field.id"
                :name="field.name"
                :value="field.id"
              />
            </Dropdown>
            <div v-if="v$.values.source_field_id.$error" class="error">
              {{ v$.values.source_field_id.$errors[0]?.$message }}
            </div>
          </div>
        </div>
        <Alert
          v-if="values.source_table_id && tableFields.length === 0"
          type="info-neutral"
          class="margin-top-1"
        >
          <template #title>{{
            $t('dataScanner.noCompatibleFieldsTitle')
          }}</template>
          <p>{{ $t('dataScanner.noCompatibleFieldsDescription') }}</p>
        </Alert>
      </FormGroup>
    </template>

    <FormGroup
      :label="$t('dataScanner.wholeWordsLabel')"
      small-label
      class="margin-bottom-2"
    >
      <Checkbox v-model="values.whole_words">
        {{ $t('dataScanner.wholeWordsCheckbox') }}
      </Checkbox>
      <template #helper>
        {{ $t('dataScanner.wholeWordsHelp') }}
      </template>
    </FormGroup>

    <FormGroup
      :label="$t('dataScanner.frequencyLabel')"
      small-label
      class="margin-bottom-2"
    >
      <Dropdown v-model="values.frequency" :show-search="false">
        <DropdownItem
          :name="$t('dataScanner.frequencyManual')"
          value="manual"
        />
        <DropdownItem
          :name="$t('dataScanner.frequencyHourly')"
          value="hourly"
        />
        <DropdownItem :name="$t('dataScanner.frequencyDaily')" value="daily" />
        <DropdownItem
          :name="$t('dataScanner.frequencyWeekly')"
          value="weekly"
        />
      </Dropdown>
      <Alert
        v-if="values.frequency === 'hourly'"
        type="warning"
        class="margin-top-1 margin-bottom-1"
      >
        <template #title>{{ $t('dataScanner.hourlyWarning') }}</template>
      </Alert>
    </FormGroup>

    <FormGroup
      :label="$t('dataScanner.workspaceScopeLabel')"
      small-label
      class="margin-bottom-2"
      :error="v$.values.workspace_ids.$error"
    >
      <Checkbox v-model="values.scan_all_workspaces">
        {{ $t('dataScanner.scanAllWorkspaces') }}
      </Checkbox>
      <div v-if="!values.scan_all_workspaces" class="margin-top-1">
        <PaginatedDropdown
          ref="workspaceScopeDropdown"
          :value="null"
          :fetch-page="fetchWorkspaces"
          :empty-item-display-name="$t('dataScanner.addWorkspace')"
          :not-selected-text="$t('dataScanner.addWorkspace')"
          :include-display-name-in-selected-event="true"
          @input="addWorkspace"
        />
        <div v-if="workspaceNamesLoading" class="loading margin-top-1"></div>
        <ul
          v-else-if="selectedWorkspaceNames.length > 0"
          class="data-scanner__tag-items margin-top-1"
        >
          <li
            v-for="ws in selectedWorkspaceNames"
            :key="ws.id"
            class="data-scanner__tag-item"
          >
            <span class="data-scanner__tag-name">{{ ws.name }}</span>
            <a
              class="data-scanner__tag-remove"
              @click.prevent="removeWorkspace(ws.id)"
            >
              <i class="iconoir-cancel" />
            </a>
          </li>
        </ul>
      </div>
      <template #error>
        {{ v$.values.workspace_ids.$errors[0]?.$message }}
      </template>
    </FormGroup>

    <slot />
  </form>
</template>

<script>
import form from '@baserow/modules/core/mixins/form'
import { useVuelidate } from '@vuelidate/core'
import { required, requiredIf, maxLength, helpers } from '@vuelidate/validators'
import { notifyIf } from '@baserow/modules/core/utils/error'
import { DataScannerScansService } from '@baserow_enterprise/services/dataScanner'
import { ADMIN_WORKSPACE_OPTIONS_URL } from '@baserow_enterprise/services/adminWorkspaces'
import PaginatedDropdown from '@baserow/modules/core/components/PaginatedDropdown'
import baseService from '@baserow/modules/core/crudTable/baseService'

export default {
  name: 'DataScanForm',
  components: {
    PaginatedDropdown,
  },
  mixins: [form],
  setup() {
    return { v$: useVuelidate() }
  },
  emits: ['submitted'],
  data() {
    return {
      values: {
        name: '',
        scan_type: 'pattern',
        pattern: '',
        frequency: 'manual',
        scan_all_workspaces: true,
        workspace_ids: [],
        list_items: [],
        source_table_id: null,
        source_field_id: null,
        whole_words: true,
      },
      listItemsText: '',
      selectedWorkspaceId: null,
      selectedDatabaseId: null,
      selectedWorkspaceNames: [],
      workspaceNamesLoading: false,
      workspaceStructure: [],
      structureLoading: false,
    }
  },
  validations() {
    return {
      values: {
        name: {
          required: helpers.withMessage(
            this.$t('error.requiredField'),
            required
          ),
        },
        pattern: {
          required: helpers.withMessage(
            this.$t('error.requiredField'),
            requiredIf(() => this.values.scan_type === 'pattern')
          ),
          maxLength: helpers.withMessage(
            this.$t('error.maxLength', { max: 100 }),
            maxLength(100)
          ),
        },
        list_items: {
          listItemsRequired: helpers.withMessage(
            this.$t('error.requiredField'),
            (value) => {
              if (this.values.scan_type !== 'list_of_values') return true
              return Array.isArray(value) && value.length > 0
            }
          ),
        },
        source_field_id: {
          required: helpers.withMessage(
            this.$t('error.requiredField'),
            requiredIf(() => this.values.scan_type === 'list_table')
          ),
        },
        workspace_ids: {
          required: helpers.withMessage(
            this.$t('error.requiredField'),
            (value) => {
              if (this.values.scan_all_workspaces) return true
              return Array.isArray(value) && value.length > 0
            }
          ),
        },
      },
    }
  },
  computed: {
    databases() {
      if (!this.selectedWorkspaceId || this.workspaceStructure.length === 0) {
        return []
      }
      return this.workspaceStructure
    },
    tables() {
      if (!this.selectedDatabaseId) return []
      const db = this.databases.find((d) => d.id === this.selectedDatabaseId)
      if (!db || !db.tables) return []
      return db.tables
    },
    tableFields() {
      if (!this.values.source_table_id) return []
      const table = this.tables.find(
        (t) => t.id === this.values.source_table_id
      )
      if (!table || !table.fields) return []
      return table.fields
    },
  },
  watch: {
    selectedWorkspaceId(newVal, oldVal) {
      if (oldVal !== null) {
        this.selectedDatabaseId = null
        this.values.source_table_id = null
        this.values.source_field_id = null
      }
      this.workspaceStructure = []
      if (newVal) {
        this.fetchWorkspaceStructure(newVal)
      }
    },
    selectedDatabaseId(newVal, oldVal) {
      if (oldVal !== null) {
        this.values.source_table_id = null
        this.values.source_field_id = null
      }
    },
    'values.source_table_id'(newVal, oldVal) {
      if (oldVal !== null) {
        this.values.source_field_id = null
      }
    },
    listItemsText(val) {
      this.values.list_items = val
        .split('\n')
        .map((line) => line.trim())
        .filter((line) => line.length > 0)
    },
  },
  async mounted() {
    if (this.values.list_items.length > 0) {
      this.listItemsText = this.values.list_items.join('\n')
    }
    if (
      this.values.source_workspace_id &&
      this.values.scan_type === 'list_table'
    ) {
      this.selectedWorkspaceId = this.values.source_workspace_id
    }
    if (
      !this.values.scan_all_workspaces &&
      this.values.workspace_ids.length > 0
    ) {
      await this.fetchWorkspaceNamesByIds(this.values.workspace_ids)
    }
  },
  methods: {
    fetchWorkspaces(page, search) {
      const workspacePaginatedService = baseService(
        this.$client,
        ADMIN_WORKSPACE_OPTIONS_URL
      )
      return workspacePaginatedService.fetch(
        ADMIN_WORKSPACE_OPTIONS_URL,
        page,
        search,
        [],
        {}
      )
    },
    onWorkspaceSelected(value) {
      this.selectedWorkspaceId = value
    },
    async fetchWorkspaceStructure(workspaceId) {
      this.structureLoading = true
      try {
        const { data } = await DataScannerScansService(
          this.$client
        ).fetchWorkspaceStructure(workspaceId)
        this.workspaceStructure = data
        // Restore database selection for edit mode
        if (this.values.source_database_id) {
          this.selectedDatabaseId = this.values.source_database_id
          // Clear so it doesn't interfere on subsequent workspace changes
          this.values.source_database_id = null
        }
        // Clear source field if it's no longer in the compatible fields list
        // (e.g. the field type was changed to an incompatible one).
        if (
          this.values.source_field_id &&
          !this.tableFields.some((f) => f.id === this.values.source_field_id)
        ) {
          this.values.source_field_id = null
        }
      } catch (error) {
        notifyIf(error)
      } finally {
        this.structureLoading = false
      }
    },
    async fetchWorkspaceNamesByIds(ids) {
      this.workspaceNamesLoading = true
      try {
        const { data } = await baseService(
          this.$client,
          ADMIN_WORKSPACE_OPTIONS_URL
        ).fetchByIds(ADMIN_WORKSPACE_OPTIONS_URL, ids)
        this.selectedWorkspaceNames = (data.results || []).map((ws) => ({
          id: ws.id,
          name: ws.value,
        }))
      } catch (error) {
        notifyIf(error)
      } finally {
        this.workspaceNamesLoading = false
      }
    },
    addWorkspace(selection) {
      if (selection === null) return
      const workspaceId = selection.value != null ? selection.value : selection
      const displayName = selection.displayName || `Workspace ${workspaceId}`
      if (
        workspaceId !== null &&
        !this.values.workspace_ids.includes(workspaceId)
      ) {
        this.values.workspace_ids = [...this.values.workspace_ids, workspaceId]
        this.selectedWorkspaceNames.push({ id: workspaceId, name: displayName })
      }
    },
    removeWorkspace(workspaceId) {
      this.values.workspace_ids = this.values.workspace_ids.filter(
        (id) => id !== workspaceId
      )
      this.selectedWorkspaceNames = this.selectedWorkspaceNames.filter(
        (ws) => ws.id !== workspaceId
      )
    },
    submit() {
      this.v$.$touch()
      if (this.v$.$invalid) return

      const data = { ...this.values }

      if (data.scan_type !== 'pattern') {
        delete data.pattern
      }
      if (data.scan_type !== 'list_of_values') {
        delete data.list_items
      }
      if (data.scan_type !== 'list_table') {
        delete data.source_table_id
        delete data.source_field_id
      }
      if (data.scan_all_workspaces) {
        delete data.workspace_ids
      }

      // Clean up internal fields not needed by API
      delete data.source_workspace_id
      delete data.source_database_id

      this.$emit('submitted', data)
    },
  },
}
</script>
