<template>
  <form @submit.prevent @keydown.enter.prevent>
    <FormGroup
      horizontal-narrow
      :label="$t('builderLoginPageForm.pageDropdownLabel')"
      required
      class="margin-top-4"
      :help-icon-tooltip="$t('builderLoginPageForm.pageDropdownDescription')"
    >
      <Dropdown
        v-model="values.login_page_id"
        :placeholder="$t('builderLoginPageForm.pageDropdownPlaceholder')"
      >
        <DropdownItem
          v-for="page in builderPages"
          :key="page.id"
          :name="page.name"
          :value="page.id"
        />
      </Dropdown>
    </FormGroup>
  </form>
</template>

<script>
import form from '@baserow/modules/core/mixins/form'

export default {
  name: 'BuilderLoginPageForm',
  mixins: [form],
  props: {
    builder: {
      type: Object,
      required: true,
    },
  },
  data() {
    return {
      values: { login_page_id: null },
      allowedValues: ['login_page_id'],
    }
  },
  computed: {
    builderPages() {
      return this.$store.getters['page/getVisiblePages'](this.builder)
    },
  },
  methods: {},
}
</script>
