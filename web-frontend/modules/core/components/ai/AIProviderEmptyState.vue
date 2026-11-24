<template>
  <section class="ai-provider-empty">
    <div class="ai-provider-empty__icon"><i class="iconoir-sparks" /></div>
    <div class="ai-provider-empty__content">
      <h2 class="ai-provider-empty__title">{{ title }}</h2>
      <p class="ai-provider-empty__description">{{ description }}</p>
    </div>
    <Button icon="iconoir-plus" :disabled="disabled" @click="emit('add')">
      {{ $t('aiProviderAdmin.addProvider') }}
    </Button>
  </section>
</template>

<script setup>
defineProps({
  title: { type: String, required: true },
  description: { type: String, required: true },
  disabled: { type: Boolean, default: false },
})

const emit = defineEmits(['add'])
</script>
