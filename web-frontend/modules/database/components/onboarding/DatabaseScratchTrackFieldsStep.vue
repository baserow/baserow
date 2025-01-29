<template>
  <div>
    <h1>{{ $t('databaseScratchTrackFieldsStep.title') }}</h1>
    <p>
      {{
        $t('databaseScratchTrackFieldsStep.description', {
          selectedFieldsLimitCount,
        })
      }}
    </p>
    <div class="flex flex-wrap margin-bottom-3" style="--gap: 8px">
      <Chips
        v-for="(whatItem, whatKey) in whatItems"
        :key="whatKey"
        :active="isChipActive(whatKey)"
        :disabled="isChipDisabled(whatKey)"
        :icon="whatItem.icon"
        @click="toggleSelection(whatKey)"
        >{{ whatItem.name }}
      </Chips>
      <Chips
        icon="iconoir-plus"
        :disabled="isChipDisabled('own')"
        :active="isChipActive('own')"
        @click="toggleSelection('own')"
      >
        {{ $t('databaseScratchTrackStep.addYourOwn') }}
      </Chips>
    </div>

    <FormGroup
      v-if="isChipActive('own')"
      required
      small-label
      class="margin-bottom-2 onboarding__form-group"
    >
      <div class="onboarding__form-group-row">
        <div class="onboarding__form-group-column">
          <div class="onboarding__form-group-label">
            {{ $t('databaseScratchTrackFieldsStep.fieldType') }}
          </div>
          <Dropdown v-model="ownField" size="large" :show-search="false">
            <DropdownItem
              v-for="field in ownFields"
              :key="field.props.type"
              :name="field.name"
              :value="field"
              :icon="field.icon"
            >
            </DropdownItem>
          </Dropdown>
        </div>
        <div class="onboarding__form-group-column">
          <div class="onboarding__form-group-label">
            {{ $t('databaseScratchTrackFieldsStep.fieldName') }}
          </div>

          <FormInput
            v-model="ownField.props.name"
            :placeholder="$t('databaseScratchTrackFieldsStep.fieldName')"
            size="large"
            :error="v$.ownField.props.name.$error"
            @blur="v$.ownField.props.name.$touch"
          />
          <p
            v-if="v$.ownField.props.name.$error"
            class="control__messages--error"
          >
            {{ v$.ownField.props.name.$errors[0].$message }}
          </p>
        </div>
      </div>
    </FormGroup>
  </div>
</template>

<script>
import { useVuelidate } from '@vuelidate/core'
import { required, helpers } from '@vuelidate/validators'
import { DatabaseScratchTrackOnboardingType } from '@baserow/modules/database/onboardingTypes'

export default {
  name: 'DatabaseScratchTrackFieldsStep',
  props: {
    data: {
      type: Object,
      required: true,
    },
  },
  setup() {
    return { v$: useVuelidate({ $lazy: true }) }
  },
  data() {
    return {
      what: '',
      selectedFieldsLimitCount: 4,
      selectedFieldsCount: 0,
      selectedFields: {},
      ownField: {
        props: {
          name: '',
        },
      },
      isOwnFieldValidationEnabled: false,
      whatItems: [],
      ownFields: [],
    }
  },
  watch: {
    ownField: {
      handler(field) {
        this.selectedFields.own = field
        this.updateValue()
      },
      deep: true,
    },
  },
  mounted() {
    this.what =
      this.data[
        DatabaseScratchTrackOnboardingType.getType()
      ].tableName.toLowerCase()
    let onboardingTrackFieldsType

    try {
      onboardingTrackFieldsType = this.$registry.get(
        'onboardingTrackFields',
        `database_scratch_track_fields_${this.what}`
      )
    } catch {
      onboardingTrackFieldsType = this.$registry.get(
        'onboardingTrackFields',
        `database_scratch_track_fields_custom`
      )
    }
    this.whatItems = onboardingTrackFieldsType.getFields()
    this.ownFields = onboardingTrackFieldsType.getOwnFields()
    this.updateValue()
  },
  methods: {
    isChipDisabled(name) {
      return (
        this.selectedFieldsCount >= this.selectedFieldsLimitCount &&
        !Object.keys(this.selectedFields).includes(name)
      )
    },
    isChipActive(name) {
      const isActive = Object.keys(this.selectedFields).includes(name)
      if (name === 'own') {
        this.isOwnFieldValidationEnabled = isActive
      }
      return isActive
    },
    isValid() {
      if (this.selectedFieldsCount && !this.isChipActive('own')) return true
      else return !this.v$.$invalid && this.v$.$dirty
    },
    toggleSelection(value) {
      const isAlreadySelected = this.isChipActive(value)
      if (
        this.selectedFieldsCount >= this.selectedFieldsLimitCount &&
        !isAlreadySelected
      ) {
        return
      }

      if (isAlreadySelected) {
        this.selectedFieldsCount--
        delete this.selectedFields[value]
      } else {
        this.selectedFieldsCount++
        if (value === 'own') {
          // preselect first field if nothing was selected
          if (!this.ownField.props.name) {
            this.ownField = this.ownFields[0]
          }
          this.selectedFields.own = this.ownField
          this.v$.ownField.props.name.$touch()
        } else {
          const selectedItem = this.whatItems[value]
          if (this.isNameUsed(selectedItem.props.name)) {
            const useCount = this.useCount(selectedItem.props.name)
            selectedItem.props.name = `${selectedItem.props.name} ${
              useCount + 1
            }`
          } else {
            selectedItem.props.name = selectedItem.name
          }

          this.selectedFields[value] = selectedItem
        }
      }
      this.forceValidation(value)
      this.updateValue()
    },
    updateValue() {
      const fields = this.selectedFields
      this.$emit('update-data', { fields })
    },
    getSelectedFieldNames(excludeField) {
      return Object.entries(this.selectedFields)
        .filter(([key, value]) => key !== excludeField)
        .map(([key, value]) => value.props.name)
    },
    useCount(value, excludeField) {
      return this.getSelectedFieldNames(excludeField).filter(
        (name) => name === value
      ).length
    },
    isNameUsed(value, excludeField) {
      const selectedFieldNames = this.getSelectedFieldNames(excludeField)
      return selectedFieldNames && selectedFieldNames.includes(value)
    },
    forceValidation(value) {
      // This is needed because we need to trigger validation without
      // changing the value (by clicking on chips). Vuelidate
      // doesn't trigger validation if the value doesn't change.
      // We want only to trigger validation if own field is selected
      if (value !== 'own' && this.isChipActive('own')) {
        const tmp = this.v$.ownField.props.name.$model
        this.v$.ownField.props.name.$model = ''
        this.v$.ownField.props.name.$model = tmp
        this.v$.ownField.props.name.$touch()
      }
    },
  },
  validations() {
    const rules = {}

    rules.ownField = {
      props: {
        name: {
          required: helpers.withMessage(
            this.$t('error.requiredField'),
            required
          ),
          uniqueNameValidator: helpers.withMessage(
            this.$t('error.alreadyInUse'),
            (value) => {
              return !this.isNameUsed(value, 'own')
            }
          ),
        },
      },
    }

    return rules
  },
}
</script>
