import { useEffect, useMemo, useRef } from 'react'
import { DEFAULT_MAP_PADDING, DEFAULT_MAP_STYLE } from '../../lib/maps/maplibre-config'
import { getImageryImageCoordinates, getImageryOverlayUrl } from '../../lib/api'
import type { ImageryScene } from '../../lib/api/types'
import { getZoneById, zoneMap } from '../../features/dashboard/dashboardData'

interface ZoneMapProps {
  selectedZoneId: string
  onSelect: (zoneId: string) => void
  imagery: ImageryScene | null
  imageryMode: 'rgb' | 'ndvi'
  imageryVisible: boolean
}

type GeoJSONSourceLike = {
  setData: (data: GeoJSON.FeatureCollection) => void
}

type ImageSourceLike = {
  updateImage: (image: { url: string; coordinates: [[number, number], [number, number], [number, number], [number, number]] }) => void
}

type MapLibreModule = typeof import('maplibre-gl')
type MapLibreMap = import('maplibre-gl').Map

type MapController = {
  map: MapLibreMap
  zoneSource: GeoJSONSourceLike | null
  imagerySource: ImageSourceLike | null
}

const SOURCE_ID = 'zones'
const FILL_LAYER_ID = 'zones-fill'
const LINE_LAYER_ID = 'zones-outline'
const IMAGERY_SOURCE_ID = 'zone-imagery'
const IMAGERY_LAYER_ID = 'zone-imagery-image'
const EMPTY_PIXEL = 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=='

function buildZoneGeoJson(selectedZoneId: string): GeoJSON.FeatureCollection {
  return {
    ...zoneMap,
    features: zoneMap.features.map((feature) => ({
      ...feature,
      properties: {
        ...feature.properties,
        state: getZoneById(feature.properties.zone_id).state,
        active: feature.properties.zone_id === selectedZoneId,
      },
    })),
  }
}

function getActiveImagery(imagery: ImageryScene | null, imageryMode: 'rgb' | 'ndvi'): ImageryScene | null {
  if (!imagery) {
    return null
  }

  if (imageryMode === 'rgb') {
    return imagery.rgb_url ? imagery : null
  }

  return imagery.ndvi_url ? imagery : null
}

function syncImageryLayer(
  controller: MapController,
  imagery: ImageryScene | null,
  imageryMode: 'rgb' | 'ndvi',
  imageryVisible: boolean,
  selectedZoneId: string,
) {
  const imageUrl = imagery ? getImageryOverlayUrl(imagery, imageryMode) : null
  controller.imagerySource?.updateImage({
    url: imageUrl ?? EMPTY_PIXEL,
    coordinates: getImageryImageCoordinates(selectedZoneId),
  })

  if (controller.map.getLayer(IMAGERY_LAYER_ID)) {
    controller.map.setLayoutProperty(IMAGERY_LAYER_ID, 'visibility', imageryVisible && imageUrl ? 'visible' : 'none')
  }
}

function fitToZones(map: MapLibreMap) {
  const coordinates = zoneMap.features.flatMap((feature) => feature.geometry.coordinates[0])
  const [firstLng, firstLat] = coordinates[0]
  const bounds = coordinates.reduce(
    (acc, [lng, lat]) => {
      acc[0][0] = Math.min(acc[0][0], lng)
      acc[0][1] = Math.min(acc[0][1], lat)
      acc[1][0] = Math.max(acc[1][0], lng)
      acc[1][1] = Math.max(acc[1][1], lat)
      return acc
    },
    [[firstLng, firstLat], [firstLng, firstLat]] as [[number, number], [number, number]],
  )
  map.fitBounds(bounds, { padding: DEFAULT_MAP_PADDING, animate: false })
}

function canBootMapLibre(): boolean {
  return typeof window !== 'undefined'
    && typeof window.Blob !== 'undefined'
    && typeof window.URL?.createObjectURL === 'function'
}

