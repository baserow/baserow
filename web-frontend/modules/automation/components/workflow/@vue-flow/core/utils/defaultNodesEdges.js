import DefaultNode from '../components/Nodes/DefaultNode'
import OutputNode from '../components/Nodes/OutputNode'
import InputNode from '../components/Nodes/InputNode'
import StraightEdge from '../components/Edges/StraightEdge'
import StepEdge from '../components/Edges/StepEdge'
import BezierEdge from '../components/Edges/BezierEdge'
import SimpleBezierEdge from '../components/Edges/SimpleBezierEdge'
import SmoothStepEdge from '../components/Edges/SmoothStepEdge'

export const defaultNodeTypes = {
  input: InputNode,
  default: DefaultNode,
  output: OutputNode,
}

export const defaultEdgeTypes = {
  default: BezierEdge,
  straight: StraightEdge,
  step: StepEdge,
  smoothstep: SmoothStepEdge,
  simplebezier: SimpleBezierEdge,
}
