<template>
  <Modal ref="modal">
    <h2 class="box__title">{{ $t('viewsAdminRotateSlugModal.title') }}</h2>
    <Error :error="error"></Error>
    <div>
      <p>
        {{
          $t('viewsAdminRotateSlugModal.refreshWarning', {
            viewName: view.name,
          })
        }}
      </p>
      <div class="actions">
        <div class="align-right">
          <Button
            type="primary"
            size="large"
            :loading="loading"
            :disabled="loading"
            @click="rotateSlug()"
          >
            {{ $t('viewsAdminRotateSlugModal.generateNewURL') }}
          </Button>
        </div>
      </div>
    </div>
  </Modal>
</template>

<script>
import modal from '@baserow/modules/core/mixins/modal'
import error from '@baserow/modules/core/mixins/error'
import ViewsAdminService from '@baserow/modules/database/services/admin/views'

export default {
  name: 'ViewsAdminRotateSlugModal',
  mixins: [modal, error],
  props: {
    view: {
      type: Object,
      required: true,
    },
  },
  emits: ['update'],
  data() {
    return {
      loading: false,
    }
  },
  methods: {
    async rotateSlug() {
      this.hideError()
      this.loading = true

      try {
        const { data } = await ViewsAdminService(this.$client).rotateSlug(
          this.view.id
        )
        this.$emit('update', data)
        this.hide()
      } catch (error) {
        this.handleError(error, 'view')
      }

      this.loading = false
    },
  },
}
</script>
