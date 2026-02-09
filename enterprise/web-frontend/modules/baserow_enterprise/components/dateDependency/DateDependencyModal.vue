<template>
  <Modal
    v-if="isAllowed"
    ref="modal"
    :small="true"
    :content-padding="false"
    @show="init()"
    @hidden="ready = false"
  >
    <h2 class="box__title">
      {{ $t('dateDependencyModal.title', { tableName: table.name }) }}
    </h2>
    <p>
      {{ $t('dateDependencyModal.description') }}
    </p>

    <div v-if="!ready" class="loading"></div>
    <form v-else @submit.prevent="submit">
      <div v-if="dependency.id" class="row">
        <div class="col">
          <SwitchInput
            v-model="v$.dependency.is_active.$model"
            class="margin-bottom-2"
            small
          >
            <span>{{ $t('dateDependencyModal.enableDateDependency') }}</span>
          </SwitchInput>
        </div>
      </div>

      <template v-if="dependency.is_active">
        <div class="row date-dependency__container">
          <div class="col col-6">
            <DateDependencyFieldPicker
              ref="start_date_field_id"
              v-model="v$.dependency.start_date_field_id.$model"
              required
              :fields="startDateFields"
              icon="iconoir-calendar"
              :errors="v$.dependency.start_date_field_id.$errors"
              :field-name="$t('dateDependencyModal.startDateFieldLabel')"
              add-new
              @add-new="addNewField('start_date_field_id')"
            />
          </div>
          <div class="col col-6">
            <DateDependencyFieldPicker
              ref="end_date_field_id"
              v-model="v$.dependency.end_date_field_id.$model"
              required
              :fields="endDateFields"
              :errors="v$.dependency.end_date_field_id.$errors"
              icon="iconoir-calendar"
              :field-name="$t('dateDependencyModal.endDateFieldLabel')"
              add-new
              @add-new="addNewField('end_date_field_id')"
            />
          </div>
        </div>
        <div class="row date-dependency__container">
          <div class="col col-6">
            <DateDependencyFieldPicker
              ref="duration_field_id"
              v-model="v$.dependency.duration_field_id.$model"
              required
              :fields="durationFields"
              :errors="v$.dependency.duration_field_id.$errors"
              icon="iconoir-clock-rotate-right"
              :field-name="$t('dateDependencyModal.durationFieldLabel')"
              :helper-text="$t('dateDependencyModal.durationFieldHint')"
              add-new
              @add-new="addNewField('duration_field_id')"
            />
          </div>

          <div class="col col-6">
            <DateDependencyFieldPicker
              ref="dependency_linkrow_field_id"
              v-model="v$.dependency.dependency_linkrow_field_id.$model"
              :fields="linkrowFields"
              :required="false"
              :errors="v$.dependency.dependency_linkrow_field_id.$errors"
              icon="iconoir-clock-rotate-right"
              :field-name="
                $t('dateDependencyModal.dependencyLinkrowFieldLabel')
              "
              :helper-text="
                $t('dateDependencyModal.dependencyLinkrowFieldHint')
              "
              add-new
              @add-new="addNewField('dependency_linkrow_field_id')"
            />
          </div>
        </div>
      </template>
      <div class="row context__form-footer-actions--align-right">
        <div>
          <Button :loading="loading" @click.prevent.stop="submit">
            {{ $t('action.save') }}
          </Button>
        </div>
      </div>
    </form>
  </Modal>
</template>
<script>
import modal from '@baserow/modules/core/mixins/modal'

import DateDependencyFieldPicker from '@baserow_enterprise/components/dateDependency/DateDependencyFieldPicker'
import _ from 'lodash'

import { useVuelidate } from '@vuelidate/core'
import { required, requiredIf } from '@vuelidate/validators'
import { ResponseErrorMessage } from '@baserow/modules/core/plugins/clientHandler'
import FieldService from '@baserow/modules/database/services/field'
import { notifyIf } from '@baserow/modules/core/utils/error'
import { getNextAvailableNameInSequence } from '@baserow/modules/core/utils/string'

