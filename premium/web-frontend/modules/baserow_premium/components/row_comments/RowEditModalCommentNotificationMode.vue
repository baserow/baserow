<template>
  <div>
    <a
      class="row-edit-modal-comments-notification-mode"
      @click.prevent="
        $refs.context.toggle($event.currentTarget, 'bottom', 'right', 2)
      "
    >
      <i class="iconoir-bell"></i>
    </a>
    <Context ref="context" overflow-scroll max-height-if-outside-viewport>
      <div>
        <ul class="context__menu context__menu--can-be-active">
          <li class="context__menu-item">
            <a
              class="context__menu-item-link context__menu-item-link--with-desc"
              :class="{ active: isModeMentions }"
              @click.prevent="updateNotificationMode('mentions')"
            >
              <span class="context__menu-item-title">{{
                $t('RowEditModalCommentNotificationMode.modeMentionsTitle')
              }}</span>
              <div class="context__menu-item-description">
                {{ $t('RowEditModalCommentNotificationMode.modeMentionsDesc') }}
              </div>
              <div
                v-if="!hasPremiumFeaturesEnabled"
                class="context__menu-deactivated-icon"
              >
                <i class="iconoir-lock"></i>
              </div>
              <i
                v-else-if="isModeMentions"
                class="context__menu-active-icon iconoir-check"
              ></i>
            </a>
          </li>
          <li class="context__menu-item">
            <a
              class="context__menu-item-link context__menu-item-link--with-desc"
              :class="{ active: isModeAll }"
              @click.prevent="updateNotificationMode('all')"
            >
              <span class="context__menu-item-title">{{
                $t('RowEditModalCommentNotificationMode.modeAllTitle')
              }}</span>
              <div class="context__menu-item-description">
                {{ $t('RowEditModalCommentNotificationMode.modeAllDesc') }}
              </div>
              <div
                v-if="!hasPremiumFeaturesEnabled"
                class="context__menu-deactivated-icon"
              >
                <i class="iconoir-lock"></i>
              </div>
              <i
                v-else-if="isModeAll"
                class="context__menu-active-icon iconoir-check"
              ></i>
            </a>
          </li>
        </ul>
      </div>
    </Context>
    <PaidFeaturesModal
      ref="paidFeaturesModal"
      initial-selected-type="row_notifications"
      :workspace="database.workspace"
    ></PaidFeaturesModal>
  </div>
</template>

<script>
import context from '@baserow/modules/core/mixins/context'
import { notifyIf } from '@baserow/modules/core/utils/error'
import PremiumFeatures from '@baserow_premium/features'
import PaidFeaturesModal from '@baserow_premium/components/PaidFeaturesModal'

const MODE_ALL = 'all'
const MODE_MENTIONS = 'mentions'

export default {
  name: 'RowEditModalCommentNotificationMode',
  components: {
    PaidFeaturesModal,
  },
  mixins: [context],
  props: {
    database: {
      type: Object,
      required: true,
    },
    table: {
      type: Object,
      required: true,
    },
    row: {
      type: Object,
      required: true,
    },
  },
  computed: {
    hasPremiumFeaturesEnabled() {
      return this.$hasFeature(
        PremiumFeatures.PREMIUM,
        this.database.workspace.id
      )
    },
    isModeAll() {
      return (
        this.hasPremiumFeaturesEnabled &&
        this.row._.metadata.row_comments_notification_mode === MODE_ALL
      )
    },
    isModeMentions() {
      // Mode mentions is the default mode, and the backend will not store it
      // (so it will be undefined). Once set in the frontend, it will be stored
      // as 'mentions'
      return (
        this.hasPremiumFeaturesEnabled &&
        [undefined, MODE_MENTIONS].includes(
          this.row._.metadata.row_comments_notification_mode
        )
      )
    },
  },
  methods: {
    async updateNotificationMode(mode) {
      if (!this.hasPremiumFeaturesEnabled) {
        this.$refs.context.hide()
        this.$refs.paidFeaturesModal.show()
        return
      }

      if (
        (mode === MODE_ALL && this.isModeAll) ||
        (mode === MODE_MENTIONS && this.isModeMentions)
      ) {
        return // nothing to do
      }

      try {
        await this.$store.dispatch('row_comments/updateNotificationMode', {
          table: this.table,
          row: this.row,
          mode,
        })
      } catch (error) {
        notifyIf(error, 'application')
      }
    },
  },
}
</script>
