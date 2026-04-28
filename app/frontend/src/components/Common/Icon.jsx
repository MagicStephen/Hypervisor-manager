import { FontAwesomeIcon } from '@fortawesome/react-fontawesome'
import {
  faHome,
  faUser,
  faCog,
  faServer,
  faChartLine,
  faComputer,
  faArrowUp,
  faCubes,
  faCube,
} from '@fortawesome/free-solid-svg-icons'

const icons = {
  home: faHome,
  user: faUser,
  settings: faCog,
  server: faServer,
  trendChart: faChartLine,
  rollUp: faArrowUp,

  cluster: faCubes,
  node: faCube,
  vm: faComputer
}

export default function Icon({ name, ...props }) {
  return <FontAwesomeIcon icon={icons[name]} {...props} />
}