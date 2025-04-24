export const initialNodes = [
  {
    id: '1',
    label: 'Baserow custom node',
    type: 'baserow',
    position: { x: 0, y: 0 },
  },
  {
    id: '2',
    label: 'Baserow custom node',
    position: { x: 0, y: 100 },
    type: 'baserow',
  },
  {
    id: '3',
    label: 'Baserow custom node',
    position: { x: 0, y: 200 },
    type: 'baserow',
  },
  {
    id: '4',
    label: 'Baserow custom node',
    position: { x: 0, y: 300 },
    type: 'baserow',
  },
  {
    id: '5',
    label: 'Baserow custom node',
    position: { x: 0, y: 400 },
    type: 'baserow',
  },
  {
    id: '6',
    label: 'Baserow custom node',
    position: { x: 0, y: 500 },
    type: 'baserow',
  },
  {
    id: '7',
    label: 'Baserow custom node',
    position: { x: 0, y: 600 },
    type: 'baserow',
  },
  {
    id: '8',
    label: 'Baserow custom node',
    position: { x: 0, y: 700 },
    type: 'baserow',
  },
  {
    id: '9',
    label: 'Baserow custom node',
    position: { x: 0, y: 800 },
    type: 'baserow',
  },
  {
    id: '10',
    label: 'Baserow custom node',
    position: { x: 0, y: 900 },
    type: 'baserow',
  },
  {
    id: '11',
    label: 'Baserow custom node',
    position: { x: 0, y: 1000 },
    type: 'baserow',
  },
]

export const initialEdges = [
  {
    id: 'e1-2',
    source: '1',
    target: '2',
  },
  {
    id: 'e2-3',
    source: '2',
    target: '3',
    label: 'Node 2',
    style: { stroke: 'orange' },
    labelBgStyle: { fill: 'orange' },
  },
  {
    id: 'e3-4',
    source: '3',
    target: '4',
    label: 'smoothstep-edge',
  },
]
