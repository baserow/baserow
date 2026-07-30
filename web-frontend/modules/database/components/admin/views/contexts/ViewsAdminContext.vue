<template>
  <Context ref="context" overflow-scroll max-height-if-outside-viewport>
    <template v-if="Object.keys(view).length > 0">
      <div class="context__menu-title">{{ view.name }} ({{ view.id }})</div>
      <ul class="context__menu">
        <li v-if="view.public && publicUrl" class="context__menu-item">
          <a class="context__menu-item-link" @click.prevent="copyPublicUrl">
            <i class="context__menu-item-icon iconoir-copy"></i>
            {{ $t('viewsAdminContext.copyPublicUrl') }}
          </a>
        </li>
        <li v-if="view.public && publicUrl" class="context__menu-item">
          <a class="context__menu-item-link" @click.prevent="openPublicUrl">
            <i class="context__menu-item-icon iconoir-open-new-window"></i>
            {{ $t('viewsAdminContext.openPublicView') }}
          </a>
        </li>
        <li class="context__menu-item">
          <a class="context__menu-item-link" @click.prevent="searchWorkspaceId">
            <i class="context__menu-item-icon iconoir-search"></i>
            {{ $t('viewsAdminContext.searchWorkspaceId') }}
          </a>
        </li>
        <li class="context__menu-item">
          <a
            class="context__menu-item-link"
            @click.prevent="showRotateSlugModal"
          >
            <i class="context__menu-item-icon iconoir-refresh-double"></i>
            {{ $t('viewsAdminContext.rotateSlug') }}
          </a>
        </li>
        <li class="context__menu-item context__menu-item--with-separator">
          <a
            v-if="view.public"
            class="context__menu-item-link context__menu-item-link--delete"
            :class="{ 'context__menu-item-link--loading': updatePublicLoading }"
            @click.prevent="updatePublic(false)"
          >
            <i class="context__menu-item-icon iconoir-lock"></i>
            {{ $t('viewsAdminContext.makePrivate') }}
          </a>
          <a
            v-else
            class="context__menu-item-link"
            :class="{ 'context__menu-item-link--loading': updatePublicLoading }"
            @click.prevent="updatePublic(true)"
          >
            <i class="context__menu-item-icon iconoir-globe"></i>
            {{ $t('viewsAdminContext.makePublic') }}
          </a>
        </li>
      </ul>
      <ViewsAdminRotateSlugModal
        ref="rotateSlugModal"
        :view="view"
        @update="$emit('update', $event)"
      ></ViewsAdminRotateSlugModal>
    </template>
  </Context>
</template>

<script>
import context from '@baserow/modules/core/mixins/context'
import { notifyIf } from '@baserow/modules/core/utils/error'
import { copyToClipboard } from '@baserow/modules/database/utils/clipboard'
import ViewsAdminService from '@baserow/modules/database/services/admin/views'
import ViewsAdminRotateSlugModal from '@baserow/modules/database/components/admin/views/modals/ViewsAdminRotateSlugModal'

export default {
  name: 'ViewsAdminContext',
  components: {
    ViewsAdminRotateSlugModal,
  },
  mixins: [context],
  props: {
    view: {
      required: true,
      type: Object,
    },
  },
  emits: ['update', 'search-workspace-id'],
  data() {
    return {
      updatePublicLoading: false,
    }
  },
  computed: {
    viewType() {
      return this.$registry.get('view', this.view.type)
    },
    publicUrl() {
      if (!this.viewType.canShare) {
        return null
      }
      return (
        this.$config.public.baserowEmbeddedShareUrl +
        this.$router.resolve({
          name: this.viewType.getPublicRoute(),
          params: { slug: this.view.slug },
        }).href
      )
    },
  },
  methods: {
    copyPublicUrl() {
      copyToClipboard(this.publicUrl)
      this.$store.dispatch('toast/info', {
        title: this.$t('viewsAdminContext.publicUrlCopiedTitle'),
        message: this.$t('viewsAdminContext.publicUrlCopiedMessage'),
      })
      this.hide()
    },
    openPublicUrl() {
      window.open(this.publicUrl, '_blank')
      this.hide()
    },
    searchWorkspaceId() {
      this.$emit('search-workspace-id', this.view.workspace_id)
      this.hide()
    },
    async updatePublic(publicValue) {
      this.updatePublicLoading = true
      try {
        const { data } = await ViewsAdminService(this.$client).update(
          this.view.id,
          { public: publicValue }
        )
        this.hide()
        this.$emit('update', data)
      } catch (error) {
        notifyIf(error, 'view')
      }
      this.updatePublicLoading = false
    },
    showRotateSlugModal() {
      this.$refs.rotateSlugModal.show()
      this.hide()
    },
  },
}
</script>
