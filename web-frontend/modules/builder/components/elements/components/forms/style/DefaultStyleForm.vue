<template>
  <form @submit.prevent>
    <FormSection v-if="isStyleAllowed('style_background')">
      <FormGroup
        v-if="isStyleAllowed('style_background')"
        :label="$t('defaultStyleForm.backgroundLabel')"
        small-label
        required
        class="margin-bottom-2"
      >
        <RadioGroup
          v-model="values.style_background"
          type="button"
          :options="backgroundTypes"
        />
      </FormGroup>
      <FormGroup
        v-if="
          values.style_background === BACKGROUND_TYPES.COLOR &&
          isStyleAllowed('style_background_color')
        "
        class="margin-bottom-2"
        small-label
        required
      >
        <ColorInput
          v-model="values.style_background_color"
          small
          :color-variables="colorVariables"
        />
      </FormGroup>
      <FormGroup
        v-if="isStyleAllowed('style_background_file')"
        :label="$t('defaultStyleForm.backgroundImage')"
        small-label
        required
        class="margin-top-2"
      >
        <ImageInput v-model="values.style_background_file" />
      </FormGroup>
      <FormGroup
        v-if="
          isStyleAllowed('style_background_mode') &&
          values.style_background_file
        "
        :label="$t('defaultStyleForm.backgroundImageMode')"
        small-label
        required
      >
        <RadioGroup
          v-model="values.style_background_mode"
          type="button"
          :options="backgroundModes"
        />
      </FormGroup>
    </FormSection>
    <FormSection v-if="isStyleAllowed('style_width')">
      <FormGroup
        :label="$t('defaultStyleForm.widthLabel')"
        small-label
        required
        class="margin-bottom-2"
      >
        <Dropdown v-model="values.style_width">
          <DropdownItem
            v-for="type in Object.values(WIDTH_TYPES)"
            :key="type.value"
            :name="$t(type.name)"
            :value="type.value"
          >
          </DropdownItem>
        </Dropdown>
      </FormGroup>
    </FormSection>
    <StyleBoxForm
      v-for="{ name, label } in borders"
      :key="name"
      v-model="boxStyles[name]"
      :title="label"
      :padding-is-allowed="isStyleAllowed(`style_padding_${name}`)"
      :border-is-allowed="isStyleAllowed(`style_border_${name}`)"
      :margin-is-allowed="isStyleAllowed(`style_margin_${name}`)"
    />
  </form>
</template>

<script>
import StyleBoxForm from '@baserow/modules/builder/components/elements/components/forms/style/StyleBoxForm'
import styleForm from '@baserow/modules/builder/mixins/styleForm'
import {
  BACKGROUND_TYPES,
  WIDTH_TYPES,
  BACKGROUND_MODES,
} from '@baserow/modules/builder/enums'
import { IMAGE_FILE_TYPES } from '@baserow/modules/core/enums'

export default {
  components: { StyleBoxForm },
  mixins: [styleForm],
  computed: {
    BACKGROUND_TYPES: () => BACKGROUND_TYPES,
    WIDTH_TYPES: () => WIDTH_TYPES,
    backgroundTypes() {
      return [
        {
          label: this.$t('backgroundTypes.none'),
          value: BACKGROUND_TYPES.NONE,
        },
        {
          label: this.$t('backgroundTypes.color'),
          value: BACKGROUND_TYPES.COLOR,
        },
      ]
    },
    backgroundModes() {
      return [
        {
          label: this.$t('backgroundModes.fill'),
          value: BACKGROUND_MODES.FILL,
        },
        {
          label: this.$t('backgroundModes.fit'),
          value: BACKGROUND_MODES.FIT,
        },
        {
          label: this.$t('backgroundModes.tile'),
          value: BACKGROUND_MODES.TILE,
        },
      ]
    },
    IMAGE_FILE_TYPES() {
      return IMAGE_FILE_TYPES
    },
  },
}
</script>
