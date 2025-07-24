<template>
  <Modal
    ref="modal"
    :small="true"
    :content-padding="false"
    @show="init()"
    @hide="onModalClose()"
  >
    <h2 class="box__title">
      {{ $t('dateDependencyModal.title', { tableName: table.name }) }}
    </h2>
    <p>
      {{ $t('dateDependencyModal.description') }}
    </p>
    <div class="row">
      <div class="col">
        <SwitchInput
          class="margin-bottom-2"
          small
          :disabled="false"
          :value="dependency.is_active"
          @input="toggleDateDependency()"
        >
          <span>{{ $t('dateDependencyModal.enableDateDependency') }}</span>
        </SwitchInput>
      </div>
    </div>

    <form v-if="dependency.is_active" @submit.prevent="submit">
      <div class="row date-dependency__container">
        <div class="col col-6">
          <DateDependencyFieldPicker
            :value="dependency.start_date_field_id"
            :fields="startDateFields"
            :required="true"
            icon="iconoir-calendar"
            :error="v$.dependency?.start_date_field_id.$error"
            :field-name="$t('dateDependencyModal.startDateFieldLabel')"
            @change="onDependencyFieldChange('start_date_field_id', $event)"
          />
        </div>
        <div class="col col-6">
          <DateDependencyFieldPicker
            :value="dependency.end_date_field_id"
            :fields="endDateFields"
            :required="true"
            :error="v$.dependency?.end_date_field_id.$error"
            icon="iconoir-calendar"
            :field-name="$t('dateDependencyModal.endDateFieldLabel')"
            @change="onDependencyFieldChange('end_date_field_id', $event)"
          />
        </div>
      </div>
      <div class="row date-dependency__container">
        <div class="col col-6">
          <DateDependencyFieldPicker
            :value="dependency.duration_field_id"
            :fields="durationFields"
            :required="true"
            :error="v$.dependency?.duration_field_id.$error"
            icon="iconoir-clock-rotate-right"
            :field-name="$t('dateDependencyModal.durationFieldLabel')"
            :helper-text="$t('dateDependencyModal.durationFieldHint')"
            @change="onDependencyFieldChange('duration_field_id', $event)"
          />
        </div>
        <div class="col col-6">
          <DateDependencyFieldPicker
            :value="dependency.dependency_linkrow_field_id"
            :fields="dependencyFields"
            :error="v$.dependency?.dependency_linkrow_field_id.$error"
            icon="iconoir-ev-plug"
            :field-name="$t('dateDependencyModal.dependencyFieldLabel')"
            :helper-text="$t('dateDependencyModal.dependencyFieldHint')"
            @change="
              onDependencyFieldChange('dependency_linkrow_field_id', $event)
            "
          />
        </div>
      </div>
      <div class="row date-dependency__container">
        <div class="col">
          <!-- predecessors / successors -->
          <SegmentControl
            ref="linkRowRoleControl"
            size="regular"
            :segments="dependencyLinkRowRoles"
            :error="v$.dependency?.dependency_linkrow_role.$error"
            :initial-active-index="linkrowFieldRoleIdx"
            @update:activeIndex="linkRowFieldRoleChanged($event)"
          />
        </div>
      </div>

      <div class="row date-dependency__container">
        <!-- rescheduling logic: flexible/fixed/none -->
        <div class="col col-12">
          <DateDependencyFieldPicker
            class="noop"
            :value="dependency.dependency_buffer_type"
            :fields="dependencyBufferTypes"
            :error="v$.dependency?.dependency_buffer_type.$error"
            :required="dependency.dependency_linkrow_field_id !== null"
            :field-name="$t('dateDependencyModal.dependencyBufferTypeLabel')"
            @change="onDependencyFieldChange('dependency_buffer_type', $event)"
          />
        </div>
      </div>
      <div class="row">
        <div class="col col-6">
          <FormGroup
            :label="$t('dateDependencyModal.durationBufferLabel')"
            :small-label="true"
            :required="dependency.dependency_linkrow_field_id !== null"
            class="field-duration"
          >
            <!--      :placeholder="field.duration_format"-->
            <!--      :error="touched && !valid"-->
            <!--      :disabled="readOnly"-->
            <!--      class="field-duration"-->
            <!--      @keypress="onKeyPress(field, $event)"-->
            <!--      @keyup.enter="$refs.input.blur()"-->
            <!--      @keyup="updateCopy(field, $event.target.value)"-->
            <!--      @focus="select()"-->
            <!--      @blur="unselect()"-->

            <FormInput
              ref="dateDependencyDuration"
              :value="dependencyBufferValue"
              :error="v$.dependency?.dependency_buffer.$error"
              size="regular"
              class="field-duration"
              @blur="onTimeBufferChange"
            />
          </FormGroup>
        </div>
        <div class="col col-6">
          <!-- end-to-start/end-to-end/start-to-end/start-to-start -->
          <DateDependencyFieldPicker
            :value="dependency.dependency_connection_type"
            :fields="dependencyConnectionTypes"
            :error="v$.dependency?.dependency_connection_type?.$error"
            :required="dependency.dependency_linkrow_field_id !== null"
            :field-name="
              $t('dateDependencyModal.dependencyConnectionTypeLabel')
            "
            @change="
              onDependencyFieldChange('dependency_connection_type', $event)
            "
          />
        </div>
      </div>

      <div class="row date-dependency__container">
        <div class="col">
          <Checkbox
            :checked="dependency.include_weekends"
            :error="v$.dependency?.include_weekends?.$error"
            :title="$t('dateDependencyModal.advancedSettingsLabel')"
            @input="onDependencyFieldChange('include_weekends', $event)"
          >
            {{ $t('dateDependencyModal.includeWeekendsLabel') }}
          </Checkbox>
        </div>
      </div>
      <div class="row context__form-footer-actions--align-right">
        <div>
          <span class="margin-right-2">
            <a class="form-action" @click="cancel">{{ $t('action.cancel') }}</a>
          </span>

          <Button
            :loading="loading"
            :disabled="loading"
            @click.prevent.stop="submit"
          >
            {{ $t('action.save') }}
          </Button>
        </div>
      </div>
    </form>
    <form v-else-if="dependency.id !== null" @submit.prevent="submit()">
      <div class="row context__form-footer-actions--align-right">
        <div class="col">
          <span class="margin-right-2">
            <a class="form-action" @click="cancel">{{ $t('action.cancel') }}</a>
          </span>

          <Button
            :loading="loading"
            :disabled="loading"
            @click.prevent.stop="submit"
          >
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
import FieldService from '@baserow/modules/database/services/field'
import SegmentControl from '@baserow/modules/core/components/SegmentControl'
import FormInput from '@baserow/modules/core/components/FormInput'
import Checkbox from '@baserow/modules/core/components/Checkbox'
import {
  DependencyBufferType,
  DependencyConnectionTypes,
  DependencyLinkRowRoles,
} from '@baserow_enterprise/dateDependency'

