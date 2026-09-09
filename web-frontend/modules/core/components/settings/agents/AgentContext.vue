<template>
  <Context ref="context">
    <ul class="context__menu">
      <li class="context__menu-item">
        <a class="context__menu-item-link" @click.prevent="edit">
          <i class="context__menu-item-icon iconoir-edit-pencil"></i>
          {{ $t('agents.edit') }}
        </a>
      </li>
      <li class="context__menu-item context__menu-item--with-separator">
        <a
          class="context__menu-item-link context__menu-item-link--delete"
          @click.prevent="remove"
        >
          <i class="context__menu-item-icon iconoir-bin"></i>
          {{ $t('agents.delete') }}
        </a>
      </li>
    </ul>
  </Context>
</template>

<script>
import context from '@baserow/modules/core/mixins/context'

export default {
  name: 'AgentContext',
  mixins: [context],
  props: { agent: { type: Object, required: true } },
  emits: ['edit', 'deleted'],
  methods: {
    edit() {
      this.hide()
      this.$emit('edit')
    },
    async remove() {
      await this.$store.dispatch('agent/delete', this.agent)
      this.hide()
      this.$emit('deleted', this.agent.id)
    },
  },
}
</script>
