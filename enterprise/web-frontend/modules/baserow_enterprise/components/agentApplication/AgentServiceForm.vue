<template>
  <component
    :is="formComponent"
    v-if="formComponent"
    :application="application"
    :service="service"
    :service-type="serviceType"
    :default-values="service"
    @values-changed="$emit('values-changed', $event)"
  />
  <div v-else class="agent-configuration__placeholder">
    {{ $t('agentServiceForm.noConfiguration') }}
  </div>
</template>

<script>
import { computed, reactive } from 'vue'
import LocalBaserowNodeServiceForm from '@baserow/modules/automation/components/workflow/LocalBaserowNodeServiceForm'
import AutomationBuilderFormulaInput from '@baserow/modules/automation/components/AutomationBuilderFormulaInput'
import { LocalBaserowIntegrationType } from '@baserow/modules/integrations/localBaserow/integrationTypes'

/**
 * Renders the configuration form of a service used by the agent as a trigger
 * or as an action tool. Local Baserow services are wrapped in the automation
 * integration picker so a table can be chosen, other services render their own
 * form component directly. For action tools the tool's declared runtime
 * inputs are exposed in the formula data explorer via the `tool_input` data
 * provider; triggers have no preceding data to reference.
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
    const self = this
    return {
      formulaComponent: AutomationBuilderFormulaInput,
      dataProvidersAllowed: this.tool ? ['tool_input'] : [],
      applicationContext: reactive({
        get tool() {
          return self.tool
        },
      }),
      workspace: computed(() => this.application.workspace),
    }
  },
  computed: {
    formComponent() {
      if (
        this.serviceType.integrationType?.getType() ===
        LocalBaserowIntegrationType.getType()
      ) {
        return LocalBaserowNodeServiceForm
      }
      return this.serviceType.formComponent
    },
  },
}
</script>
