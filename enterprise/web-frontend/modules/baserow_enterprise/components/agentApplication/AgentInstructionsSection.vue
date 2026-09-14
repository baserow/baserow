<template>
  <div>
    <FormTextarea
      v-model="value"
      :rows="14"
      :disabled="!canUpdate"
      :placeholder="$t('agentInstructions.placeholder')"
      @input="onInput"
    ></FormTextarea>
    <div class="agent-configuration__hint">
      {{ $t('agentInstructions.hint') }}
    </div>
    <div class="agent-configuration__actions">
      <Button
        v-if="canUpdate"
        type="secondary"
        icon="iconoir-sparks"
        :loading="improving"
        @click="improve"
      >
        {{ $t('agentInstructions.improve') }}
      </Button>
      <span class="agent-configuration__counter">
        {{ $t('agentInstructions.characters', { count: value.length }) }}
      </span>
    </div>
  </div>
</template>

<script>
import { defineComponent, ref, toRef } from 'vue'
import { useStore } from 'vuex'
import { notifyIf } from '@baserow/modules/core/utils/error'
import { useSeededAgentField } from '@baserow_enterprise/composables/useSeededAgentField'

export default defineComponent({
  name: 'AgentInstructionsSection',
  props: {
    application: {
      type: Object,
      required: true,
    },
    canUpdate: {
      type: Boolean,
      required: true,
    },
  },
  setup(props) {
    const store = useStore()
    const { agent, value, onInput, setValue, flush } = useSeededAgentField(
      'instructions',
      { canUpdate: toRef(props, 'canUpdate') }
    )

    const improving = ref(false)
    const improve = async () => {
      if (improving.value || !agent.value) {
        return
      }
      improving.value = true
      try {
        // Persist what the user typed before asking for the improved version.
        flush()
        const instructions = await store.dispatch(
          'agentApplication/improveInstructions',
          { agentId: agent.value.id, instructions: value.value }
        )
        setValue(instructions)
      } catch (error) {
        notifyIf(error, 'application')
      } finally {
        improving.value = false
      }
    }

    return { value, onInput, improving, improve }
  },
})
</script>
