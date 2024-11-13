<template>
  <div
    class="notification-panel"
    :class="{ 'visibility-hidden': !open }"
    ph-autocapture="notifications"
  >
    <div class="notification-panel__head">
      <div class="notification-panel__title">
        {{ $t('notificationPanel.title') }}
      </div>
      <div v-show="totalCount > 0" class="notification-panel__actions">
        <a
          v-show="unreadCount > 0"
          class="notification-panel__action"
          @click="markAllAsRead"
        >
          {{ $t('notificationPanel.markAllAsRead') }}
        </a>
        <a
          class="notification-panel__action"
          @click="$refs.clearAllConfirmModal.show()"
        >
          {{ $t('notificationPanel.clearAll') }}
        </a>
      </div>
    </div>
    <div v-if="!loaded && loading" class="loading-absolute-center"></div>
    <div v-else-if="totalCount === 0" class="notification-panel__empty">
      <i class="notification-panel__empty-icon iconoir-bell-off"></i>
      <div class="notification-panel__empty-title">
        {{ $t('notificationPanel.noNotificationTitle') }}
      </div>
      <div class="notification-panel__empty-text">
        {{ $t('notificationPanel.noNotification') }}
      </div>
    </div>
    <div v-else class="notification-panel__body">
      <div v-if="needRefresh" class="notification-panel__refresh-hint">
        <div class="notification-panel__refresh-hint-text">
          <span class="notification-panel__refresh-hint-icon"></span>
          {{ $t('notificationPanel.newNotificationsAvailable') }}
        </div>
        <Button type="secondary" @click.prevent="initialLoad">
          {{ $t('notificationPanel.refresh') }}
        </Button>
      </div>
      <InfiniteScroll
        ref="infiniteScroll"
        :current-count="currentCount"
        :max-count="totalCount"
        :loading="loading"
        :render-end="false"
        @load-next-page="loadNextPage"
      >
        <template #default>
          <div
            v-for="(notification, index) in notifications"
            :key="index"
            class="notification-panel__notification"
            :class="{
              'notification-panel__notification--unread': !notification.read,
            }"
          >
            <div class="notification-panel__notification-icon">
              <component
                :is="getNotificationIcon(notification)"
                :notification="notification"
                v-bind="getNotificationIconProps(notification)"
              >
              </component>
            </div>
            <div class="notification-panel__notification-content">
              <component
                :is="getNotificationContent(notification)"
                :notification="notification"
                :workspace="workspace"
                @close-panel="hide"
              >
              </component>
              <div class="notification-panel__notification-time">
                {{ timeAgo(notification.created_on) }}
              </div>
            </div>
            <div class="notification-panel__notification-status">
              <span v-if="!notification.read"></span>
            </div>
          </div>
        </template>
      </InfiniteScroll>
    </div>
    <ClearAllNotificationsConfirmModal
      ref="clearAllConfirmModal"
      @confirm="
        ($event) => {
          $event.preventDefault()
          $event.stopPropagation()
          clearAll()
        }
      "
      @cancel="
        ($event) => {
          $event.preventDefault()
          $event.stopPropagation()
        }
      "
    ></ClearAllNotificationsConfirmModal>
  </div>
</template>

<script>
import { mapGetters } from 'vuex'
import moment from '@baserow/modules/core/moment'
import { isElement, onClickOutside } from '@baserow/modules/core/utils/dom'
import { notifyIf } from '@baserow/modules/core/utils/error'
import InfiniteScroll from '@baserow/modules/core/components/helpers/InfiniteScroll'
import ClearAllNotificationsConfirmModal from '@baserow/modules/core/components/modals/ClearAllNotificationsConfirmModal'
import MoveToBody from '@baserow/modules/core/mixins/moveToBody'

export default {
  name: 'NotificationPanel',
  components: {
    ClearAllNotificationsConfirmModal,
    InfiniteScroll,
  },
  mixins: [MoveToBody],
  data() {
    return {
      open: false,
      needRefresh: false,
    }
  },
  computed: {
    ...mapGetters({
      workspaceId: 'notification/getWorkspaceId',
      notifications: 'notification/getAll',
      loading: 'notification/getLoading',
      loaded: 'notification/getLoaded',
      unreadCount: 'notification/getUnreadCount',
      currentCount: 'notification/getCurrentCount',
      totalCount: 'notification/getTotalCount',
    }),
    workspace() {
      return this.$store.getters['workspace/get'](this.workspaceId)
    },
  },
  watch: {
    loaded(isLoaded) {
      // On receiving many notifications, only the unread count is sent via web
      // sockets and the 'loaded' state resets to false in the store. This
      // watcher ensure to do the correct action if the panel is open and we
      // receive new notifications.

      if (isLoaded || !this.open) {
        return
      }

      // If we have no notifications, we can safely load the initial set.
      // Otherwise, we show a hint that new notifications are available.
      if (this.totalCount === 0) {
        this.initialLoad()
      } else {
        this.needRefresh = true
      }
    },
  },
  methods: {
    async initialLoad() {
      this.needRefresh = false
      try {
        await this.$store.dispatch('notification/fetchAll', {
          workspaceId: this.workspaceId,
        })
      } catch (e) {
        notifyIf(e, 'application')
      }
    },
    show(target) {
      if (!this.loaded && !this.loading) {
        this.initialLoad()
      }
      this.open = true
      const opener = target
      const removeOnClickOutsideHandler = onClickOutside(this.$el, (target) => {
        if (
          this.open &&
          !isElement(opener, target) &&
          !this.moveToBody.children.some((child) => {
            return isElement(child.$el, target)
          })
        ) {
          this.hide()
        }
      })
      this.$once('hidden', removeOnClickOutsideHandler)
      this.$emit('shown')
    },
    hide() {
      this.open = false
      this.opener = null
      this.$emit('hidden')
    },
    toggle(target) {
      if (this.open) {
        this.hide()
      } else {
        this.show(target)
      }
    },
    async markAllAsRead() {
      try {
        await this.$store.dispatch('notification/markAllAsRead')
      } catch (error) {
        notifyIf(error, 'application')
      }
    },
    async clearAll() {
      try {
        await this.$store.dispatch('notification/clearAll')
      } catch (error) {
        notifyIf(error, 'application')
      }
    },
    getNotificationIcon(notification) {
      return this.$registry
        .get('notification', notification.type)
        .getIconComponent()
    },
    getNotificationIconProps(notification) {
      return this.$registry
        .get('notification', notification.type)
        .getIconComponentProps()
    },
    getNotificationContent(notification) {
      return this.$registry
        .get('notification', notification.type)
        .getContentComponent()
    },
    timeAgo(timestamp) {
      return moment.utc(timestamp).fromNow()
    },
    async loadNextPage() {
      try {
        await this.$store.dispatch('notification/fetchNextSetOfNotifications')
      } catch (e) {
        notifyIf(e, 'application')
      }
    },
  },
}
</script>
