import Vue from 'vue'
import Vuex from 'vuex'
import { setupVue } from '@baserow/modules/core/plugins/global'
import { setupVueForAB } from '@baserow/modules/builder/plugins/global'
import { vi, fail } from 'vitest'

const addVuex = (context) => {
  context.vuex = Vuex
  context.vue.use(context.vuex)
}
const addBus = (context) => {
  context.vue_bus = Vue
  const EventBus = new Vue()

  const EventBusPlugin = {
    install(v) {
      // Event bus
      v.prototype.$bus = EventBus
    },
  }
  context.vue.use(EventBusPlugin)
}
const addI18n = (context) => {
  context.vueTestUtils.config.mocks.$t = (key) => key
}
const compositeConfiguration = (...configs) => {
  return (context) => configs.forEach((config) => config(context))
}

export const bootstrapVueContext = (configureContext) => {
  configureContext =
    configureContext || compositeConfiguration(addVuex, addBus, addI18n)

  const context = {}
  const teardownVueContext = () => {
    vi.resetModules()
  }

  vi.isolateModules(() => {
    context.vueTestUtils = require('@vue/test-utils')
    context.vueTestUtils.config.stubs.nuxt = { template: '<div />' }
    context.vueTestUtils.config.stubs.NuxtChild = { template: '<div />' }
    context.vueTestUtils.config.stubs['nuxt-link'] = {
      template: '<a><slot /></a>',
    }
    context.vueTestUtils.config.stubs['no-ssr'] = {
      template: '<span><slot /></span>',
    }
    context.vue = context.vueTestUtils.createLocalVue()
    setupVue(context.vue)
    setupVueForAB(context.vue)

    vi.doMock('vue', () => context.vue)

    // Ensure any error logs cause the test to fail!
    vi.spyOn(console, 'error')
    console.error.mockImplementation(fail)

    configureContext && configureContext(context)
  })

  return {
    teardownVueContext,
    ...context,
  }
}
