<template>
  <component
    :is="formComponent"
    v-if="formComponent"
    :application="application"
    :service="service"
    :service-type="serviceType"
    :default-values="service"
    :databases="workspaceDatabases"
    @values-changed="$emit('values-changed', $event)"
  />
  <div v-else class="agent-configuration__placeholder">
    {{ $t('agentServiceForm.noConfiguration') }}
  </div>
</template>

<script>
import { computed, reactive, toRef } from 'vue'
import AutomationBuilderFormulaInput from '@baserow/modules/automation/components/AutomationBuilderFormulaInput'
import { DatabaseApplicationType } from '@baserow/modules/database/applicationTypes'

/**
 * Renders the configuration form of a service used by the agent as a trigger
 * or as an action tool. Like a button field, Local Baserow services need no
 * integration here: they run as the agent's identity, or the identity chosen
 * under "Runs as", so the form offers every database of the workspace to pick
 * a table from. For action tools the tool's declared runtime inputs are
 * exposed in the formula data explorer via the `tool_input` data provider;
 * triggers have no preceding data to reference.
 */
export default {
  name: 'AgentServiceForm',
  props: {
    application: {
      type: Object,
      required: true,
    },
    serviceType: {
      type: Object,
      required: true,
    },
    service: {
      type: Object,
      required: false,
      default: () => ({}),
    },
    tool: {
      type: Object,
      required: false,
      default: null,
    },
  },
  emits: ['values-changed'],
  provide() {
    return {
      formulaComponent: AutomationBuilderFormulaInput,
      dataProvidersAllowed: this.tool ? ['tool_input'] : [],
      applicationContext: reactive({ tool: toRef(this, 'tool') }),
      workspace: computed(() => this.application.workspace),
    }
  },
  computed: {
    formComponent() {
      return this.serviceType.formComponent
    },
    workspaceDatabases() {
      return this.$store.getters['application/getAllOfWorkspace'](
        this.application.workspace
      ).filter(
        (application) => application.type === DatabaseApplicationType.getType()
      )
    },
  },
}
</script>
