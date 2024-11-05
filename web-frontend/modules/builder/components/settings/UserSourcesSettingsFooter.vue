<template>
  <div>
    <template v-if="displayUserSourceForm">
      <Button type="secondary" @click="handleCancelBtn">
        {{ $t('action.cancel') }}
      </Button>

      <Button v-if="createUserSource" @click="handleCreateUserSourceBtn">
        {{ $t('action.create') }}
      </Button>
      <Button v-if="editUserSource" @click="handleEditUserSourceBtn">
        {{ $t('action.save') }}
      </Button>
    </template>
    <Button v-else @click="handleAddUserSourceBtn()">
      {{ $t('userSourceSettings.addUserSource') }}
    </Button>
  </div>
</template>

<script>
export default {
  name: 'UserSourcesSettingsFooter',
  data() {
    return {
      displayUserSourceForm: false,
      createUserSource: true,
      editUserSource: false,
    }
  },
  methods: {
    handleAddUserSourceBtn() {
      this.displayUserSourceForm = true
      this.$emit('show-user-source-form')
    },
    handleCancelBtn() {
      this.displayUserSourceForm = false
      this.createUserSource = true
      this.editUserSource = false
      this.$emit('hide-user-source-form')
    },
    handleCreateUserSourceBtn() {
      this.createUserSource = false
      this.editUserSource = true
      this.$emit('create-user-source')
    },
    handleEditUserSourceBtn() {
      this.createUserSource = true
      this.editUserSource = false
      this.displayUserSourceForm = false
      this.$emit('edit-user-source')
    },
    setEditMode() {
      this.displayUserSourceForm = true
      this.createUserSource = false
      this.editUserSource = true
    },
  },
}
</script>
