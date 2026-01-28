<template>
  <Context ref="context" overflow-scroll max-height-if-outside-viewport>
    <template v-if="Object.keys(invitation).length > 0">
      <ul class="context__menu">
        <li class="context__menu-item">
          <a
            class="context__menu-item-link"
            @click.prevent="copyEmail(invitation)"
          >
            <Copied ref="emailCopied"></Copied>
            {{ $t('membersSettings.invitesTable.actions.copyEmail') }}
          </a>
        </li>
        <li class="context__menu-item context__menu-item--with-separator">
          <a
            :class="{
              'context__menu-item-link--loading': removeLoading,
            }"
            class="context__menu-item-link context__menu-item-link--delete"
            @click.prevent="remove(invitation)"
          >
            <i class="context__menu-item-icon iconoir-bin"></i>
            {{ $t('membersSettings.invitesTable.actions.remove') }}
          </a>
        </li>
      </ul>
    </template>
  </Context>
</template>

<script>
import context from '@baserow/modules/core/mixins/context'
import { notifyIf } from '@baserow/modules/core/utils/error'
import WorkspaceService from '@baserow/modules/core/services/workspace'

export default {
  name: 'EditInviteContext',
  mixins: [context],
  props: {
    invitation: {
      required: true,
      type: Object,
    },
  },
  emits: ['refresh'],
  data() {
    return {
      removeLoading: false,
    }
  },
  methods: {
    async copyEmail({ email }) {
      await navigator.clipboard.writeText(email)
      this.$refs.emailCopied.show()
    },
    async remove(invitation) {
      if (this.removeLoading) {
        return
      }

      this.removeLoading = true

      try {
        await WorkspaceService(this.$client).deleteInvitation(invitation.id)
        this.$emit('refresh')
        this.hide()
      } catch (error) {
        notifyIf(error)
      } finally {
        this.removeLoading = false
      }
    },
  },
}
</script>
