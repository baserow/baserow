<template>
  <!-- toolbar icon -->
  <div>
    <a
      ref="contextLink"
      class="header__filter-link"
      :class="{ 'active active--primary': view.isShared }"
      @click="$refs.context.toggle($refs.contextLink, 'bottom', 'left', 4)"
    >
      <i class="header__filter-icon iconoir-share-android"></i>
      <span class="header__filter-name">
        {{ $t('shareViewLink.shareView', { viewTypeSharingLinkName }) }}
      </span>
    </a>

    <!-- modal -->
    <Context ref="context" max-height-if-outside-viewport>
      <div class="view-sharing__content">
        <!-- is not yet shared -->
        <div
          v-if="!view.isShared"
          v-auto-overflow-scroll
          class="view-sharing__share-link view-sharing__share-link--scrollable"
        >
          <div class="view-sharing__share-link-title">
            {{
              $t('shareViewLink.shareViewTitle', { viewTypeSharingLinkName })
            }}
          </div>

          <!-- custom shared view text provided by viewType, should be i18n'ed already -->
          <p class="view-sharing__share-link-description">
            {{ view.createShareViewText || $t('shareViewLink.shareViewText') }}
          </p>

          <div class="view-sharing__share-link-options">
            <Button
              type="secondary"
              :disabled="readOnly"
              icon="baserow-icon-share"
              @click.stop="!readOnly && updateView({ public: true })"
            >
              {{
                $t('shareViewLink.createPrivateLink', {
                  viewTypeSharingLinkName,
                })
              }}
            </Button>

            <component
              :is="extraLink"
              v-for="(extraLink, i) in additionalCreateShareLinkOptions"
              :key="i"
              :view="view"
              @update-view="forceUpdateView"
            />
          </div>
        </div>

        <div v-else class="view-sharing">
          <div v-auto-overflow-scroll class="view-sharing--scrollable">
            <div v-if="view.public" class="view-sharing__shared-link">
              <!-- title and description -->
              <div class="view-sharing__shared-link-title">
                {{
                  $t('shareViewLink.sharedViewTitle', {
                    viewTypeSharingLinkName,
                  })
                }}
              </div>
              <div class="view-sharing__shared-link-description">
                {{
                  $t('shareViewLink.sharedViewDescription', {
                    viewTypeSharingLinkName,
                  })
                }}
              </div>

              <!-- generated url bar -->
              <div class="view-sharing__shared-link-content">
                <div class="view-sharing__shared-link-box">{{ shareUrl }}</div>
                <a
                  v-tooltip="$t('shareViewLink.copyURL')"
                  class="view-sharing__shared-link-action"
                  @click="copyShareUrlToClipboard()"
                >
                  <i class="iconoir-copy" />
                  <Copied ref="copied"></Copied>
                </a>
                <a
                  v-if="!readOnly"
                  v-tooltip="$t('shareViewLink.generateNewUrl')"
                  class="view-sharing__shared-link-action"
                  @click.prevent="$refs.rotateSlugModal.show()"
                >
                  <i class="iconoir-refresh-double" />
                  <ViewRotateSlugModal
                    ref="rotateSlugModal"
                    :service="viewService"
                    :view="view"
                  ></ViewRotateSlugModal>
                </a>
              </div>
              <div class="view-sharing__shared-link-options">
                <div class="view-sharing__option">
                  <SwitchInput
                    small
                    :value="view.public_view_has_password"
                    @input="toggleShareViewPassword"
                  >
                    <i
                      class="view-sharing__option-icon"
                      :class="[
                        view.public_view_has_password
                          ? 'iconoir-lock'
                          : 'iconoir-globe',
                      ]"
                    />
                    <span>{{ $t(optionPasswordText) }}</span>
                  </SwitchInput>

                  <a
                    v-if="view.public_view_has_password"
                    class="view-sharing__option-change-password"
                    @click.stop="$refs.enablePasswordModal.show"
                  >
                    {{ $t('shareViewLink.ChangePassword') }}
                    <i class="iconoir-edit-pencil" />
                  </a>
                  <EnablePasswordModal ref="enablePasswordModal" :view="view" />
                  <DisablePasswordModal
                    ref="disablePasswordModal"
                    :view="view"
                  />
                </div>

                <component
                  :is="component"
                  v-for="(component, i) in additionalShareLinkOptions"
                  :key="i"
                  :view="view"
                  @update-view="forceUpdateView"
                />
              </div>
            </div>

            <component
              :is="sharingSection"
              v-for="(sharingSection, i) in additionalSharingSections"
              :key="i"
              :view="view"
              @update-view="forceUpdateView"
            />
          </div>
          <div v-if="!readOnly" class="context__footer">
            <ButtonText
              v-if="view.public"
              icon="iconoir-cancel"
              @click.stop="updateView({ public: false })"
            >
              {{ $t('shareViewLink.disableLink') }}
            </ButtonText>
            <ButtonText
              v-else
              icon="baserow-icon-share"
              @click.stop="!readOnly && updateView({ public: true })"
            >
              {{
                $t('shareViewLink.createPrivateLink', {
                  viewTypeSharingLinkName,
                })
              }}
            </ButtonText>

            <component
              :is="comp"
              v-for="(comp, i) in additionalDisableSharedLinkOptions"
              :key="i"
              location="footer"
              :view="view"
              @update-view="forceUpdateView"
            />
          </div>
        </div>
      </div>
    </Context>
  </div>
