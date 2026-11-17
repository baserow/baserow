<template>
  <FormGroup :label="$t('teamMembersSummary.title')" small-label required>
    <div
      class="team-members-summary"
      :class="{ 'team-members-summary--empty': isEmpty }"
    >
      <template v-if="isEmpty">
        <span class="team-members-summary__names">
          {{ $t('teamMembersSummary.empty') }}
        </span>
      </template>
      <template v-else>
        <div class="team-members-summary__avatars">
          <component
            :is="getSubjectType(sample.subject_type).avatarComponent"
            v-for="(sample, index) in avatarSamples"
            :key="index"
            class="team-members-summary__avatar"
            size="medium"
            :subject="{ name: sample.subject_label }"
          />
        </div>
        <span class="team-members-summary__names" :title="names">
          {{ names }}
        </span>
      </template>
      <Button
        v-if="canManageMembers"
        type="secondary"
        button-type="button"
        :icon="isEmpty ? 'iconoir-plus' : 'iconoir-community'"
        @click="$emit('manage')"
      >
        {{
          isEmpty
            ? $t('teamMembersSummary.add')
            : $t('teamMembersSummary.manage')
        }}
      </Button>
    </div>
  </FormGroup>
</template>

<script>
// The number of avatars shown before the rest is left to the names.
const AVATAR_COUNT = 3

/**
 * Who is in a team, from the `subject_count` and `subject_sample` of the team,
 * with a button that emits `manage` to open its members.
 */
export default {
  name: 'TeamMembersSummary',
  props: {
    team: {
      type: Object,
      required: true,
    },
    canManageMembers: {
      type: Boolean,
      required: false,
      default: false,
    },
  },
  emits: ['manage'],
  computed: {
    samples() {
      return this.team.subject_sample || []
    },
    count() {
      return this.team.subject_count ?? this.samples.length
    },
    isEmpty() {
      return this.count === 0
    },
    avatarSamples() {
      return this.samples.slice(0, AVATAR_COUNT)
    },
    names() {
      const [first, second] = this.samples.map(
        ({ subject_label: label }) => label
      )
      if (this.count === 1) {
        return first
      }
      if (this.count === 2) {
        return this.$t('teamMembersSummary.twoNames', { first, second })
      }
      return this.$t('teamMembersSummary.moreNames', {
        first,
        second,
        count: this.count - 2,
      })
    },
  },
  methods: {
    getSubjectType(type) {
      return this.$registry.get('subject', type)
    },
  },
}
</script>
