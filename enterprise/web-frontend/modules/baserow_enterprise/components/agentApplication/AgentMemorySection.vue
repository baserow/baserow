<template>
  <div>
    <FormTextarea
      v-model="value"
      :rows="12"
      :disabled="!canUpdate"
      :placeholder="$t('agentMemory.placeholder')"
      @input="onInput"
    ></FormTextarea>
    <div class="agent-configuration__hint">
      {{ $t('agentMemory.hint') }}
    </div>
    <div class="agent-configuration__actions">
      <Button
        v-if="canUpdate"
        type="secondary"
        icon="iconoir-bin"
        :disabled="value === ''"
        @click="setValue('')"
      >
        {{ $t('agentMemory.clear') }}
      </Button>
      <span class="agent-configuration__counter">
        {{ $t('agentMemory.characters', { count: value.length }) }}
      </span>
    </div>
  </div>
</template>

<script>
import { defineComponent, toRef } from 'vue'
import { useSeededAgentField } from '@baserow_enterprise/composables/useSeededAgentField'

export default defineComponent({
  name: 'AgentMemorySection',
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
    const { value, onInput, setValue } = useSeededAgentField('memory', {
      canUpdate: toRef(props, 'canUpdate'),
    })
    return { value, onInput, setValue }
  },
})
</script>
