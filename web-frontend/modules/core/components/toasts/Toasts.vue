<template>
  <div>
    <div class="toasts__container-top">
      <PermissionsUpdatedToast v-if="permissionsUpdated" />
      <UserSessionExpiredToast
        v-if="isUserSessionExpired"
      ></UserSessionExpiredToast>
      <UserPasswordChangedToast
        v-if="isUserPasswordChanged"
      ></UserPasswordChangedToast>
      <WorkspaceOutdatedToast v-if="workspaceOutdated && !reconnecting" />
      <ConnectingToast v-if="reconnecting" />
      <FailedConnectingToast v-if="failedConnecting"></FailedConnectingToast>
      <AuthorizationErrorToast v-if="unauthorized"></AuthorizationErrorToast>
      <Toast
        v-for="toast in normalToasts"
        :key="toast.id"
        :type="toast.type"
        :icon="toastIcon(toast.type)"
        close-button
        @close="closeToast(toast)"
      >
        <template #title>{{ toast.title }}</template>
        <span>{{ toast.message }}</span>
      </Toast>
    </div>

    <div class="toasts__container-bottom">
      <UndoRedoToast
        v-if="undoRedoIsNotHidden"
        :state="undoRedoState"
      ></UndoRedoToast>
      <CopyingToast v-if="copying"></CopyingToast>
      <PastingToast v-if="pasting"></PastingToast>
      <ClearingToast v-if="clearing"></ClearingToast>
      <RestoreToast
        v-for="toast in restoreToasts"
        :key="toast.id"
        :toast="toast"
      ></RestoreToast>
    </div>
  </div>
</template>

<script>
import { mapGetters, mapState } from 'vuex'

import Toast from '@baserow/modules/core/components/toasts/Toast'
import ConnectingToast from '@baserow/modules/core/components/toasts/ConnectingToast'
import FailedConnectingToast from '@baserow/modules/core/components/toasts/FailedConnectingToast'
import RestoreToast from '@baserow/modules/core/components/toasts/RestoreToast'
import CopyingToast from '@baserow/modules/core/components/toasts/CopyingToast'
import PastingToast from '@baserow/modules/core/components/toasts/PastingToast'
import ClearingToast from '@baserow/modules/core/components/toasts/ClearingToast'
import AuthorizationErrorToast from '@baserow/modules/core/components/toasts/AuthorizationErrorToast'
import UserSessionExpiredToast from '@baserow/modules/core/components/toasts/UserSessionExpiredToast'
import UserPasswordChangedToast from '@baserow/modules/core/components/toasts/UserPasswordChangedToast'
import UndoRedoToast from '@baserow/modules/core/components/toasts/UndoRedoToast'
import { UNDO_REDO_STATES } from '@baserow/modules/core/utils/undoRedoConstants'
import PermissionsUpdatedToast from '@baserow/modules/core/components/toasts/PermissionsUpdatedToast'
import WorkspaceOutdatedToast from '@baserow/modules/core/components/toasts/WorkspaceOutdatedToast'

export default {
  name: 'Toasts',
  components: {
    PermissionsUpdatedToast,
    WorkspaceOutdatedToast,
    RestoreToast,
    Toast,
    ConnectingToast,
    FailedConnectingToast,
    CopyingToast,
    PastingToast,
    ClearingToast,
    AuthorizationErrorToast,
    UndoRedoToast,
    UserSessionExpiredToast,
    UserPasswordChangedToast,
  },
  computed: {
    undoRedoIsNotHidden() {
      return this.undoRedoState !== UNDO_REDO_STATES.HIDDEN
    },
    restoreToasts() {
      return this.toasts.filter((n) => n.type === 'restore')
    },
    normalToasts() {
      return this.toasts.filter((n) => n.type !== 'restore')
    },
    ...mapState({
      unauthorized: (state) => state.toast.authorizationError,
      failedConnecting: (state) => state.toast.failedConnecting,
      reconnecting: (state) => state.toast.reconnecting,
      copying: (state) => state.toast.copying,
      pasting: (state) => state.toast.pasting,
      clearing: (state) => state.toast.clearing,
      toasts: (state) => state.toast.items,
      undoRedoState: (state) => state.toast.undoRedoState,
      isUserSessionExpired: (state) => state.toast.userSessionExpired,
      isUserPasswordChanged: (state) => state.toast.userPasswordChanged,
      permissionsUpdated: (state) => state.toast.permissionsUpdated,
      workspaceOutdated: (state) => state.toast.workspaceOutdated,
    }),
    ...mapGetters({ isAuthenticated: 'auth/isAuthenticated' }),
  },
  watch: {
    isAuthenticated(value) {
      if (!value) {
        this.$store.dispatch('toast/userLoggedOut')
      }
    },
  },
  methods: {
    toastIcon(toastType) {
      switch (toastType) {
        case 'warning':
          return 'iconoir-warning-circle'
        case 'success':
          return 'iconoir-check-circle'
        case 'info-primary':
          return 'iconoir-info-empty'
        case 'error':
          return 'iconoir-warning-triangle'
        default:
          return 'iconoir-info-empty'
      }
    },
    closeToast(toast) {
      this.$store.dispatch('toast/remove', toast)
    },
  },
}
</script>
