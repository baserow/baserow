<template>
  <div>
    <Button v-if="!showCreationForm" @click="handleAddDomainBtn">
      {{ $t('domainSettings.addDomain') }}
    </Button>

    <template v-else>
      <Button type="secondary" @click="handleCancelBtn">
        {{ $t('action.cancel') }}
      </Button>

      <Button
        :loading="loading"
        :disabled="loading"
        @click="$emit('create-domain')"
      >
        {{ $t('action.create') }}
      </Button>
    </template>
  </div>
</template>

<script>
export default {
  name: 'DomainsSettingsFooter',
  props: {
    loading: {
      type: Boolean,
      default: false,
    },
  },
  data() {
    return {
      showCreationForm: false,
    }
  },
  methods: {
    handleAddDomainBtn() {
      this.showCreationForm = true
      this.$emit('show-domains-form')
    },
    reset() {
      this.showCreationForm = false
    },
    handleCancelBtn() {
      this.showCreationForm = false
      this.$emit('hide-domains-form')
    },
  },
}
</script>
