<template>
  <div>
    <h1>{{ $t('databaseScratchTrackStep.title') }}</h1>
    <p>{{ $t('databaseScratchTrackStep.description') }}</p>
    <div class="flex flex-wrap margin-bottom-3" style="--gap: 8px">
      <Chips
        v-for="whatItem in Object.keys(whatItems)"
        :key="whatItem"
        :active="what === whatItem"
        @click="select(whatItem)"
        >{{ whatItem }}</Chips
      >
      <Chips
        :active="what === 'own'"
        icon="iconoir-plus"
        @click="select('own')"
        >{{ $t('databaseScratchTrackStep.addYourOwn') }}</Chips
      >
    </div>
    <FormGroup
      v-if="what === 'own'"
      :error="v$.tableName.$error"
      :label="$t('databaseScratchTrackStep.tableName')"
      required
      small-label
      class="margin-bottom-2"
    >
      <FormInput
        v-model="tableName"
        :placeholder="$t('databaseScratchTrackStep.tableName') + '...'"
        size="large"
        :error="v$.tableName.$error"
        @input="updateValue"
        @blur="v$.tableName.$touch"
      />
      <template #error>
        {{ v$.tableName.$errors[0].$message }}
      </template>
    </FormGroup>

    <FormGroup
      v-for="(row, index) in [0, 1, 2]"
      v-show="what !== ''"
      :key="index"
      class="margin-bottom-2"
      :error="v$['row' + index]?.$error"
      small-label
    >
      <template v-if="index === 0" #label>
        {{ $t('databaseScratchTrackStep.thisIncludes') }}</template
      >
      <FormInput
        v-model="v$['row' + index].$model"
        :placeholder="$t('databaseScratchTrackStep.rowName') + '...'"
        size="large"
        :error="v$['row' + index]?.$error"
        @input="updateValue"
        @blur="v$['row' + index].$touch"
      />
      <template #error>
        {{ v$['row' + index].$errors[0].$message }}
      </template>
    </FormGroup>
  </div>
</template>

<script>
import { useVuelidate } from '@vuelidate/core'
import { required, helpers } from '@vuelidate/validators'

export default {
  name: 'DatabaseScratchTrackStep',
  setup() {
    return { v$: useVuelidate({ $lazy: true }) }
  },
  data() {
    return {
      what: '',
      tableName: '',
      own: false,
      row0: '',
      row1: '',
      row2: '',
    }
  },
  computed: {
    whatItems() {
      const items = {
        [this.$t('databaseScratchTrackStep.projects')]: [
          this.$t('databaseScratchTrackStep.productsRow1'),
          this.$t('databaseScratchTrackStep.productsRow2'),
          this.$t('databaseScratchTrackStep.productsRow3'),
        ],
        [this.$t('databaseScratchTrackStep.teams')]: [
          this.$t('databaseScratchTrackStep.teamsRow1'),
          this.$t('databaseScratchTrackStep.teamsRow2'),
          this.$t('databaseScratchTrackStep.teamsRow3'),
        ],
        [this.$t('databaseScratchTrackStep.tasks')]: [
          this.$t('databaseScratchTrackStep.tasksRow1'),
          this.$t('databaseScratchTrackStep.tasksRow2'),
          this.$t('databaseScratchTrackStep.tasksRow3'),
        ],
        [this.$t('databaseScratchTrackStep.campaigns')]: [
          this.$t('databaseScratchTrackStep.campaignsRow1'),
          this.$t('databaseScratchTrackStep.campaignsRow2'),
          this.$t('databaseScratchTrackStep.campaignsRow3'),
        ],
      }
      return items
    },
  },
  mounted() {
    this.updateValue()
  },
  methods: {
    isValid() {
      return !!this.what && !this.v$.$invalid && this.v$.$dirty
    },
    select(value) {
      if (
        this.what !== value &&
        Object.prototype.hasOwnProperty.call(this.whatItems, value)
      ) {
        this.v$.row0.$model = this.whatItems[value][0]
        this.v$.row1.$model = this.whatItems[value][1]
        this.v$.row2.$model = this.whatItems[value][2]
      }

      // this.v$.row0?.$touch()
      this.what = value
      this.updateValue()
    },
    updateValue() {
      const tableName = this.what === 'own' ? this.tableName : this.what
      const rows = [this.row0, this.row1, this.row2]
      this.$emit('update-data', { tableName, rows })
    },
  },
  validations() {
    const rules = {}

    rules.row0 = {
      required: helpers.withMessage(this.$t('error.requiredField'), required),
    }
    rules.row1 = {
      required: helpers.withMessage(this.$t('error.requiredField'), required),
    }
    rules.row2 = {
      required: helpers.withMessage(this.$t('error.requiredField'), required),
    }

    if (this.what === 'own') {
      rules.tableName = {
        required: helpers.withMessage(this.$t('error.requiredField'), required),
      }
    }

    return rules
  },
}
</script>