export default {
  name: 'DateDependencyModal',
  components: {
    DateDependencyFieldPicker,
  },
  mixins: [modal],
  props: {
    table: {
      type: Object,
      required: true,
    },
    workspaceId: {
      type: Number,
      required: true,
    },
    tableFields: {
      type: [Array, null],
      required: false,
      default: null,
    },
  },
  setup() {
    return { v$: useVuelidate() }
  },
  data() {
    return {
      // skeleton value
      dependency: {
        id: null,
        table_id: this.table.id,
        type: 'date_dependency',
        is_active: true,
        start_date_field_id: null,
        end_date_field_id: null,
        duration_field_id: null,
        dependency_linkrow_field_id: null,
      },
      loading: false,
      fields: [],
      ready: false,
    }
  },
  validations() {
    return {
      dependency: {
        is_active: { required },
        start_date_field_id: {
          requiredIfIsActive: requiredIf(() => {
            return this.dependency.is_active
          }),
        },
        end_date_field_id: {
          requiredIfIsActive: requiredIf(() => {
            return this.dependency.is_active
          }),
        },
        duration_field_id: {
          requiredIfIsActive: requiredIf(() => {
            return this.dependency.is_active
          }),
        },
        dependency_linkrow_field_id: {},
      },
    }
  },
  computed: {
    isAllowed() {
      return this.$hasPermission(
        'database.table.field_rules.set_field_rules',
        this.table,
        this.workspaceId
      )
    },
    endDateFields() {
      // we want to exclude field that is used in start date field
      const excludeId = this.dependency.start_date_field_id
      return this.getFieldsForType(this.fields, 'date', (f) => {
        return !(f.id === excludeId || f.date_include_time)
      })
    },
    startDateFields() {
      // we want to exclude field that is used in end date field
      const excludeId = this.dependency.end_date_field_id
      return this.getFieldsForType(this.fields, 'date', (f) => {
        return !(f.id === excludeId || f.date_include_time)
      })
    },
    durationFields() {
      return this.getFieldsForType(this.fields, 'duration', (f) => {
        return f.duration_format === 'd h'
      })
    },
    linkrowFields() {
      const tableId = this.table.id
      const fields = this.getFieldsForType(this.fields, 'link_row', (x) => {
        return x.link_row_table_id === tableId
      })
      // Empty row allows to deselect link row field
      fields.unshift({ id: null, name: '' })
      return fields
    },
  },
  methods: {
    async handleCreateField(value) {
      const { forceCreateCallback, newField } = await this.$store.dispatch(
        'field/create',
        {
          ...value,
          forceCreate: false,
        }
      )

      // The fields store is context-sensitive, and shows fields for the current table
      // only, so we should add the field only if the modal has been opened for the
      // current table.
      if (this.table.id === this.$store.getters['table/getSelectedId']) {
        if (_.isFunction(forceCreateCallback)) {
          await forceCreateCallback()
        }
      }

      return newField
    },
    async addNewField(dependencyFieldName) {
      try {
        return await this._addNewField(dependencyFieldName)
      } catch (error) {
        notifyIf(error)
      }
    },

    async _addNewField(dependencyFieldName) {
      // Defaults for new fields depending on a configuration field.
      // We need to have access to instance variables, so this is inside a method.
      const FIELDS_DEFAULTS = {
        dependency_linkrow_field_id: {
          type: 'link_row',
          table: this.table,
          values: {
            link_row_table_id: this.table.id,
            name: this.$t('dateDependencyModal.linkRowFieldTitle'),
          },
        },
        duration_field_id: {
          type: 'duration',
          table: this.table,
          values: {
            duration_format: 'd h',
            table: this.table.id,
            name: this.$t('dateDependencyModal.durationFieldLabel'),
          },
        },
        start_date_field_id: {
          type: 'date',
          table: this.table,
          values: {
            date_include_time: false,
            table: this.table.id,
            name: this.$t('dateDependencyModal.startDateFieldLabel'),
          },
        },
        end_date_field_id: {
          type: 'date',
          table: this.table,
          values: {
            date_include_time: false,
            table: this.table.id,
            name: this.$t('dateDependencyModal.endDateFieldLabel'),
          },
        },
      }

      const fieldDef = _.clone(FIELDS_DEFAULTS[dependencyFieldName])

      const usedFieldNames = _.map(this.fields, 'name')

      const fieldName = getNextAvailableNameInSequence(
        fieldDef.values.name,
        usedFieldNames
      )
      fieldDef.values.name = fieldName

      const fieldCreated = await this.handleCreateField(fieldDef)
      // fields is not using fields store, so we need to update it manually
      this.fields.push(fieldCreated)
      this.dependency[dependencyFieldName] = fieldCreated.id
    },

    async fetchFields() {
      // If the fields are already provided as a prop, we don't need to fetch them
      if (this.tableFields?.length > 0) {
        return this.tableFields
      }

      try {
        const { data: fields } = await FieldService(this.$client).fetchAll(
          this.table.id
        )
        return fields
      } catch (error) {
        notifyIf(error, 'field')
      }
    },

    getFieldsForType(fields, expectedType, extraFilters = null) {
      return Array.from(fields).filter((f) => {
        if (f.type === expectedType && !f.read_only) {
          return !_.isFunction(extraFilters) || extraFilters(f)
        }
        return false
      })
    },

    async init() {
      try {
        this.fields = await this.fetchFields(this.table.id)

        await this.$store.dispatch('fieldRules/fetchInitial', {
          tableId: this.table.id,
        })
        const dateDependencyRules = this.$store.getters[
          'fieldRules/getRulesByType'
        ]({
          tableId: this.table.id,
          ruleType: 'date_dependency',
        })
        const rule =
          dateDependencyRules.length > 0 ? dateDependencyRules[0] : null
        if (rule) {
          this.dependency = this.parseRule(rule)
        }

        this.ready = true
      } catch (err) {
        await this.$store.dispatch('toast/error', err)
      }
    },

    preparePayload() {
      const payload = {
        id: this.dependency.id,
        table_id: this.table.id,
        type: this.dependency.type,
        is_active: this.dependency.is_active,
      }
      if (this.dependency.is_active) {
        payload.start_date_field_id = this.dependency.start_date_field_id
        payload.end_date_field_id = this.dependency.end_date_field_id
        payload.duration_field_id = this.dependency.duration_field_id
        payload.dependency_linkrow_field_id =
          this.dependency.dependency_linkrow_field_id
      }
      return payload
    },

    parseRule(rule) {
      const startFieldId = this.startDateFields.find(
        (f) => f.id === rule.start_date_field_id
      )?.id

      const endFieldId = this.endDateFields.find(
        (f) => f.id === rule.end_date_field_id
      )?.id

      const durationFieldId = this.durationFields.find(
        (f) => f.id === rule.duration_field_id
      )?.id
      const dependencyLinkrowFieldId = this.linkrowFields.find(
        (f) => f.id === rule.dependency_linkrow_field_id
      )?.id

      return {
        ...this.dependency,
        id: rule.id,
        is_active: rule.is_active,
        start_date_field_id: startFieldId || null,
        end_date_field_id: endFieldId || null,
        duration_field_id: durationFieldId || null,
        dependency_linkrow_field_id: dependencyLinkrowFieldId || null,
      }
    },

    async submit() {
      this.v$.$touch()
      if (this.v$.$invalid) {
        return
      }

      try {
        const payload = this.preparePayload()

        let rule = null
        try {
          this.loading = true
          if (this.dependency.id) {
            rule = await this.$store.dispatch('fieldRules/updateRule', {
              tableId: this.table.id,
              ruleId: this.dependency.id,
              rule: payload,
            })
          } else {
            rule = await this.$store.dispatch('fieldRules/addRule', {
              tableId: this.table.id,
              rule: payload,
            })
          }
        } catch (error) {
          return this.handleError(error)
        } finally {
          this.loading = false
        }

        const stored = this.$store.getters['fieldRules/getRuleById']({
          tableId: this.table.id,
          ruleId: rule.id,
        })
        this.dependency = this.parseRule(stored)

        this.$refs.modal?.hide()
      } catch (error) {
        return this.handleError(error)
      }
    },

    handleError(error) {
      if (!error.handler || !!error.handler?.isHandled) {
        return
      }

      // Other errors we show as a toast
      const $t = this.$t.bind(this)

      const requestErrorsMap = {
        ERROR_RULE_DOES_NOT_EXIST: new ResponseErrorMessage(
          $t('fieldRule.errorTitle'),
          $t('fieldRule.ruleDoesNotExist')
        ),
        ERROR_RULE_TYPE_DOES_NOT_EXIST: new ResponseErrorMessage(
          $t('fieldRule.errorTitle'),
          $t('fieldRule.ruleTypeDoesNotExist')
        ),
        ERROR_RULE_ALREADY_EXIST: new ResponseErrorMessage(
          $t('fieldRule.errorTitle'),
          $t('fieldRule.ruleAlreadyExists')
        ),
      }

      const msg =
        error.handler?.getMessage(
          $t('dateDependencyModal.errorTitle'),
          requestErrorsMap,
          {}
        ) || {}
      this.$store.dispatch('toast/error', msg)
      error.handler?.handled()
    },
  },
}
</script>
