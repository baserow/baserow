<template>
  <Modal ref="modal" :left-sidebar="true">
    <template #sidebar>
      <div class="modal-sidebar__title">
        {{ $t('membersSettings.membersInviteModal.title') }}
      </div>
      <ul class="modal-sidebar__nav">
        <li v-for="inviteType in inviteTypes" :key="inviteType.type">
          <a
            class="modal-sidebar__nav-link"
            :class="{ active: activeInviteType === inviteType.type }"
            @click="activeInviteType = inviteType.type"
          >
            <i
              class="modal-sidebar__nav-icon"
              :class="inviteType.getIconClass()"
            ></i>
            {{ inviteType.getName() }}
          </a>
        </li>
      </ul>
    </template>
    <template #content>
      <h2 class="box__title">
        {{ $t('membersSettings.membersInviteModal.title') }}
      </h2>
      <component
        :is="activeInviteComponent"
        ref="invite"
        :workspace="workspace"
        @submitted="inviteSubmitted"
      ></component>
    </template>
  </Modal>
</template>

<script>
import modal from '@baserow/modules/core/mixins/modal'

export default {
  name: 'MembersInviteModal',
  mixins: [modal],
  props: {
    workspace: {
      type: Object,
      required: true,
    },
  },
  emits: ['invite-submitted'],
  data() {
    return {
      activeInviteType: null,
    }
  },
  computed: {
    inviteTypes() {
      return this.$registry
        .getOrderedList('invite')
        .filter((inviteType) => inviteType.isVisible?.(this.workspace) ?? true)
    },
    activeInviteComponent() {
      return this.inviteTypes
        .find((inviteType) => inviteType.type === this.activeInviteType)
        ?.getComponent()
    },
  },
  methods: {
    show(...args) {
      this.activeInviteType = this.inviteTypes[0]?.type ?? null
      this.$nextTick(() => this.$refs.invite?.reset?.())
      return modal.methods.show.call(this, ...args)
    },
    inviteSubmitted() {
      this.$emit('invite-submitted')
      this.hide()
    },
  },
}
</script>