export function ZoneMap({ selectedZoneId, onSelect, imagery, imageryMode, imageryVisible }: ZoneMapProps) {
  const containerRef = useRef<HTMLDivElement | null>(null)
  const controllerRef = useRef<MapController | null>(null)
  const onSelectRef = useRef(onSelect)
  const selectedZoneIdRef = useRef(selectedZoneId)
  const imageryRef = useRef(imagery)
  const imageryModeRef = useRef(imageryMode)
  const imageryVisibleRef = useRef(imageryVisible)

  useEffect(() => {
    onSelectRef.current = onSelect
  }, [onSelect])

  useEffect(() => {
    selectedZoneIdRef.current = selectedZoneId
  }, [selectedZoneId])

  useEffect(() => {
    imageryRef.current = imagery
  }, [imagery])

  useEffect(() => {
    imageryModeRef.current = imageryMode
  }, [imageryMode])

  useEffect(() => {
    imageryVisibleRef.current = imageryVisible
  }, [imageryVisible])

  const geoJson = useMemo(() => buildZoneGeoJson(selectedZoneId), [selectedZoneId])

  useEffect(() => {
    if (!containerRef.current || controllerRef.current || !canBootMapLibre()) {
      return
    }

    let cancelled = false
    let teardown: (() => void) | undefined

    void import('maplibre-gl').then((maplibregl: MapLibreModule) => {
      if (cancelled || !containerRef.current) {
        return
      }

      const map = new maplibregl.Map({
        container: containerRef.current,
        style: DEFAULT_MAP_STYLE,
        center: [105.45, 10.28],
        zoom: 7,
        attributionControl: { compact: true },
      })

      map.addControl(new maplibregl.NavigationControl({ showCompass: false }), 'top-right')

      map.on('load', () => {
        const initialGeoJson = buildZoneGeoJson(selectedZoneIdRef.current)
        const initialImagery = getActiveImagery(imageryRef.current, imageryModeRef.current)

        map.addSource(SOURCE_ID, {
          type: 'geojson',
          data: initialGeoJson,
        })

        map.addSource(IMAGERY_SOURCE_ID, {
          type: 'image',
          url: EMPTY_PIXEL,
          coordinates: getImageryImageCoordinates(selectedZoneIdRef.current),
        })

        map.addLayer({
          id: IMAGERY_LAYER_ID,
          type: 'raster',
          source: IMAGERY_SOURCE_ID,
          layout: { visibility: 'none' },
          paint: { 'raster-opacity': 0.72 },
        })

        map.addLayer({
          id: FILL_LAYER_ID,
          type: 'fill',
          source: SOURCE_ID,
          paint: {
            'fill-color': [
              'match',
              ['get', 'state'],
              'healthy', '#10b981',
              'moderate', '#f59e0b',
              'critical', '#ef4444',
              '#64748b',
            ],
            'fill-opacity': [
              'case',
              ['boolean', ['get', 'active'], false],
              0.55,
              0.28,
            ],
          },
        })

        map.addLayer({
          id: LINE_LAYER_ID,
          type: 'line',
          source: SOURCE_ID,
          paint: {
            'line-color': [
              'case',
              ['boolean', ['get', 'active'], false],
              '#2563eb',
              '#0f172a',
            ],
            'line-width': [
              'case',
              ['boolean', ['get', 'active'], false],
              3,
              1.5,
            ],
          },
        })

        controllerRef.current = {
          map,
          zoneSource: map.getSource(SOURCE_ID) as unknown as GeoJSONSourceLike | null,
          imagerySource: map.getSource(IMAGERY_SOURCE_ID) as unknown as ImageSourceLike | null,
        }

        syncImageryLayer(
          controllerRef.current,
          initialImagery,
          imageryModeRef.current,
          imageryVisibleRef.current,
          selectedZoneIdRef.current,
        )
        fitToZones(map)
      })

      map.on('click', FILL_LAYER_ID, (event) => {
        const zoneId = event.features?.[0]?.properties?.zone_id
        if (typeof zoneId === 'string') {
          onSelectRef.current(zoneId)
        }
      })

      map.on('mouseenter', FILL_LAYER_ID, () => {
        map.getCanvas().style.cursor = 'pointer'
      })

      map.on('mouseleave', FILL_LAYER_ID, () => {
        map.getCanvas().style.cursor = ''
      })

      teardown = () => {
        map.remove()
        controllerRef.current = null
      }
    })

    return () => {
      cancelled = true
      teardown?.()
    }
  }, [])

  useEffect(() => {
    controllerRef.current?.zoneSource?.setData(geoJson as GeoJSON.FeatureCollection)
  }, [geoJson])

  useEffect(() => {
    const controller = controllerRef.current
    if (!controller) {
      return
    }

    syncImageryLayer(controller, getActiveImagery(imagery, imageryMode), imageryMode, imageryVisible, selectedZoneId)
  }, [imagery, imageryMode, imageryVisible, selectedZoneId])

  return <div ref={containerRef} className="zone-map-canvas" aria-label="AgMultida zone map" />
}
