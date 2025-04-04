<template>
  <form @submit.prevent="submit">
    <div class="row margin-bottom-2">
      <div class="col col-12">
        <FormGroup
          required
          small-label
          :label="$t('automationWorkflowForm.nameTitle')"
          :error-message="getFirstErrorMessage('name')"
          :helper-text="$t('automationWorkflowForm.nameSubtitle')"
        >
          <FormInput
            ref="name"
            v-model="v$.values.name.$model"
            size="large"
            :placeholder="$t('automationWorkflowForm.namePlaceholder')"
            :disabled="!hasPermission"
            @blur="v$.values.name.$touch"
            @focus.once="isCreation && $event.target.select()"
          />
        </FormGroup>
      </div>
    </div>
    <slot></slot>
  </form>
</template>

<script>
import { useVuelidate } from '@vuelidate/core'
import { maxLength, required, helpers } from '@vuelidate/validators'
import form from '@baserow/modules/core/mixins/form'
import { getNextAvailableNameInSequence } from '@baserow/modules/core/utils/string'

export default {
  name: 'AutomationWorkflowSettingsForm',
  mixins: [form],
  inject: ['workspace', 'automation'],
  props: {
    workflow: {
      type: Object,
      required: false,
      default: null,
    },
    isCreation: {
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
      values: {
        name: '',
      },
    }
  },
  computed: {
    hasPermission() {
      if (this.isCreation) {
        return this.$hasPermission(
          'automation.create_workflow',
          this.automation,
          this.workspace.id
        )
      } else {
        return this.$hasPermission(
          'automation.workflow.update',
          this.workflow,
          this.workspace.id
        )
      }
    },
    defaultName() {
      const baseName = this.$t('automationWorkflowForm.defaultName')
      return getNextAvailableNameInSequence(baseName, this.workflowNames)
    },
    workflows() {
      return this.$store.getters['automationWorkflow/getWorkflows'](
        this.automation
      )
    },
    workflowNames() {
      return this.workflows.map((workflow) => workflow.name)
    },
  },
  created() {
    if (this.isCreation) {
      this.values.name = this.defaultName
    }
  },
  mounted() {
    if (this.isCreation) {
      this.$refs.name.$refs.input.focus()
    }
  },
  methods: {
    getFormValues() {
      return Object.assign({}, this.values, this.getChildFormsValues(), {})
    },
    isNameUnique(name) {
      return !this.workflowNames.includes(name) || name === this.workflow?.name
    },
  },
  validations() {
    return {
      values: {
        name: {
          required: helpers.withMessage(
            this.$t('error.requiredField'),
            required
          ),
          isUnique: helpers.withMessage(
            this.$t('automationWorkflowErrors.errorNameNotUnique'),
            this.isNameUnique
          ),
          maxLength: helpers.withMessage(
            this.$t('error.maxLength', { max: 255 }),
            maxLength(225)
          ),
        },
      },
    }
  },
}
</script>
