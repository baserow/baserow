<template>
  <form @submit.prevent>
    <FormGroup
      class="margin-bottom-2"
      :label="$t('coreRunAgentServiceForm.agent')"
      :helper-text="$t('coreRunAgentServiceForm.agentHelperText')"
      required
      small-label
    >
      <Dropdown v-model="values.agent_application_id" show-search>
        <DropdownItem
          v-for="agent in agents"
          :key="agent.id"
          :name="agent.name"
          :value="agent.id"
          icon="baserow-icon-agent"
        />
        <template v-if="agents.length === 0" #emptyState>
          <div class="select__items--no-max-width">
            {{ $t('coreRunAgentServiceForm.noAgents') }}
          </div>
        </template>
      </Dropdown>
    </FormGroup>
    <FormGroup
      class="margin-bottom-2"
      :label="$t('coreRunAgentServiceForm.prompt')"
      :helper-text="$t('coreRunAgentServiceForm.promptHelperText')"
      required
      small-label
    >
      <InjectedFormulaInput
        v-model="values.prompt"
        :placeholder="$t('coreRunAgentServiceForm.promptPlaceholder')"
      />
    </FormGroup>
    <FormGroup
      v-if="!insideBuilder"
      class="margin-bottom-2"
      :helper-text="$t('coreRunAgentServiceForm.waitHelperText')"
      small-label
    >
      <Checkbox v-model="values.wait_for_result">
        {{ $t('coreRunAgentServiceForm.wait') }}
      </Checkbox>
    </FormGroup>
  </form>
</template>

<script>
import form from '@baserow/modules/core/mixins/form'
import InjectedFormulaInput from '@baserow/modules/core/components/formula/InjectedFormulaInput'

export default {
  name: 'CoreRunAgentServiceForm',
  components: { InjectedFormulaInput },
  mixins: [form],
  // The builder's page editor provides its application; a published app
  // never waits on a model, so the switch is pointless there and the backend
  // ignores it anyway.
  inject: {
    applicationContext: { default: null },
  },
  data() {
    return {
      allowedValues: ['agent_application_id', 'prompt', 'wait_for_result'],
      values: {
        agent_application_id: null,
        prompt: '',
        wait_for_result: false,
      },
    }
  },
  computed: {
    insideBuilder() {
      return Boolean(this.applicationContext?.builder)
    },
    agents() {
      const workspace = this.$store.getters['workspace/getSelected']
      if (!workspace?.id) {
        return []
      }
      return this.$store.getters['application/getAllOfWorkspace'](workspace)
        .filter((application) => application.type === 'agent')
        .sort((a, b) => a.order - b.order)
    },
  },
}
</script>
