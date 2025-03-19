<template>
  <!-- Show user source list -->
  <div
    v-if="!showForm && editedUserSource === null"
    class="user-sources-settings"
  >
    <h2 class="box__title">{{ $t('userSourceSettings.titleOverview') }}</h2>
    <Error :error="error"></Error>
    <div v-if="!error.visible" class="actions actions--right">
      <Button icon="iconoir-plus" @click="displayForm()">
        {{ $t('userSourceSettings.addUserSource') }}
      </Button>
    </div>
    <div
      v-for="userSource in userSources"
      :key="userSource.id"
      class="user-source-settings__user-source"
      @delete="deleteUserSource(userSource)"
    >
      <Presentation
        :image="getUserSourceType(userSource).image"
        :title="userSource.name"
        :subtitle="getUserSourceType(userSource).getSummary(userSource)"
        :rounded-icon="false"
        avatar-color="transparent"
        style="flex: 1"
      />
      <div class="user-source-settings__user-source-actions">
        <ButtonIcon icon="iconoir-edit" @click="displayForm(userSource)" />
        <ButtonIcon icon="iconoir-bin" @click="deleteUserSource(userSource)" />
      </div>
    </div>
    <p v-if="!error.visible && userSources.length === 0" class="margin-top-3">
      {{ $t('userSourceSettings.noUserSourceMessage') }}
    </p>
  </div>
  <!-- Edit user source -->
  <div v-else-if="editedUserSource">
    <h2 class="box__title">
      {{ $t('userSourceSettings.titleUpdateUserSource') }}
    </h2>
    <Error :error="error"></Error>

    <Presentation
      :image="getUserSourceType(editedUserSource).image"
      :title="getUserSourceType(editedUserSource).name"
      :rounded-icon="false"
      avatar-color="transparent"
      style="flex: 1; margin-bottom: 18px"
      icon-size="medium"
    />
    <UpdateUserSourceForm
      ref="userSourceForm"
      :builder="builder"
      :user-source-type="getUserSourceType(editedUserSource)"
      :default-values="editedUserSource"
      @submitted="updateUserSource"
      @values-changed="onValueChange"
    />

    <div class="actions">
      <ButtonText
        type="secondary"
        icon="iconoir-nav-arrow-left"
        @click="editedUserSource = null"
      >
        {{ $t('action.back') }}
      </ButtonText>
      <Button
        :disabled="actionInProgress || invalidForm"
        :loading="actionInProgress"
        size="large"
        @click="$refs.userSourceForm.submit(true)"
      >
        {{ $t('action.save') }}
      </Button>
    </div>
  </div>
  <!-- Create user source -->
  <div v-else>
    <h2 class="box__title">
      {{ $t('userSourceSettings.titleAddUserSource') }}
    </h2>
    <Error :error="error"></Error>
    <CreateUserSourceForm
      ref="userSourceForm"
      :builder="builder"
      @submitted="createUserSource"
      @values-changed="onValueChange"
    />
    <div class="actions">
      <ButtonText
        type="secondary"
        icon="iconoir-nav-arrow-left"
        @click="hideForm"
      >
        {{ $t('action.back') }}
      </ButtonText>

      <Button
        :disabled="actionInProgress || invalidForm"
        :loading="actionInProgress"
        size="large"
        @click="$refs.userSourceForm.submit()"
      >
        {{ $t('action.create') }}
      </Button>
    </div>
  </div>
</template>

<script>
import { mapActions } from 'vuex'
import error from '@baserow/modules/core/mixins/error'
import { clone } from '@baserow/modules/core/utils/object'
import { notifyIf } from '@baserow/modules/core/utils/error'
import CreateUserSourceForm from '@baserow/modules/builder/components/userSource/CreateUserSourceForm'
import UpdateUserSourceForm from '@baserow/modules/builder/components/userSource/UpdateUserSourceForm'
import builderSetting from '@baserow/modules/builder/components/settings/mixins/builderSetting'

export default {
  name: 'UserSourceSettings',
  components: { CreateUserSourceForm, UpdateUserSourceForm },
  mixins: [error, builderSetting],
  provide() {
    return { builder: this.builder }
  },
  data() {
    return {
      showForm: false,
      editedUserSource: null,
      actionInProgress: false,
      invalidForm: true,
    }
  },
  computed: {
    integrations() {
      return this.$store.getters['integration/getIntegrations'](this.builder)
    },
    userSources() {
      return this.$store.getters['userSource/getUserSources'](this.builder)
    },
  },
  async mounted() {
    try {
      await this.actionFetchIntegrations({
        application: this.builder,
      })
      // We load the domains here because some providers might use them
      await this.actionFetchDomains({ builderId: this.builder.id })
    } catch (error) {
      notifyIf(error)
    }
  },
  methods: {
    ...mapActions({
      actionFetchIntegrations: 'integration/fetch',
      actionCreateUserSource: 'userSource/create',
      actionUpdateUserSource: 'userSource/update',
      actionDeleteUserSource: 'userSource/delete',
      actionFetchDomains: 'domain/fetch',
    }),
    getUserSourceType(userSource) {
      return this.$registry.get('userSource', userSource.type)
    },
    onValueChange() {
      this.invalidForm = !this.$refs.userSourceForm.isFormValid()
    },
    async displayForm(userSourceToEdit) {
      if (userSourceToEdit) {
        this.editedUserSource = userSourceToEdit
      } else {
        this.showForm = true
      }
      await this.$nextTick()
      this.onValueChange()
    },
    hideForm() {
      this.showForm = false
      this.editedUserSource = null
      this.hideError()
      this.invalidForm = true
    },
    async createUserSource(values) {
      this.actionInProgress = true
      const { type, ...rest } = values
      try {
        const createdUserSource = await this.actionCreateUserSource({
          application: this.builder,
          userSourceType: type,
          values: rest,
        })

        this.hideForm()
        // immediately select this user source to edit it.
        this.editedUserSource = createdUserSource
      } catch (error) {
        this.handleError(error)
      }
      this.actionInProgress = false
    },
    async updateUserSource(newValues) {
      if (!this.$refs.userSourceForm.isFormValid(true)) {
        return
      }

      this.actionInProgress = true
      try {
        await this.actionUpdateUserSource({
          application: this.builder,
          userSourceId: this.editedUserSource.id,
          values: clone(newValues),
        })
        // If the builder settings modal is set to hide after create, normally
        // we would have hidden the modal and shared the record ID after the user
        // source was created, but in this settings component we'll share the ID
        // after the update, when there's a better change of having a configure source.
        this.hideModalIfRequired(this.editedUserSource.id)
        this.hideForm()
      } catch (error) {
        // Restore the previously saved values from the store
        if (!this.$refs.userSourceForm.handleServerError(error)) {
          this.$refs.userSourceForm.reset()
          this.handleError(error)
        }
      }
      this.actionInProgress = false
    },
    async deleteUserSource(userSource) {
      try {
        await this.actionDeleteUserSource({
          application: this.builder,
          userSourceId: userSource.id,
        })
      } catch (error) {
        notifyIf(error)
      }
    },
  },
}
</script>
