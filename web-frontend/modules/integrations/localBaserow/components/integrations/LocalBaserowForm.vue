<template>
  <div>
    <FormGroup :label="$t('localBaserowForm.subject')" required small-label>
      <Dropdown v-model="authenticationSubject" :disabled="loadingAgents">
        <DropdownItem
          :name="$t('localBaserowForm.currentUser')"
          value="user"
          icon="iconoir-user"
        />
        <DropdownItem
          v-for="agent in agents"
          :key="agent.id"
          :name="agent.name"
          :value="agent.id"
          icon="baserow-icon-agent"
        />
      </Dropdown>
      <template #helper>
        {{ $t('localBaserowForm.subjectMessage') }}
      </template>
    </FormGroup>
  </div>
</template>

<script>
import form from '@baserow/modules/core/mixins/form'
import AgentService from '@baserow/modules/core/services/agent'
import { notifyIf } from '@baserow/modules/core/utils/error'

export default {
  mixins: [form],
  props: {
    application: {
      type: Object,
      required: true,
    },
  },
  data() {
    return {
      values: {
        authorized_agent_id: this.defaultValues.authorized_agent?.id || null,
      },
      allowedValues: ['authorized_agent_id'],
      agents: [],
      loadingAgents: false,
    }
  },
  computed: {
    authenticationSubject: {
      get() {
        return this.values.authorized_agent_id || 'user'
      },
      set(value) {
        this.values.authorized_agent_id = value === 'user' ? null : value
      },
    },
  },
  async mounted() {
    this.loadingAgents = true
    try {
      const { data } = await AgentService(this.$client).list(
        this.application.workspace.id
      )
      this.agents = data.results
    } catch (error) {
      notifyIf(error, 'agent')
    } finally {
      this.loadingAgents = false
    }
  },
}
</script>
