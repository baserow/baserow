<template>
  <Modal ref="modal" :small="true" @show="hideError()">
    <h2 class="box__title">
      {{ $t('changePrimaryFieldModal.title') }}
    </h2>
    <Error :error="error"></Error>
    <form @submit.prevent="changePrimaryField()">
      <FormGroup
        :label="$t('changePrimaryFieldModal.primaryFieldLabel')"
        small-label
        required
        :helper-text="
          $t('changePrimaryFieldModal.existingPrimary', {
            name: fromField.name,
          })
        "
      >
        <Dropdown v-model="newPrimaryFieldId">
          <DropdownItem
            v-for="field in newPrimaryFields"
            :key="'field-' + field.id"
            :name="field.name"
            :value="field.id"
            :icon="field._.type.iconClass"
            :disabled="!field._.type.canBePrimaryField"
          ></DropdownItem>
        </Dropdown>
      </FormGroup>
      <div class="actions actions--right">
        <Button
          ref="submitButton"
          type="primary"
          :loading="loading"
          :disabled="loading"
        >
          {{ $t('changePrimaryFieldModal.change') }}
        </Button>
      </div>
    </form>
  </Modal>
</template>

<script>
import error from '@baserow/modules/core/mixins/error'
import modal from '@baserow/modules/core/mixins/modal'

export default {
  name: 'ChangePrimaryFieldModal',
  mixins: [modal, error],
  props: {
    table: {
      type: Object,
      required: true,
    },
    fromField: {
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
      loading: false,
      newPrimaryFieldId: this.fromField.id,
    }
  },
  computed: {
    newPrimaryFields() {
      return this.allFieldsInTable.filter((field) => !field.primary)
    },
  },
  methods: {
    async changePrimaryField() {
      if (this.loading || this.disabled) {
        return
      }
      this.loading = true
      this.hideError()
      const newPrimaryField = this.allFieldsInTable.find(
        (field) => field.id === this.newPrimaryFieldId
      )
      try {
        await this.$store.dispatch('field/changePrimary', {
          field: newPrimaryField,
        })
        this.newPrimaryFieldId = null
        this.hide()
      } catch (error) {
        this.handleError(error)
      }
      this.loading = false
    },
  },
}
</script>
