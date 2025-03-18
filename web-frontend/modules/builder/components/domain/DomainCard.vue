<template>
  <Expandable card :default-expanded="isOnlyDomain">
    <template #header="{ toggle, expanded }">
      <div class="domain-card__header">
        <div>
          <div class="margin-bottom-1 domain-card__name">
            {{ domain.domain_name }}
          </div>
          <a class="domain-card__detail-button-link" @click="toggle">
            {{ $t('domainCard.detailLabel')
            }}<i
              class="domain-card__detail-button-icon"
              :class="
                expanded ? 'iconoir-nav-arrow-down' : 'iconoir-nav-arrow-right'
              "
            />
          </a>
        </div>
        <div>
          <div class="domain-card__domain-type margin-bottom-1">
            {{ domainType.name }}
          </div>
          <LastPublishedDomainDate
            :domain="domain"
            class="domain-card__last-update"
          />
        </div>
      </div>
      <Alert
        v-if="!domain.last_published"
        type="warning"
        class="margin-bottom-0"
      >
        <p>{{ $t('domainCard.unpublishedDomainWarning') }}</p>
      </Alert>
    </template>
    <component
      :is="domainType.detailsComponent"
      :domain="domain"
      @delete="$emit('delete')"
    />
  </Expandable>
</template>

<script>
import DnsStatus from '@baserow/modules/builder/components/domain/DnsStatus'
import LastPublishedDomainDate from '@baserow/modules/builder/components/domain/LastPublishedDomainDate'

export default {
  name: 'DomainCard',
  components: { DnsStatus, LastPublishedDomainDate },
  props: {
    domain: {
      type: Object,
      required: true,
    },
    isOnlyDomain: {
      type: Boolean,
      required: false,
      default: false,
    },
  },
  computed: {
    domainType() {
      return this.$registry.get('domain', this.domain.type)
    },
  },
}
</script>
