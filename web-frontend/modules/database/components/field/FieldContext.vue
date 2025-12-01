<template>
  <Context ref="context" overflow-scroll max-height-if-outside-viewport>
    <div class="context__menu-title">{{ field.name }} ({{ field.id }})</div>
    <ul class="context__menu">
      <li
        v-if="
          $hasPermission(
            'database.table.field.update',
            field,
            database.workspace.id
          )
        "
        class="context__menu-item"
      >
        <a
          ref="updateFieldContextLink"
          class="context__menu-item-link grid-view__description-options"
          @click="
            $refs.updateFieldContext.toggle(
              $refs.updateFieldContextLink,
              'bottom',
              'left',
              0
            )
          "
        >
          <i class="context__menu-item-icon iconoir-edit-pencil"></i>
          {{ $t('fieldContext.editField') }}
        </a>
        <UpdateFieldContext
          ref="updateFieldContext"
          :table="table"
          :view="view"
          :field="field"
          :all-fields-in-table="allFieldsInTable"
          :database="database"
          @update="$emit('update', $event)"
          @updated="$refs.context.hide()"
        ></UpdateFieldContext>
      </li>
      <li
        v-if="
          field.primary &&
          $hasPermission(
            'database.table.field.update',
            field,
            database.workspace.id
          )
        "
        class="context__menu-item"
      >
        <a
          class="context__menu-item-link"
          @click="$refs.changePrimaryFieldModal.show()"
        >
          <i class="context__menu-item-icon iconoir-coins-swap"></i>
          {{ $t('fieldContext.changePrimaryField') }}
        </a>
        <ChangePrimaryFieldModal
          ref="changePrimaryFieldModal"
          :all-fields-in-table="allFieldsInTable"
          :from-field="field"
          :table="table"
        ></ChangePrimaryFieldModal>
      </li>
      <li
        v-for="(
          updateFieldContextComponent, index
        ) in updateFieldContextExtraItems"
        :key="'update-field-menu-item' + index"
      >
        <component
          :is="updateFieldContextComponent"
          :field="field"
          :view="view"
          :table="table"
          :database="database"
          @hide-context="$refs.context.hide()"
        ></component>
      </li>
      <slot></slot>
      <li
        v-if="
          !field.primary &&
          !syncedUniquePrimary &&
          $hasPermission(
            'database.table.field.delete',
            field,
            database.workspace.id
          )
        "
        class="context__menu-item context__menu-item--with-separator"
      >
        <a
          :class="{ 'context__menu-item-link--loading': deleteLoading }"
          class="context__menu-item-link context__menu-item-link--delete"
          @click="deleteField()"
        >
          <i class="context__menu-item-icon iconoir-bin"></i>
          {{ $t('fieldContext.deleteField') }}
        </a>
      </li>
    </ul>
  </Context>
</template>

<script>
import context from '@baserow/modules/core/mixins/context'
import UpdateFieldContext from '@baserow/modules/database/components/field/UpdateFieldContext'
import { notifyIf } from '@baserow/modules/core/utils/error'
import ChangePrimaryFieldModal from '@baserow/modules/database/components/field/ChangePrimaryFieldModal'

export default {
  name: 'FieldContext',
  components: {
    ChangePrimaryFieldModal,
    UpdateFieldContext,
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
    view: {
      type: [Object, null],
      required: false,
      default: null,
    },
    field: {
      type: Object,
      required: true,
    },
    allFieldsInTable: {
      type: Array,
      required: true,
    },
  },
  data() {
    return {
      deleteLoading: false,
    }
  },
  computed: {
    syncedUniquePrimary() {
      if (!this.table.data_sync) {
        return false
      }
      return this.table.data_sync.synced_properties.some((p) => {
        return p.field_id === this.field.id && p.unique_primary
      })
    },
    updateFieldContextExtraItems() {
      const extraMenuItems = Object.values(
        this.$registry.getAll('fieldContextItem')
      )

      return extraMenuItems
        .map((menuItemType) => menuItemType.getComponent())
        .filter((component) => component !== null)
    },
  },
  methods: {
    // Allows other components to toggle the `FieldContext`
    // and then, once visible, immediately show the
    // `UpdateFieldContext` at the same time.
    showUpdateFieldContext() {
      this.$refs.updateFieldContext.toggle(
        this.$refs.updateFieldContextLink,
        'bottom',
        'left'
      )
    },
    isFieldReadOnly(field) {
      const fieldType = this.$registry.get('field', field.type)
      return fieldType.isReadOnly || field.read_only
    },
    async deleteField() {
      this.deleteLoading = true
      const { field } = this

      try {
        const { data } = await this.$store.dispatch('field/deleteCall', field)
        this.$emit('delete')
        await this.$store.dispatch('field/forceDelete', field)
        await this.$store.dispatch('field/forceUpdateFields', {
          fields: data.related_fields,
        })
        await this.$store.dispatch('toast/restore', {
          trash_item_type: 'field',
          trash_item_id: field.id,
        })
      } catch (error) {
        if (error.response && error.response.status === 404) {
          this.$emit('delete')
          await this.$store.dispatch('field/forceDelete', field)
        } else {
          notifyIf(error, 'field')
        }
      }
      this.hide()
      this.deleteLoading = false
    },
  },
}
</script>
