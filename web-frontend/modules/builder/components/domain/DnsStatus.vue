<template>
  <div>
    <div class="margin-bottom-1">
      {{ $t('dnsStatus.description') }}
    </div>
    <table class="dns-status__table">
      <thead class="dns-status__table-head">
        <tr>
          <th class="dns-status__table-cell">
            {{ $t('dnsStatus.typeHeader') }}
          </th>
          <th class="dns-status__table-cell">
            {{ $t('dnsStatus.hostHeader') }}
          </th>
          <th class="dns-status__table-cell">
            {{ $t('dnsStatus.valueHeader') }}
          </th>
          <th class="dns-status__table-cell" />
        </tr>
      </thead>
      <tbody>
        <tr v-if="isRootDomain" class="dns-status__table-row">
          <td class="dns-status__table-cell">ALIAS</td>
          <td class="dns-status__table-cell">{{ domain.domain_name }}</td>
          <td class="dns-status__table-cell">{{ webFrontendHostname }}.</td>
          <td class="dns-status__table-cell">
            <!--
            <i class="iconoir-warning-triangle color--deep-dark-orange" />
            -->
          </td>
        </tr>
        <tr v-else class="dns-status__table-row">
          <td class="dns-status__table-cell">CNAME</td>
          <td class="dns-status__table-cell">{{ domain.domain_name }}</td>
          <td class="dns-status__table-cell">{{ webFrontendHostname }}</td>
          <td class="dns-status__table-cell">
            <!--
            <i class="iconoir-warning-triangle color--deep-dark-orange" />
            -->
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<script>
export default {
  name: 'DnsStatus',
  props: {
    domain: {
      type: Object,
      required: true,
    },
  },
  computed: {
    isRootDomain() {
      return this.domain.domain_name.split('.').length === 2
    },
    webFrontendHostname() {
      const url = new URL(this.$config.public.publicWebFrontendUrl)
      return url.hostname
    },
  },
}
</script>
