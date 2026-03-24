<template>
  <Modal ref="modal" small @hidden="$emit('hidden')">
    <h2 class="box__title">
      {{ $t('aiProviderAdmin.deleteTitle', { name: provider.name }) }}
    </h2>
    <p>{{ $t('aiProviderAdmin.deleteWarning') }}</p>
    <p v-if="usageCount > 0" class="color-error margin-top-1">
      {{ $t('aiProviderAdmin.deleteUsageWarning', { count: usageCount }) }}
    </p>
    <div>
      <div class="actions">
        <ul class="action__links">
          <li>
            <a @click="hide()">{{ $t('action.cancel') }}</a>
          </li>
        </ul>
        <Button
          type="danger"
          :disabled="loading"
          :loading="loading"
          @click="onConfirm"
        >
          {{ $t('action.delete') }}
        </Button>
      </div>
    </div>
  </Modal>
</template>

<script>
import modal from '@baserow/modules/core/mixins/modal'
import { notifyIf } from '@baserow/modules/core/utils/error'

export default {
  name: 'AIProviderDeleteModal',
  mixins: [modal],
  props: {
    provider: {
      type: Object,
      required: true,
    },
  },
  data() {
    return {
      loading: false,
    }
  },
  computed: {
    usageCount() {
      // Count total models across the provider as a proxy for "in use"
      return this.provider.models?.length || 0
    },
  },
  methods: {
    async onConfirm() {
      this.loading = true
      try {
        await this.$store.dispatch('aiProvider/delete', {
          id: this.provider.id,
        })
        this.$emit('deleted')
        this.hide()
      } catch (error) {
        notifyIf(error, 'aiProvider')
      } finally {
        this.loading = false
      }
    },
  },
}
</script>
