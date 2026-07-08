// Weather → map visuals. The same WeatherState that slows the traffic
// (world/weather.py speed_factor) drives what you SEE, so physics and
// visuals always agree.
//
// Primary path: mapbox-gl ≥3.9 native GPU precipitation (map.setRain /
// map.setSnow — verified present in the pinned 3.17). Callers should fall
// back to the CSS overlay (WorldCommand renders .wc-rain) when
// `supportsNativePrecip(map)` is false.

const HEAVY_MM_H = 12

export function supportsNativePrecip(map) {
  return !!map && typeof map.setRain === 'function' && typeof map.setSnow === 'function'
}

/** Intensity bucket used by both native + CSS paths: none|light|heavy. */
export function rainBucket(weather) {
  if (!weather || weather.precip_mm_h <= 0 || weather.condition === 'snow') return 'none'
  return weather.precip_mm_h >= HEAVY_MM_H ? 'heavy' : 'light'
}

export function applyWeatherToMap(map, weather) {
  if (!map || !weather) return
  const precip = weather.precip_mm_h || 0
  const snowing = weather.condition === 'snow'
  const raining = precip > 0 && !snowing
  const strength = Math.min(precip / 15, 1)

  if (supportsNativePrecip(map)) {
    try {
      map.setRain(raining ? {
        density: 0.3 + strength * 0.7,
        intensity: 0.4 + strength * 0.6,
        color: '#a8adbc',
        opacity: 0.55,
        vignette: strength * 0.5,
        'vignette-color': '#464646',
        direction: [0, Math.min(50 + (weather.wind_kmh || 0), 85)],
        'droplet-size': [2.6, 18.2],
        'distortion-strength': 0.5,
        'center-thinning': 0.57,
      } : null)
      map.setSnow(snowing ? {
        density: 0.85,
        intensity: 0.6,
        color: '#ffffff',
        opacity: 0.9,
        vignette: 0.3,
        'vignette-color': '#ffffff',
        'center-thinning': 0.4,
        direction: [0, 50],
        'flake-size': 0.71,
      } : null)
    } catch { /* experimental API drift — CSS fallback still covers rain */ }
  }

  // Cloud cover + visibility → atmosphere. Standard style has its own sky;
  // fog densification reads as overcast without fighting the light preset.
  try {
    const cc = Math.min(Math.max((weather.cloud_cover_pct || 0) / 100, 0), 1)
    const visKm = Math.max((weather.visibility_m || 10000) / 1000, 0.3)
    map.setFog({
      range: [Math.min(visKm * 0.15, 2), Math.max(visKm * 1.2, 4)],
      'horizon-blend': 0.05 + cc * 0.25,
      color: cc > 0.6 ? '#9aa3ad' : '#ffffff',
      'high-color': cc > 0.6 ? '#6b7480' : '#245cdf',
      'star-intensity': 0,
    })
  } catch { /* fog is cosmetic */ }
}

/** Smog haze opacity from a region's annual PM2.5 baseline (0 → clear). */
export function hazeOpacity(aqiBaseline) {
  const pm25 = aqiBaseline?.annual_mean_pm25 || 0
  if (pm25 <= 25) return 0
  return Math.min((pm25 - 25) / 150, 0.38)
}
