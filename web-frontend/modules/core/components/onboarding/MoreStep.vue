<template>
  <div>
    <h1>{{ $t('moreStep.title') }}</h1>
    <FormGroup
      :label="$t('moreStep.how')"
      :error="v$.how.$error"
      required
      small-label
      class="margin-bottom-2"
    >
      <Dropdown
        v-model="how"
        :error="v$.how.$error"
        size="large"
        @hide="v$.how.$touch"
      >
        <DropdownItem
          v-for="howName in hows"
          :key="howName"
          :name="howName"
          :value="howName"
        ></DropdownItem>
      </Dropdown>
    </FormGroup>
    <FormGroup
      :label="$t('teamStep.description')"
      :error="v$.team.$error"
      required
      small-label
      class="margin-bottom-2"
    >
      <Dropdown
        v-model="team"
        :error="v$.team.$error"
        size="large"
        @hide="v$.team.$touch"
      >
        <DropdownItem
          v-for="teamName in teams"
          :key="teamName"
          :name="teamName"
          :value="teamName"
        ></DropdownItem>
      </Dropdown>
    </FormGroup>
    <FormGroup
      :label="$t('moreStep.country')"
      :error="v$.country.$error"
      required
      small-label
      class="margin-bottom-2"
    >
      <Dropdown
        v-model="country"
        :error="v$.country.$error"
        size="large"
        @hide="v$.country.$touch"
      >
        <DropdownItem
          v-for="countryName in countries"
          :key="countryName"
          :name="countryName"
          :value="countryName"
        ></DropdownItem>
      </Dropdown>
    </FormGroup>

    <Checkbox v-model="share">{{ $t('moreStep.share') }}</Checkbox>
  </div>
</template>

<script>
import { useVuelidate } from '@vuelidate/core'
import { required, helpers } from '@vuelidate/validators'
import { countryList } from '@baserow/modules/core/utils/countries'

export default {
  name: 'MoreStep',
  emits: ['update-data'],
  setup() {
    return { v$: useVuelidate({ $lazy: true }) }
  },
  data() {
    return {
      how: '',
      team: '',
      country: '',
      share: true,
    }
  },
  computed: {
    hows() {
      return [
        this.$t('moreStep.howSearchEngine'),
        this.$t('moreStep.howSocialMedia'),
        this.$t('moreStep.howOnlineAds'),
        this.$t('moreStep.howContent'),
        this.$t('moreStep.howReviewSite'),
        this.$t('moreStep.howFriend'),
        this.$t('moreStep.howColleague'),
        this.$t('moreStep.howEvent'),
        this.$t('moreStep.howSales'),
        this.$t('moreStep.howOther'),
      ]
    },
    countries() {
      return countryList
    },
    teams() {
      const teams = [
        this.$t('teamStep.marketingTeam'),
        this.$t('teamStep.productAndDesignTeam'),
        this.$t('teamStep.engineeringTeam'),
        this.$t('teamStep.operationsTeam'),
        this.$t('teamStep.itAndSupportTeam'),
        this.$t('teamStep.hrAndLegalTeam'),
        this.$t('teamStep.financeTeam'),
        this.$t('teamStep.creativeProductionTeam'),
        this.$t('teamStep.salesAndAccountManagementTeam'),
        this.$t('teamStep.customerServiceTeam'),
        this.$t('teamStep.manufacturingTeam'),
        this.$t('teamStep.otherPersonalTeam'),
      ]
      return teams
    },
  },

  watch: {
    how() {
      this.updateValue()
    },
    team() {
      this.updateValue()
    },
    country() {
      this.updateValue()
    },
  },
  mounted() {
    this.updateValue()
  },
  methods: {
    isValid() {
      return !this.v$.$invalid && this.v$.$dirty
    },
    updateValue() {
      this.$emit('update-data', {
        how: this.how,
        team: this.team,
        country: this.country,
        share: this.share,
      })
    },
  },
  validations() {
    return {
      how: {
        required: helpers.withMessage(this.$t('error.requiredField'), required),
      },
      team: {
        required: helpers.withMessage(this.$t('error.requiredField'), required),
      },
      country: {
        required: helpers.withMessage(this.$t('error.requiredField'), required),
      },
    }
  },
}
</script>
