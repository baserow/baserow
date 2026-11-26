<template>
  <article class="agent-channel-card" :aria-busy="saving">
    <header class="agent-channel-card__header">
      <button
        type="button"
        class="agent-channel-card__toggle"
        :aria-expanded="expanded"
        :aria-label="$t('agentChannels.settings', { name: shownName })"
        @click="$emit('toggle')"
      >
        <Icon
          :icon="
            expanded ? 'iconoir-nav-arrow-down' : 'iconoir-nav-arrow-right'
          "
          aria-hidden="true"
        />
        <Icon
          :icon="channelType.icon"
          class="agent-channel-card__icon"
          aria-hidden="true"
        />
        <span class="agent-channel-card__name">{{ shownName }}</span>
        <span
          v-if="shownName !== channelType.name"
          class="agent-channel-card__type"
          >{{ channelType.name }}</span
        >
      </button>
      <span class="agent-channel-card__saving-slot">
        <span
          v-if="saving"
          class="agent-channel-card__saving"
          role="status"
          :aria-label="$t('agent.saving')"
        />
      </span>
      <SwitchInput
        class="agent-channel-card__switch"
        small
        role="switch"
        :tabindex="canSwitch ? 0 : -1"
        :aria-label="$t('agentChannels.channelEnabled')"
        :aria-checked="channel.enabled"
        :aria-disabled="!canSwitch"
        :model-value="channel.enabled"
        :disabled="!canSwitch"
        @update:model-value="$emit('update', { enabled: $event })"
        @keydown.enter.prevent="toggleEnabled"
        @keydown.space.prevent="toggleEnabled"
      />
    </header>
    <div v-show="expanded" class="agent-channel-card__body">
      <component
        :is="channelType.formComponent"
        :channel="channel"
        :agent-name="agentName"
        :can-edit="canEdit"
        v-bind="formProps"
        @update="$emit('update', $event)"
      />
    </div>
    <footer
      v-if="editable"
      v-show="expanded"
      class="agent-channel-card__footer"
    >
      <ButtonText
        type="secondary"
        size="small"
        button-type="button"
        icon="iconoir-bin"
        class="agent-channel-card__delete"
        @click="$emit('delete')"
      >
        {{ $t('agentChannels.deleteChannel') }}
      </ButtonText>
    </footer>
  </article>
</template>

<script setup>
import { computed } from 'vue'
import Icon from '@baserow/modules/core/components/Icon'
import ButtonText from '@baserow/modules/core/components/ButtonText'

const props = defineProps({
  /** The channel as the card shows it, edits included. */
  channel: { type: Object, required: true },
  /** The registered type of the channel. */
  channelType: { type: Object, required: true },
  /** The props the type's form takes beyond the common ones. */
  formProps: { type: Object, default: () => ({}) },
  /** The Agent's name, which a channel may show without its own title. */
  agentName: { type: String, default: '' },
  /** Whether the user may change the channel. */
  editable: Boolean,
  /** Without the licence, only switching the channel off and deleting it remain. */
  licensed: Boolean,
  /** Whether the card shows its settings below its header. */
  expanded: Boolean,
  /** Whether a save of the channel is in flight. */
  saving: Boolean,
})
const emit = defineEmits(['toggle', 'update', 'delete'])

const canEdit = computed(() => props.editable && props.licensed)
const canSwitch = computed(
  () => canEdit.value || (props.editable && props.channel.enabled)
)
const shownName = computed(() =>
  props.channelType.getChannelName(props.channel)
)

function toggleEnabled() {
  if (canSwitch.value) emit('update', { enabled: !props.channel.enabled })
}
</script>
