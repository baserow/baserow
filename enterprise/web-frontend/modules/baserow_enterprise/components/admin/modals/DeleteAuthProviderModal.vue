<template>
  <Modal ref="modal" small>
    <h2 class="box__title">
      {{ $t('deleteAuthProviderModal.title', { name: getProviderName() }) }}
    </h2>
    <p>
      {{
        $t('deleteAuthProviderModal.comment', { type: getProviderTypeName() })
      }}
    </p>
    <div>
      <div class="actions">
        <ul class="action__links">
          <li>
            <a @click="$emit('cancel')">{{ $t('action.cancel') }}</a>
          </li>
        </ul>

        <Button
          type="danger"
          :disabled="loading"
          :loading="loading"
          @click="deleteProvider"
        >
          {{ $t('action.delete') }}</Button
        >
      </div>
    </div>
  </Modal>
</template>

<script>
import modal from '@baserow/modules/core/mixins/modal'
import { notifyIf } from '@baserow/modules/core/utils/error'

export default {
  name: 'DeleteAuthProviderModal',
  emits: ['cancel', 'provider-deleted'],
  mixins: [modal],
  props: {
    authProvider: {
      type: Object,
      required: true,
    },
  },
  data() {
    return {
      loading: false,
    }
  },
  methods: {
    getProviderName() {
      return this.$registry
        .get('authProvider', this.authProvider.type)
        .getProviderName(this.authProvider)
    },
    getProviderTypeName() {
      return this.$registry
        .get('authProvider', this.authProvider.type)
        .getName(this.authProvider)
    },
    async deleteProvider() {
      this.loading = true
      try {
        await this.$store.dispatch(
          'authProviderAdmin/delete',
          this.authProvider
        )
        this.$emit('provider-deleted')
      } catch (error) {
        notifyIf(error, 'settings')
      } finally {
        this.loading = false
      }
    },
  },
}
</script>
