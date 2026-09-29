<template>
  <div
    v-if="actions.length || (showDisabledTrigger && disabled)"
    class="ai-provider-actions-menu"
  >
    <ButtonIcon
      ref="trigger"
      type="secondary"
      size="small"
      icon="iconoir-more-vert"
      :disabled="disabled"
      :title="title"
      :aria-label="title"
      @click="open"
    />
    <Context
      v-if="actions.length"
      ref="context"
      overflow-scroll
      max-height-if-outside-viewport
    >
      <ul class="context__menu">
        <li
          v-for="action in actions"
          :key="action.key"
          class="context__menu-item"
        >
          <a
            href="#"
            class="context__menu-item-link"
            :class="{
              'context__menu-item-link--delete': action.danger,
              'context__menu-item-link--loading': action.loading,
            }"
            :data-action="action.key"
            @click.prevent="select(action.key)"
          >
            <i class="context__menu-item-icon" :class="action.icon" />
            {{ action.label }}
          </a>
        </li>
      </ul>
    </Context>
  </div>
</template>

<script>
export default {
  name: 'AIProviderActionsMenu',
  props: {
    actions: { type: Array, required: true },
    disabled: { type: Boolean, default: false },
    showDisabledTrigger: { type: Boolean, default: false },
    title: { type: String, required: true },
  },
  emits: ['select'],
  computed: {
    loadingAction() {
      return this.actions.find((action) => action.loading)?.key || null
    },
  },
  watch: {
    disabled(value) {
      if (value) this.$refs.context?.hide()
    },
    loadingAction(value, previous) {
      // The menu stays open while an action is in flight and closes once it
      // has settled, whether it succeeded or the parent reported an error.
      if (previous !== null && value === null) this.$refs.context?.hide()
    },
  },
  methods: {
    open() {
      if (this.disabled || !this.$refs.context) return
      return this.$refs.context.toggle(
        this.$refs.trigger.$el,
        'bottom',
        'right',
        4
      )
    },
    select(action) {
      if (this.disabled || this.loadingAction !== null) return
      this.$emit('select', action)
      // A parent that starts a request marks the action as loading in the
      // same tick, in which case the menu must remain visible.
      this.$nextTick(() => {
        if (this.loadingAction !== action) this.$refs.context?.hide()
      })
    },
  },
}
</script>
