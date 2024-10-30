<template>
  <div>
    <h4>{{ $t('domainSettings.titleAddDomain') }}</h4>
    <Error :error="error"></Error>
    <FormGroup class="margin-bottom-3">
      <Dropdown
        v-model="selectedDomain"
        :show-search="false"
        class="domain-settings__domain-type"
      >
        <DropdownItem
          v-for="option in options"
          :key="option.value.domain"
          :name="option.name"
          :value="option.value"
        />
      </Dropdown>
    </FormGroup>
    <component
      :is="currentDomainType.formComponent"
      ref="domainForm"
      :builder="builder"
      :domain="selectedDomain.domain"
      @submitted="createDomain($event)"
      @error="formHasError = $event"
    />
  </div>
</template>

<script>
import { mapActions } from 'vuex'
import error from '@baserow/modules/core/mixins/error'

export default {
  name: 'DomainsForm',
  mixins: [error],
  props: {
    builder: {
      type: Object,
      required: true,
    },
    hideForm: {
      type: Function,
      required: true,
    },
  },
  data() {
    return {
      selectedDomain: { type: 'custom', domain: 'custom' },
      createLoading: false,
      formHasError: false,
    }
  },
  computed: {
    domainTypes() {
      return Object.values(this.$registry.getAll('domain')) || []
    },
    selectedDomainType() {
      return this.selectedDomain.type
    },
    currentDomainType() {
      return this.$registry.get('domain', this.selectedDomainType)
    },
    options() {
      return this.domainTypes.map((domainType) => domainType.options).flat()
    },
  },
  watch: {
    selectedDomainType() {
      this.$refs?.domainForm?.reset()
    },
    createLoading(value) {
      this.$emit('loading', value)
    },
  },
  methods: {
    ...mapActions({
      actionCreateDomain: 'domain/create',
    }),
    async createDomain(data) {
      this.createLoading = true
      try {
        await this.actionCreateDomain({
          builderId: this.builder.id,
          ...data,
          type: this.selectedDomainType,
        })
        this.hideError()
        this.hideForm()
      } catch (error) {
        this.handleAnyError(error)
      } finally {
        // this.createLoading = false
        this.$emit('loading', false) // somehow the createLoading watcher is not triggered so I need to emit the event here as well
      }
    },
    handleAnyError(error) {
      if (
        !this.$refs.domainForm ||
        !this.$refs.domainForm.handleServerError ||
        !this.$refs.domainForm.handleServerError(error)
      ) {
        this.handleError(error)
      }
    },
    submitForm() {
      this.$refs.domainForm.submit()
    },
  },
}
</script>
