<template>
  <div class="invitation-links">
    <h2 v-if="!targetType.getTitle(workspace, target)" class="box__title">
      {{ $t('inviteModal.linkTitle') }}
    </h2>
    <Error :error="error"></Error>
    <div v-if="loading" class="loading"></div>
    <div v-else-if="invitationLinks.length === 0" class="invitation-link-empty">
      <div class="invitation-link-empty__icon">
        <i class="iconoir-link"></i>
      </div>
      <h3 class="invitation-link-empty__title">
        {{ $t('inviteModal.linkEmptyTitle') }}
      </h3>
      <p class="invitation-link-empty__description">
        {{ $t('inviteModal.linkEmptyDescription') }}
      </p>
    </div>
    <template v-else>
      <div class="invitation-links__head">
        <div class="invitation-links__role">
          {{ $t('inviteModal.linkInviteAs') }}
        </div>
        <div class="invitation-links__url">
          {{ $t('inviteModal.linkColumn') }}
        </div>
      </div>
      <ul class="invitation-links__items">
        <li
          v-for="invitationLink in invitationLinks"
          :key="invitationLink.id"
          class="invitation-links__item"
        >
          <WorkspaceRoleSelector
            class="invitation-links__role"
            :model-value="invitationLink.permissions"
            :roles="roles"
            :workspace="workspace"
            show-role-icons
            @update:model-value="(uid) => updateRole(invitationLink, uid)"
          />
          <FormInput
            class="invitation-links__url"
            :model-value="getUrl(invitationLink)"
            disabled
          />
          <a
            v-tooltip="$t('inviteModal.linkCopy')"
            class="invitation-links__action"
            @click="copy(invitationLink)"
          >
            <i class="iconoir-copy"></i>
            <Copied
              :ref="(el) => (copiedRefs[invitationLink.id] = el)"
            ></Copied>
          </a>
          <a
            v-tooltip="$t('inviteModal.linkDelete')"
            class="invitation-links__action"
            @click="$refs.deleteModal.show(invitationLink)"
          >
            <i class="iconoir-bin"></i>
          </a>
        </li>
      </ul>
    </template>
    <ButtonFloating
      v-if="!loading"
      v-tooltip="$t('inviteModal.linkAdd')"
      type="secondary"
      position="absolute"
      icon="iconoir-plus"
      :loading="creating"
      :disabled="defaultRoleUid === null"
      @click="create"
    />
    <InvitationLinkAdminConfirmModal
      ref="adminConfirmModal"
      @confirm="confirmPendingChange"
    />
    <InvitationLinkDeleteModal
      ref="deleteModal"
      :workspace="workspace"
      :target="target"
      :target-type="targetType"
      @deleted="removed"
    />
  </div>
</template>

<script>
import InvitationLinkAdminConfirmModal from '@baserow/modules/core/components/invitation/InvitationLinkAdminConfirmModal'
import InvitationLinkDeleteModal from '@baserow/modules/core/components/invitation/InvitationLinkDeleteModal'
import WorkspaceRoleSelector from '@baserow/modules/core/components/workspace/WorkspaceRoleSelector'
import error from '@baserow/modules/core/mixins/error'
import { copyToClipboard } from '@baserow/modules/database/utils/clipboard'

const ADMIN_ROLE_UID = 'ADMIN'

/**
 * Lists the permanent links that anyone can use to join the target, each with
 * the role it grants, and lets the links be created, changed, copied and
 * deleted. Granting the admin role through a link and deleting a link must be
 * confirmed first. The links come from the target type, so only targets
 * supporting them get this route. It is registered behind the
 * `RBAC_IMPROVEMENTS` feature flag.
 */
export default {
  name: 'LinkInvitationRoute',
  components: {
    InvitationLinkAdminConfirmModal,
    InvitationLinkDeleteModal,
    WorkspaceRoleSelector,
  },
  mixins: [error],
  props: {
    workspace: {
      type: Object,
      required: true,
    },
    target: {
      type: Object,
      required: true,
    },
    targetType: {
      type: Object,
      required: true,
    },
  },
  data() {
    return {
      loading: true,
      creating: false,
      invitationLinks: [],
      copiedRefs: {},
      pendingChange: null,
    }
  },
  computed: {
    roles() {
      return this.targetType.getRoles(this.workspace, this.target)
    },
    /**
     * The role of a new link: the default role for invitations, or else the last
     * active one, which is the role with the least access.
     */
    defaultRoleUid() {
      const active = this.roles.filter((role) => !role.isDeactivated)
      return (
        active.find((role) => role.isDefaultForInvitations)?.uid ??
        active[active.length - 1]?.uid ??
        null
      )
    },
  },
  async mounted() {
    try {
      this.invitationLinks = await this.targetType.fetchInvitationLinks(
        this.workspace,
        this.target
      )
    } catch (error) {
      this.handleError(error)
    }
    this.loading = false
  },
  methods: {
    getUrl(invitationLink) {
      return (
        this.$config.public.publicWebFrontendUrl +
        this.$router.resolve({
          name: 'invitation-link',
          params: { slug: invitationLink.slug },
        }).href
      )
    },
    copy(invitationLink) {
      copyToClipboard(this.getUrl(invitationLink))
      this.copiedRefs[invitationLink.id]?.show()
    },
    /**
     * Runs the change right away, unless it makes the link grant the admin role,
     * in which case it waits for the confirmation.
     */
    confirmIfAdmin(roleUid, change) {
      if (roleUid === ADMIN_ROLE_UID) {
        this.pendingChange = change
        this.$refs.adminConfirmModal.show()
      } else {
        change()
      }
    },
    confirmPendingChange() {
      const change = this.pendingChange
      this.pendingChange = null
      change?.()
    },
    create() {
      this.confirmIfAdmin(this.defaultRoleUid, async () => {
        this.creating = true
        this.hideError()
        try {
          const invitationLink = await this.targetType.createInvitationLink(
            this.workspace,
            this.target,
            this.defaultRoleUid
          )
          this.invitationLinks.push(invitationLink)
        } catch (error) {
          this.handleError(error)
        }
        this.creating = false
      })
    },
    updateRole(invitationLink, roleUid) {
      if (roleUid === invitationLink.permissions) {
        return
      }
      this.confirmIfAdmin(roleUid, async () => {
        this.hideError()
        try {
          const updated = await this.targetType.updateInvitationLink(
            this.workspace,
            this.target,
            invitationLink,
            roleUid
          )
          Object.assign(invitationLink, updated)
        } catch (error) {
          this.handleError(error)
        }
      })
    },
    removed(invitationLink) {
      this.invitationLinks = this.invitationLinks.filter(
        (link) => link.id !== invitationLink.id
      )
    },
  },
}
</script>
