import { lazy, Suspense } from "react"
import { ChartSkeleton } from "./LoadingSkeleton"
import type { Data, Layout, Config } from "plotly.js"

const Plot = lazy(() => import("react-plotly.js"))

const DARK_LAYOUT: Partial<Layout> = {
  paper_bgcolor: "transparent",
  plot_bgcolor:  "transparent",
  font:          { family: "Inter, sans-serif", color: "#64748B", size: 11 },
  margin:        { l: 40, r: 20, t: 20, b: 40 },
  xaxis: {
    gridcolor: "#1E2D40",
    zerolinecolor: "#1E2D40",
    tickfont: { color: "#64748B" },
  },
  yaxis: {
    gridcolor: "#1E2D40",
    zerolinecolor: "#1E2D40",
    tickfont: { color: "#64748B" },
  },
  legend: { font: { color: "#E2E8F0" } },
}

const DARK_CONFIG: Partial<Config> = {
  displayModeBar: false,
  responsive: true,
  scrollZoom: false,
}

interface Props {
  data: Data[]
  layout?: Partial<Layout>
  height?: number
  className?: string
  config?: Partial<Config>
}

export function PlotlyChart({ data, layout = {}, height = 300, className = "", config }: Props) {
  return (
    <Suspense fallback={<ChartSkeleton height={height} />}>
      <div className={className}>
        <Plot
          data={data}
          layout={{ ...DARK_LAYOUT, ...layout, height }}
          config={{ ...DARK_CONFIG, ...config }}
          style={{ width: "100%", height }}
          useResizeHandler
        />
      </div>
    </Suspense>
  )
}

// ─── Preset Charts ────────────────────────────────────────────────────────────

export function GaugeChart({ value, label, color = "#00D4FF" }: { value: number; max?: number; label: string; color?: string }) {
  return (
    <PlotlyChart
      height={200}
      data={[{
        type: "indicator",
        mode: "gauge+number",
        value: value * 100,
        number: { suffix: "%", font: { size: 24, color: "#E2E8F0", family: "Bebas Neue" } },
        title: { text: label, font: { size: 11, color: "#64748B" } },
        gauge: {
          axis: { range: [0, 100], tickcolor: "#1E2D40", tickwidth: 1, tickfont: { color: "#64748B", size: 9 } },
          bar: { color },
          bgcolor: "#111827",
          borderwidth: 0,
          steps: [
            { range: [0, 33], color: "#1E2D40" },
            { range: [33, 66], color: "#1A2536" },
            { range: [66, 100], color: "#162030" },
          ],
        },
      } as Data]}
      layout={{ margin: { l: 20, r: 20, t: 30, b: 10 } }}
    />
  )
}

export function DonutChart({ labels, values, colors }: { labels: string[]; values: number[]; colors: string[] }) {
  return (
    <PlotlyChart
      height={280}
      data={[{
        type: "pie",
        hole: 0.6,
        labels,
        values,
        marker: { colors },
        textinfo: "label+percent",
        textfont: { color: "#E2E8F0", size: 11 },
        hovertemplate: "%{label}: %{percent}<extra></extra>",
      } as Data]}
      layout={{ showlegend: false, margin: { l: 20, r: 20, t: 10, b: 10 } }}
    />
  )
}

export function RadarChart({ categories, values, name, color = "#00D4FF" }: { categories: string[]; values: number[]; name: string; color?: string }) {
  return (
    <PlotlyChart
      height={300}
      data={[{
        type: "scatterpolar",
        r: values,
        theta: categories,
        fill: "toself",
        name,
        line: { color },
        fillcolor: `${color}20`,
      } as Data]}
      layout={{
        polar: {
          radialaxis: { visible: true, range: [0, 1], gridcolor: "#1E2D40", tickfont: { color: "#64748B", size: 9 } },
          angularaxis: { tickfont: { color: "#E2E8F0", size: 10 } },
          bgcolor: "transparent",
        },
        showlegend: false,
        margin: { l: 40, r: 40, t: 20, b: 20 },
      }}
    />
  )
}

export function BarChart({
  labels, values, color = "#00D4FF", horizontal = false, height = 300
}: { labels: string[]; values: number[]; color?: string; horizontal?: boolean; height?: number }) {
  return (
    <PlotlyChart
      height={height}
      data={[{
        type: "bar",
        ...(horizontal ? { x: values, y: labels, orientation: "h" } : { x: labels, y: values }),
        marker: { color: values.map((_, i) => i === 0 ? color : `${color}80`) },
        hovertemplate: "%{label}: %{value:.3f}<extra></extra>",
      } as Data]}
      layout={{ bargap: 0.3, margin: { l: horizontal ? 100 : 40, r: 20, t: 10, b: horizontal ? 40 : 60 } }}
    />
  )
}

export function HeatmapChart({ z, x, y, title }: { z: number[][]; x: string[]; y: string[]; title?: string }) {
  return (
    <PlotlyChart
      height={350}
      data={[{
        type: "heatmap",
        z,
        x,
        y,
        colorscale: [[0, "#0A0E1A"], [0.5, "#00D4FF40"], [1, "#00D4FF"]],
        hovertemplate: "%{y} vs %{x}: %{z:.3f}<extra></extra>",
        showscale: true,
        colorbar: { tickfont: { color: "#64748B" }, outlinewidth: 0 },
      } as Data]}
      layout={{ title: title ? { text: title, font: { color: "#64748B", size: 11 } } : undefined }}
    />
  )
}

export function LineChart({ x, y, name, color = "#00D4FF" }: { x: number[] | string[]; y: number[]; name: string; color?: string }) {
  return (
    <PlotlyChart
      height={250}
      data={[{
        type: "scatter",
        mode: "lines+markers",
        x,
        y,
        name,
        line: { color, width: 2 },
        marker: { color, size: 5 },
        hovertemplate: "%{x}: %{y:.3f}<extra></extra>",
      } as Data]}
    />
  )
}
