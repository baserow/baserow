export const initialNodes = [
  {
    id: '1',
    label: 'Node',
    type: 'baserow-node',
    position: { x: 0, y: 0 },
  },
  {
    id: '2',
    label: '',
    position: { x: 190, y: 92 },
    type: 'add-button',
  },
  {
    id: '3',
    label: 'Node',
    position: { x: 0, y: 144 },
    type: 'baserow-node',
  },
  {
    id: '4',
    label: '',
    position: { x: 190, y: 236 },
    type: 'add-button',
  },
  {
    id: '5',
    label: 'Node',
    position: { x: 0, y: 288 },
    type: 'baserow-node',
  },
  {
    id: '6',
    label: '',
    position: { x: 190, y: 380 },
    type: 'add-button',
  },
]

export const initialEdges = [
  {
    id: 'e1-2',
    source: '1',
    target: '2',
    type: 'baserow-edge',
  },
  {
    id: 'e2-3',
    source: '2',
    target: '3',
    type: 'baserow-edge',
  },
  {
    id: 'e3-4',
    source: '3',
    target: '4',
    type: 'baserow-edge',
  },
  {
    id: 'e4-5',
    source: '4',
    target: '5',
    type: 'baserow-edge',
  },
  {
    id: 'e5-6',
    source: '5',
    target: '6',
    type: 'baserow-edge',
  },
]
