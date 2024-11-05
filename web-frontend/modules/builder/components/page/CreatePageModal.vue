<template>
  <Modal>
    <h2 class="box__title">
      {{ $t('createPageModal.header') }}
    </h2>
    <PageSettingsForm
      ref="pageForm"
      :builder="builder"
      is-creation
      @submitted="addPage"
    >
      <div class="actions actions--right">
        <Button size="large" :loading="loading">
          {{ $t('createPageModal.submit') }}
        </Button>
      </div>
    </PageSettingsForm>
  </Modal>
</template>

<script>
import modal from '@baserow/modules/core/mixins/modal'
import { notifyIf } from '@baserow/modules/core/utils/error'
import PageSettingsForm from '@baserow/modules/builder/components/page/settings/PageSettingsForm'

export default {
  name: 'CreatePageModal',
  components: { PageSettingsForm },
  mixins: [modal],
  provide() {
    return {
      currentPage: null,
      builder: this.builder,
      workspace: this.workspace,
    }
  },
  props: {
    workspace: {
      type: Object,
      required: true,
    },
    builder: {
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
    async addPage({
      name,
      path,
      path_params: pathParams,
      query_params: queryParams,
    }) {
      this.loading = true
      try {
        const page = await this.$store.dispatch('page/create', {
          builder: this.builder,
          name,
          path,
          pathParams,
          queryParams,
        })
        this.$refs.pageForm.v$.$reset()
        this.hide()
        this.$router.push(
          {
            name: 'builder-page',
            params: { builderId: this.builder.id, pageId: page.id },
          },
          null,
          () => {}
        )
      } catch (error) {
        notifyIf(error, 'application')
      }
      this.loading = false
    },
  },
}
</script>
