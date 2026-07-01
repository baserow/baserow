<template>
  <li class="tree__item tree__item--loading">
    <div class="tree__action tree__action--disabled">
      <a class="tree__link">
        <i class="tree__icon" :class="jobIconClass"></i>
        <span class="tree__link-text">{{ jobSidebarText }}</span>
        <div class="tree__progress-percentage">
          {{ job.progress_percentage }} %
        </div>
      </a>
    </div>
  </li>
</template>

<script>
export default {
  name: 'SidebarApplicationPendingJob',
  props: {
    job: {
      type: Object,
      required: true,
    },
  },
  computed: {
    jobSidebarText() {
      return this.$registry.get('job', this.job.type).getSidebarText(this.job)
    },
    jobIconClass() {
      return this.$registry.get('job', this.job.type).getIconClass(this.job)
    },
  },
}
</script>
