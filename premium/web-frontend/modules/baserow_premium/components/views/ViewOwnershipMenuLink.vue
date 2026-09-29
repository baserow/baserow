<template>
  <li v-if="isVisible" class="context__menu-item">
    <a
      v-if="!changeOwnershipTypeIsDeactivated"
      class="context__menu-item-link"
      @click="changeOwnershipType(view.ownership_type)"
    >
      <i class="context__menu-item-icon iconoir-right-round-arrow"></i>
      {{ changeOwnershipTypeText }}
    </a>
    <a
      v-else
      v-tooltip="$t('premium.deactivated')"
      class="context__menu-item-link"
      @click="$refs.paidFeaturesModal.show()"
    >
      <i class="context__menu-item-icon iconoir-right-round-arrow"></i>
      {{ changeOwnershipTypeText }}
      <div class="deactivated-label">
        <i class="iconoir-lock"></i>
      </div>
    </a>
    <PaidFeaturesModal
      ref="paidFeaturesModal"
      initial-selected-type="personal_views"
      :workspace="database.workspace"
    ></PaidFeaturesModal>
  </li>
</template>

<script>
import { notifyIf } from '@baserow/modules/core/utils/error'
import { CollaborativeViewOwnershipType } from '@baserow/modules/database/viewOwnershipTypes'
import { PersonalViewOwnershipType } from '@baserow_premium/viewOwnershipTypes'
import PaidFeaturesModal from '@baserow_premium/components/PaidFeaturesModal'

export default {
  name: 'ViewOwnershipMenuLink',
  components: {
    PaidFeaturesModal,
  },
  props: {
    view: {
      type: Object,
      required: true,
    },
    database: {
      type: Object,
      required: true,
    },
  },
  computed: {
    targetOwnershipType() {
      return this.view.ownership_type === PersonalViewOwnershipType.getType()
        ? CollaborativeViewOwnershipType.getType()
        : PersonalViewOwnershipType.getType()
    },
    isVisible() {
      if (
        ![
          CollaborativeViewOwnershipType.getType(),
          PersonalViewOwnershipType.getType(),
        ].includes(this.view.ownership_type)
      ) {
        return false
      }

      const workspaceId = this.database.workspace.id
      const isPersonal =
        this.view.ownership_type === PersonalViewOwnershipType.getType()

      // For personal→collaborative: check against collaborative target so the
      // view_ownership manager passes through and basic/role decides correctly.
      // For collaborative→personal: check against current view — view_ownership
      // already passes through for collaborative views.
      const permissionContext = isPersonal
        ? {
            ...this.view,
            ownership_type: this.targetOwnershipType,
            owned_by_id: null,
          }
        : this.view

      return this.$hasPermission(
        'database.table.view.update',
        permissionContext,
        workspaceId
      )
    },
    changeOwnershipTypeOptions() {
      const collaborativeOwnershipType = this.$registry.get(
        'viewOwnershipType',
        CollaborativeViewOwnershipType.getType()
      )
      const personalOwnershipType = this.$registry.get(
        'viewOwnershipType',
        PersonalViewOwnershipType.getType()
      )
      const workspaceId = this.database.workspace.id

      return {
        [collaborativeOwnershipType.getType()]: {
          text: this.$t('viewContext.toPersonal'),
          targetType: personalOwnershipType.getType(),
          isDeactivated: personalOwnershipType.isDeactivated(workspaceId),
        },
        [personalOwnershipType.getType()]: {
          text: this.$t('viewContext.toCollaborative'),
          targetType: collaborativeOwnershipType.getType(),
          isDeactivated: collaborativeOwnershipType.isDeactivated(workspaceId),
        },
      }
    },
    changeOwnershipTypeText() {
      return this.changeOwnershipTypeOptions[this.view.ownership_type].text
    },
    changeOwnershipTypeIsDeactivated() {
      return this.changeOwnershipTypeOptions[this.view.ownership_type]
        .isDeactivated
    },
  },
  methods: {
    async changeOwnershipType() {
      const targetType =
        this.changeOwnershipTypeOptions[this.view.ownership_type].targetType
      try {
        await this.$store.dispatch('view/update', {
          view: this.view,
          values: { ownership_type: targetType },
        })
      } catch (error) {
        notifyIf(error, 'view')
      }
    },
  },
}
</script>
