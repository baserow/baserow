<template>
  <form @submit.prevent @keydown.enter.prevent>
    <FormGroup :label="$t('generalSettings.labelForm')" required>
      <ImageInput
        v-model="values.favicon_file"
        :default-image="defaultFavicon"
        :allowed-image-types="FAVICON_IMAGE_FILE_TYPES"
        :label-description="$t('generalSettings.labelDescription')"
        :label-button="$t('generalSettings.labelButton')"
      />
    </FormGroup>
    <FormGroup
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
import { FAVICON_IMAGE_FILE_TYPES } from '@baserow/modules/core/enums'
import DefaultFavicon from '@baserow/modules/core/static/img/favicon_192.png'

import form from '@baserow/modules/core/mixins/form'

export default {
  name: 'BuilderGeneralSettingsForm',
  mixins: [form],
  props: {
    builder: {
      type: Object,
      required: true,
    },
  },
  data() {
    return {
      values: { favicon_file: null, login_page_id: null },
      allowedValues: ['favicon_file', 'login_page_id'],
    }
  },
  computed: {
    defaultFavicon() {
      return DefaultFavicon
    },
    FAVICON_IMAGE_FILE_TYPES() {
      return FAVICON_IMAGE_FILE_TYPES
    },
    builderPages() {
      return this.$store.getters['page/getVisiblePages'](this.builder)
    },
  },
}
</script>