import _ from 'lodash'
import {
  formatDurationValue,
  parseDurationValue,
} from '@baserow/modules/database/utils/duration'

import { useVuelidate } from '@vuelidate/core'
import { required, requiredIf } from '@vuelidate/validators'

export default {
  name: 'DateDependencyModal',
  components: {
    DateDependencyFieldPicker,
    SegmentControl,
    FormInput,
    Checkbox,
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
        is_active: false,
        start_date_field_id: null,
        end_date_field_id: null,
        duration_field_id: null,
        dependency_linkrow_field_id: null,
        dependency_linkrow_role: DependencyLinkRowRoles.PREDECESSORS,
        dependency_buffer_type: DependencyBufferType.FLEXIBLE,
        dependency_buffer: 0,
        include_weekends: false,
        dependency_connection_type: DependencyConnectionTypes.END_TO_START,
      },
      loading: false,
      fields: [],
      localValue: true,
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
        dependency_linkrow_role: {
          requiredIfIsActive: requiredIf(() => {
            return (
              this.dependency.is_active &&
              this.dependency.dependency_linkrow_field_id
            )
          }),
        },
        dependency_buffer_type: {
          requiredIfIsActive: requiredIf(() => {
            return (
              this.dependency.is_active &&
              this.dependency.dependency_linkrow_field_id
            )
          }),
        },

        dependency_buffer: {
          requiredIfIsActive: requiredIf(() => {
            return (
              this.dependency.is_active &&
              this.dependency.dependency_linkrow_field_id
            )
          }),
        },
        dependency_connection_type: {
          requiredIfIsActive: requiredIf(() => {
            return (
              this.dependency.is_active &&
              this.dependency.dependency_linkrow_field_id
            )
          }),
        },
      },
    }
  },
  computed: {
    startDateFields() {
      const endDateFieldId = this.dependency.end_date_field_id
      return this.getFieldsForType(this.fields, 'date', (f) => {
        return f.id !== endDateFieldId
      })
    },
    endDateFields() {
      const startDateFieldId = this.dependency.start_date_field_id
      return this.getFieldsForType(this.fields, 'date', (f) => {
        return f.id !== startDateFieldId
      })
    },
    durationFields() {
      return this.getFieldsForType(this.fields, 'duration')
    },

    dependencyLinkRowRoles() {
      return DependencyLinkRowRoles.toLabels()
    },
    dependencyConnectionTypes() {
      return DependencyConnectionTypes.toFields()
    },
    dependencyBufferTypes() {
      return DependencyBufferType.toFields()
    },
    dependencyBufferValue() {
      return this.getDependencyBufferFormattedValue(
        this.dependency.dependency_buffer
      )
    },
    linkrowFieldRoleIdx() {
      const label = this.dependency?.dependency_linkrow_role
      return DependencyLinkRowRoles.getIndex(label)
    },

    dependencyFields() {
      const tableId = this.table.id
      return this.getFieldsForType(this.fields, 'link_row', [
        (x) => {
          return x.link_row_table_id === tableId
        },
      ])
    },
  },
  methods: {
    async getFields(tableId) {
      const { data } = await FieldService(this.$client).fetchAll(this.table.id)
      return data
    },
    linkRowFieldRoleChanged(newIndex) {
      const val = DependencyLinkRowRoles.toLabels()[newIndex].label
      this.onDependencyFieldChange('dependency_linkrow_role', val)
    },
    getDurationField() {
      const durationFieldId = this.dependency.duration_field_id
      const out = this.getFieldsForType(this.fields, 'duration', (x) => {
        return x.id === durationFieldId
      })
      if (out.length === 1) {
        return out[0]
      }
    },
    getFieldsForType(
      fields,
      expectedType,
      extraFilters = null,
      addEmpty = true
    ) {
      const out = Array.from(fields).filter((f) => {
        if (f.type === expectedType && !f.read_only) {
          if (_.isFunction(extraFilters)) {
            if (!extraFilters(f)) {
              return false
            }
          }
          return true
        }
        return false
      })
      if (addEmpty && out.length > 0) {
        out.unshift({ id: null, name: '' })
      }

      return out
    },

    async init() {
      this.localValue = false
      try {
        this.fields = await this.getFields(this.table.id)
        if (
          !this.$store.getters['fieldRules/hasRules']({
            tableId: this.table.id,
          })
        ) {
          await this.$store.dispatch('fieldRules/fetchInitial', {
            tableId: this.table.id,
          })
        }
        const deps = this.$store.getters['fieldRules/getRulesByType']({
          tableId: this.table.id,
          ruleType: 'date_dependency',
        })
        if (deps.length > 0) {
          Object.assign(this.dependency, deps[0])
          this.localValue = false
        }
      } catch (err) {
        await this.$store.dispatch('toast/error', err)
      }
      this.$store.dispatch('fieldRules/setCurrent', {
        tableId: this.dependency.table_id,
        ruleId: this.dependency.id,
      })
    },
    toggleDateDependency() {
      this.onDependencyFieldChange('is_active', !this.dependency.is_active)
    },
    onDependencyFieldChange(fieldName, value) {
      this.dependency[fieldName] = value

      if (this.dependency.id === null) {
        // this.dependency[fieldName] = value
        return
      }

      const dep = Object.assign({}, this.dependency)
      dep[fieldName] = value
      // this.$store.dispatch('fieldRules/ruleChanged', {
      //   tableId: this.table.id,
      //   ruleId: dep.id,
      //   rule: dep
      // })
    },
    getDependencyBufferFormattedValue(value) {
      const inValue = value
      const durationFormat = 'd h'
      const parsed = parseDurationValue(inValue, durationFormat)

      // We don't have `d` format yet, so need to manually round to full days.
      const fullDay = 24 * 3600
      const rounded = Math.round(parsed / fullDay) * fullDay
      return formatDurationValue(rounded, durationFormat)
    },
    onTimeBufferChange(evt) {
      // input evt, so there's .target
      const inValue = evt.target.value
      const outValue = this.getDependencyBufferFormattedValue(inValue)
      if (outValue !== inValue) {
        this.onDependencyFieldChange('dependency_buffer', outValue)
      }
    },

    async submit() {
      this.loading = true
      try {
        const valid = await this.v$.$validate()
        if (!valid) {
          this.loading = false

          return
        }
      } catch (err) {
        this.$store.dispatch('toast/error', err)
        return
      }
      try {
        const sendData = Object.assign({}, this.dependency)
        // change to seconds before sending
        sendData.dependency_buffer = parseDurationValue(
          sendData.dependency_buffer,
          'd h'
        )
        let updated = null
        if (this.dependency.id === null) {
          updated = await this.$store.dispatch('fieldRules/addRule', {
            tableId: this.table.id,
            rule: sendData,
          })
        } else {
          updated = await this.$store.dispatch('fieldRules/updateRule', {
            tableId: this.table.id,
            ruleId: this.dependency.id,
            rule: sendData,
          })
        }
        const stored = this.$store.getters['fieldRules/getRuleById']({
          tableId: this.table.id,
          ruleId: updated.id,
        })
        Object.assign(this.dependency, stored)
        if (this.$refs.modal !== undefined) {
          this.$refs.modal.hide()
        }
      } catch (err) {
        this.$store.dispatch('toast/error', err)
      } finally {
        this.loading = false
      }
    },
    cancel() {
      this.$refs.modal.hide()
    },
    onModalClose() {
      this.$store.dispatch('fieldRules/unsetCurrent')
    },
  },
}
</script>
