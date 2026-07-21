<template>
  <div v-if="actions.length" class="ai-provider-actions-menu">
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
    <Context ref="context" overflow-scroll max-height-if-outside-viewport>
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
    title: { type: String, required: true },
  },
  emits: ['select'],
  watch: {
    disabled(value) {
      if (value) this.$refs.context?.hide()
    },
  },
  methods: {
    open() {
      return this.$refs.context.toggle(
        this.$refs.trigger.$el,
        'bottom',
        'right',
        4
      )
    },
    select(action) {
      if (this.disabled) return
      this.$refs.context.hide()
      this.$emit('select', action)
    },
  },
}
</script>
