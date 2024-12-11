<template>
  <Context ref="context" overflow-scroll max-height-if-outside-viewport>
    <ul class="context__menu">
      <li
        v-for="authProviderType in authProviderTypes"
        :key="authProviderType.type"
        class="context__menu-item"
      >
        <a
          class="context__menu-item-link"
          @click="$emit('create', authProviderType)"
        >
          <AuthProviderIcon :icon="authProviderType.getIcon()" />
          {{ authProviderType.getName() }}
        </a>
      </li>
    </ul>
  </Context>
</template>

<script>
import context from '@baserow/modules/core/mixins/context'
import AuthProviderIcon from '@baserow_enterprise/components/AuthProviderIcon.vue'

export default {
  name: 'CreateAuthProviderContext',
  components: { AuthProviderIcon },
  mixins: [context],
  props: {
    authProviderTypes: {
      type: Array,
      required: true,
    },
  },
}
</script>
