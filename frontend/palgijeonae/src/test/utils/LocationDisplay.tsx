import { useLocation } from 'react-router-dom'

// 현재 주소를 화면에 노출해서, 화면 이동을 getCurrentLocation()(renderWithProviders)으로 검증할 수 있게 한다.
function LocationDisplay() {
  const location = useLocation()
  return <div data-testid="location">{`${location.pathname}${location.search}`}</div>
}

export default LocationDisplay
