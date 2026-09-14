<template>
  <div class="agent-configuration__card">
    <div class="agent-configuration__card-header">
      <a class="agent-configuration__card-toggle" @click.prevent="toggle">
        <i
          class="agent-configuration__card-chevron iconoir-nav-arrow-right"
          :class="{ 'agent-configuration__card-chevron--expanded': expanded }"
        ></i>
        <img
          v-if="image"
          class="agent-configuration__card-image"
          :src="image"
        />
        <i
          v-else-if="icon"
          class="agent-configuration__card-icon"
          :class="icon"
        ></i>
        <div class="agent-configuration__card-name">{{ title }}</div>
        <div v-if="subtitle" class="agent-configuration__card-subtitle">
          {{ subtitle }}
        </div>
      </a>
      <slot name="header-right"></slot>
    </div>
    <div v-show="expanded" class="agent-configuration__card-body">
      <slot></slot>
      <div v-if="$slots.footer" class="agent-configuration__card-footer">
        <slot name="footer"></slot>
      </div>
    </div>
  </div>
</template>

<script>
/**
 * A collapsible card in the configuration panel (a trigger, an action tool,
 * a chat channel). The body stays mounted while folded so unsaved drafts and
 * debounced saves inside it are not lost.
 */
export default {
  name: 'AgentConfigurationCard',
  props: {
    title: {
      type: String,
      required: true,
    },
    subtitle: {
      type: String,
      required: false,
      default: '',
    },
    icon: {
      type: String,
      required: false,
      default: '',
    },
    image: {
      type: String,
      required: false,
      default: '',
    },
  },
  data() {
    return { expanded: true }
  },
  methods: {
    toggle() {
      this.expanded = !this.expanded
    },
  },
}
</script>