</template>

<script>
import { copyToClipboard } from '@baserow/modules/database/utils/clipboard'
import ViewRotateSlugModal from '@baserow/modules/database/components/view/ViewRotateSlugModal'
import EnablePasswordModal from '@baserow/modules/database/components/view/public/EnablePasswordModal'
import DisablePasswordModal from '@baserow/modules/database/components/view/public/DisablePasswordModal'
import { notifyIf } from '@baserow/modules/core/utils/error'
import ViewService from '@baserow/modules/database/services/view'

export default {
  name: 'ShareViewLink',
  components: {
    ViewRotateSlugModal,
    EnablePasswordModal,
    DisablePasswordModal,
  },
  props: {
    view: {
      type: Object,
      required: true,
    },
    readOnly: {
      type: Boolean,
      required: true,
    },
  },
  data() {
    return {
      rotateSlugLoading: false,
      viewService: ViewService(this.$client),
    }
  },
  computed: {
    shareUrl() {
      return (
        this.$config.BASEROW_EMBEDDED_SHARE_URL +
        this.$router.resolve({
          name: this.viewType.getPublicRoute(),
          params: { slug: this.view.slug },
        }).href
      )
    },
    optionPasswordText() {
      return this.view.public_view_has_password
        ? 'shareViewLink.DisablePassword'
        : 'shareViewLink.EnablePassword'
    },
    viewType() {
      return this.$registry.get('view', this.view.type)
    },
    viewTypeSharingLinkName() {
      return this.viewType.getSharingLinkName()
    },
    additionalCreateShareLinkOptions() {
      return this.viewType.getAdditionalCreateShareLinkOptions()
    },
    additionalDisableSharedLinkOptions() {
      return this.viewType.getAdditionalDisableSharedLinkOptions()
    },
    additionalShareLinkOptions() {
      const opts = Object.values(this.$registry.getAll('plugin'))
        .reduce((components, plugin) => {
          components = components.concat(plugin.getAdditionalShareLinkOptions())
          return components
        }, [])
        .filter((component) => component !== null)
      return opts
    },
    additionalSharingSections() {
      return this.viewType.getAdditionalSharingSections()
    },
  },
  methods: {
    copyShareUrlToClipboard() {
      copyToClipboard(this.shareUrl)
      this.$refs.copied.show()
    },
    async updateView(values) {
      const view = this.view
      this.$store.dispatch('view/setItemLoading', { view, value: true })

      try {
        await this.$store.dispatch('view/update', {
          view,
          values,
        })
      } catch (error) {
        notifyIf(error, 'view')
      }

      this.$store.dispatch('view/setItemLoading', { view, value: false })
    },
    forceUpdateView(values) {
      this.$store.dispatch('view/forceUpdate', {
        view: this.view,
        values,
        repopulate: true,
      })
    },
    toggleShareViewPassword() {
      if (this.view.public_view_has_password) {
        this.$refs.disablePasswordModal.show()
      } else {
        this.$refs.enablePasswordModal.show()
      }
    },
  },
}
</script>
