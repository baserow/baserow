<template>
  <form @submit.prevent @keydown.enter.prevent>
    <CustomStyleButton
      v-model="values.styles"
      style-key="image"
      :config-block-types="['image']"
      :theme="builder.theme"
    />
    <FormGroup
      class="margin-bottom-2"
      required
      small-label
      :label="$t('imageElementForm.fileLabel')"
    >
      <RadioGroup
        v-model="values.image_source_type"
        :options="imageSourceTypeOptions"
        type="button"
      >
      </RadioGroup>
    </FormGroup>
    <FormGroup
      v-if="values.image_source_type === IMAGE_SOURCE_TYPES.UPLOAD"
      class="margin-bottom-2"
    >
      <Button
        v-if="values.image_file === null"
        type="upload"
        @click="openFileUploadModal"
      >
        {{ $t('imageElementForm.uploadFileButton') }}
      </Button>

      <Thumbnail
        v-else
        removable
        :src="values.image_file.url"
        @remove="values.image_file = null"
      />
      <UserFilesModal
        ref="userFilesModal"
        :multiple-files="false"
        :file-types-acceptable="IMAGE_FILE_TYPES"
        @uploaded="fileUploaded"
      />
    </FormGroup>
    <FormGroup
      v-if="values.image_source_type === IMAGE_SOURCE_TYPES.URL"
      class="margin-bottom-2"
      :helper-text="$t('imageElementForm.urlWarning')"
      small-label
    >
      <InjectedFormulaInput
        v-model="values.image_url"
        :placeholder="$t('elementForms.urlInputPlaceholder')"
      />
    </FormGroup>
    <FormGroup
      class="margin-bottom-2"
      :label="$t('imageElementForm.altTextTitle')"
      :helper-text="$t('imageElementForm.altTextDescription')"
      small-label
      required
    >
      <InjectedFormulaInput
        v-model="values.alt_text"
        :placeholder="$t('elementForms.textInputPlaceholder')"
      />
    </FormGroup>
  </form>
</template>

<script>
import { IMAGE_SOURCE_TYPES } from '@baserow/modules/builder/enums'
import { IMAGE_FILE_TYPES } from '@baserow/modules/core/enums'
import UserFilesModal from '@baserow/modules/core/components/files/UserFilesModal'
import { UploadFileUserFileUploadType } from '@baserow/modules/core/userFileUploadTypes'
import InjectedFormulaInput from '@baserow/modules/core/components/formula/InjectedFormulaInput'
import elementForm from '@baserow/modules/builder/mixins/elementForm'
import CustomStyleButton from '@baserow/modules/builder/components/elements/components/forms/style/CustomStyleButton'

export default {
  name: 'ImageElementForm',
  components: {
    InjectedFormulaInput,
    CustomStyleButton,
    UserFilesModal,
  },
  mixins: [elementForm],
  data() {
    return {
      allowedValues: [
        'image_source_type',
        'image_file',
        'image_url',
        'alt_text',
        'styles',
      ],
      values: {
        image_source_type: IMAGE_SOURCE_TYPES.UPLOAD,
        image_file: null,
        image_url: {},
        alt_text: {},
        styles: {},
      },
    }
  },
  computed: {
    IMAGE_SOURCE_TYPES() {
      return IMAGE_SOURCE_TYPES
    },
    imageSourceTypeOptions() {
      return [
        {
          label: this.$t('imageElementForm.fileSourceTypeUpload'),
          value: IMAGE_SOURCE_TYPES.UPLOAD,
        },
        {
          label: this.$t('imageElementForm.fileSourceTypeURL'),
          value: IMAGE_SOURCE_TYPES.URL,
        },
      ]
    },
    IMAGE_FILE_TYPES() {
      return IMAGE_FILE_TYPES
    },
  },
  methods: {
    openFileUploadModal() {
      this.$refs.userFilesModal.show(UploadFileUserFileUploadType.getType())
    },
    fileUploaded([file]) {
      this.values.image_file = file
      this.$refs.userFilesModal.hide()
    },
  },
}
</script>
