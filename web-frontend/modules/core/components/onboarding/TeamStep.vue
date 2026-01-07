<template>
  <div>
    <h1>{{ $t('teamStep.title') }}</h1>
    <p>{{ $t('teamStep.description') }}</p>
    <div class="flex flex-wrap" style="--gap: 8px">
      <Chips
        v-for="t in teams"
        :key="t"
        :active="team === t"
        @click="select(t)"
        >{{ t }}</Chips
      >
    </div>
  </div>
</template>

<script>
export default {
  name: 'TeamStep',
  emits: ['update-data'],
  data() {
    return {
      team: '',
    }
  },
  computed: {
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
  methods: {
    isValid() {
      return !!this.team
    },
    select(team) {
      this.team = team
      this.$emit('update-data', { team })
    },
  },
}
</script>
