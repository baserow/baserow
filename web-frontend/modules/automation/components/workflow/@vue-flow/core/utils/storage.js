import { toRefs } from '@vueuse/core'
import { computed, getCurrentInstance, reactive } from 'vue'
import { useActions, useGetters, useState } from '../store'

// Définition d'une version constante au lieu d'utiliser __VUE_FLOW_VERSION__
const VUE_FLOW_VERSION = '1.0.0'

/**
 * @deprecated will be removed in the next major and replaced with a ctx based solution similar to `<ReactFlowProvider>`
 *
 * Stores all existing VueFlow state instances
 */
export class Storage {
  constructor() {
    this.currentId = 0
    this.flows = new Map()
  }

  static getInstance() {
    // Adaptation pour Vue 2.7
    const instance = getCurrentInstance()

    // Dans Vue 2.7, on accède à $root via proxy
    const vueRoot = instance?.proxy?.$root

    // Vérification si l'instance existe déjà sur Vue ou en static
    const existingInstance =
      (vueRoot && vueRoot.$vueFlowStorage) || Storage.instance

    Storage.instance = existingInstance || new Storage()

    // Si nous avons un root, définir la propriété pour un accès global
    if (vueRoot) {
      vueRoot.$vueFlowStorage = Storage.instance
    }

    return Storage.instance
  }

  set(id, flow) {
    return this.flows.set(id, flow)
  }

  get(id) {
    return this.flows.get(id)
  }

  remove(id) {
    return this.flows.delete(id)
  }

  create(id, preloadedState) {
    // Initialisation de l'état
    const state = useState()
    const reactiveState = reactive(state)

    // Création des hooks
    const hooksOn = {}
    for (const [n, h] of Object.entries(reactiveState.hooks)) {
      const name = `on${n.charAt(0).toUpperCase() + n.slice(1)}`
      hooksOn[name] = h.on
    }

    // Création des émetteurs d'événements
    const emits = {}
    for (const [n, h] of Object.entries(reactiveState.hooks)) {
      emits[n] = h.trigger
    }

    // Lookups pour accès rapide aux noeuds et arêtes
    const nodeLookup = computed(() => {
      const nodesMap = new Map()
      for (const node of reactiveState.nodes) {
        nodesMap.set(node.id, node)
      }
      return nodesMap
    })

    const edgeLookup = computed(() => {
      const edgesMap = new Map()
      for (const edge of reactiveState.edges) {
        edgesMap.set(edge.id, edge)
      }
      return edgesMap
    })

    // Récupération des getters et actions
    const getters = useGetters(reactiveState, nodeLookup, edgeLookup)
    const actions = useActions(reactiveState, nodeLookup, edgeLookup)

    // Initialisation de l'état avec préchargement si fourni
    actions.setState({ ...reactiveState, ...preloadedState })

    // Création de l'objet flow
    const flow = {
      ...hooksOn,
      ...getters,
      ...actions,
      ...toRefs(reactiveState),
      nodeLookup,
      edgeLookup,
      emits,
      id,
      vueFlowVersion: VUE_FLOW_VERSION,
      $destroy: () => {
        this.remove(id)
      },
    }

    this.set(id, flow)

    return flow
  }

  getId() {
    return `vue-flow-${this.currentId++}`
  }
}
