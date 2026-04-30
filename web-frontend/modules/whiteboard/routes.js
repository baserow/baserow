import path from 'path'

export const routes = [
  {
    name: 'whiteboard-application',
    path: '/whiteboard/:whiteboardId',
    file: path.resolve(__dirname, 'pages/whiteboard.vue'),
  },
]
