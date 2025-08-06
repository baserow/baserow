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
          v-model="v$.values.style_background.$model"
          type="button"
          :options="backgroundTypes"
        />
      </FormGroup>
      <FormGroup
        v-if="
          v$.values.style_background.$model === BACKGROUND_TYPES.COLOR &&
          isStyleAllowed('style_background_color')
        "
        class="margin-bottom-2"
        small-label
        required
      >
        <ColorInput
          v-model="v$.values.style_background_color.$model"
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
        <ImageInput v-model="v$.values.style_background_file.$model" />
      </FormGroup>
      <FormGroup
        v-if="
          isStyleAllowed('style_background_mode') &&
          v$.values.style_background_file.$model
        "
        :label="$t('defaultStyleForm.backgroundImageMode')"
        small-label
        required
      >
        <RadioGroup
          v-model="v$.values.style_background_mode.$model"
          type="button"
          :options="backgroundModes"
        />
      </FormGroup>
    </FormSection>
    <FormSection>
      <FormGroup
        :label="$t('defaultStyleForm.cssClasses')"
        small-label
        required
        class="margin-bottom-2"
        :helper-text="$t('defaultStyleForm.cssClassesHelp')"
      >
        <FormInput
          v-model="v$.values.css_classes.$model"
          :placeholder="$t('defaultStyleForm.cssClassesPlaceholder')"
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
        <Dropdown v-model="v$.values.style_width.$model">
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
    <FormSection v-if="isStyleAllowed('style_width_child')">
      <FormGroup
        :label="$t('defaultStyleForm.widthLabel')"
        small-label
        required
        class="margin-bottom-2"
      >
        <Dropdown v-model="values.style_width_child">
          <DropdownItem
            v-for="type in Object.values(CHILD_WIDTH_TYPES)"
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

    <RadiusForm
      v-model="radiusStyles"
      :background-radius-is-allowed="isStyleAllowed('style_background_radius')"
      :border-radius-is-allowed="isStyleAllowed('style_border_radius')"
    />
  </form>
</template>

<script>
import { useVuelidate } from '@vuelidate/core'
import StyleBoxForm from '@baserow/modules/builder/components/elements/components/forms/style/StyleBoxForm'
import RadiusForm from '@baserow/modules/builder/components/elements/components/forms/style/RadiusForm'
import styleForm from '@baserow/modules/builder/mixins/styleForm'
import {
  BACKGROUND_TYPES,
  WIDTH_TYPES,
  CHILD_WIDTH_TYPES,
  BACKGROUND_MODES,
} from '@baserow/modules/builder/enums'
import { IMAGE_FILE_TYPES } from '@baserow/modules/core/enums'

export default {
  components: { StyleBoxForm, RadiusForm },
  mixins: [styleForm],
  setup() {
    return { v$: useVuelidate() }
  },

  data() {
    return {
      values: {
        css_classes: '',
        style_background: BACKGROUND_TYPES.NONE,
        style_background_color: '',
        style_background_file: null,
        style_background_mode: BACKGROUND_MODES.FILL,
        style_width: WIDTH_TYPES.AUTO,
        style_margin_top: 0,
        style_border_top_color: '',
        style_border_top_size: 0,
        style_padding_top: 0,
        style_margin_left: 0,
        style_border_left_color: '',
        style_border_left_size: 0,
        style_padding_left: 0,
        style_margin_bottom: 0,
        style_border_bottom_color: '',
        style_border_bottom_size: 0,
        style_padding_bottom: 0,
        style_margin_right: 0,
        style_border_right_color: '',
        style_border_right_size: 0,
        style_padding_right: 0,
      },
    }
  },
  computed: {
    BACKGROUND_TYPES: () => BACKGROUND_TYPES,
    WIDTH_TYPES: () => WIDTH_TYPES,
    CHILD_WIDTH_TYPES: () => CHILD_WIDTH_TYPES,
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
  validations() {
    return {
      values: {
        css_classes: {},
        style_background: {},
        style_background_color: {},
        style_background_file: {},
        style_background_mode: {},
        style_width: {},
        style_border_top_color: {},
        style_border_top_size: {},
        style_padding_top: {},
        style_margin_left: {},
        style_border_left_color: {},
        style_border_left_size: {},
        style_padding_left: {},
        style_margin_bottom: {},
        style_border_bottom_color: {},
        style_border_bottom_size: {},
        style_padding_bottom: {},
        style_margin_right: {},
        style_border_right_color: {},
        style_border_right_size: {},
        style_padding_right: {},
      },
    }
  },
}
</script>
