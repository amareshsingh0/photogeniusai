"use client"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
} from "recharts"

const usageData = [
  { date: "Jan 1", credits: 12 },
  { date: "Jan 5", credits: 8 },
  { date: "Jan 10", credits: 15 },
  { date: "Jan 15", credits: 20 },
  { date: "Jan 20", credits: 10 },
  { date: "Jan 25", credits: 18 },
]

const modeBreakdown = [
  { mode: "Realism", credits: 45, color: "#3b82f6" },
  { mode: "Creative", credits: 35, color: "#a855f7" },
  { mode: "Romantic", credits: 28, color: "#ec4899" },
]

export default function UsageCharts() {
  return (
    <>
      {/* Usage Over Time */}
      <Card>
        <CardHeader>
          <CardTitle>Credits Usage Over Time</CardTitle>
        </CardHeader>
        <CardContent>
          <ResponsiveContainer width="100%" height={300}>
            <LineChart data={usageData}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="date" />
              <YAxis />
              <Tooltip />
              <Line
                type="monotone"
                dataKey="credits"
                stroke="#a855f7"
                strokeWidth={2}
              />
            </LineChart>
          </ResponsiveContainer>
        </CardContent>
      </Card>

      {/* Mode Breakdown */}
      <Card>
        <CardHeader>
          <CardTitle>Usage by Mode</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-center">
            <ResponsiveContainer width="100%" height={300}>
              <PieChart>
                <Pie
                  data={modeBreakdown}
                  dataKey="credits"
                  nameKey="mode"
                  cx="50%"
                  cy="50%"
                  outerRadius={100}
                  label
                >
                  {modeBreakdown.map((entry, index) => (
                    <Cell key={index} fill={entry.color} />
                  ))}
                </Pie>
                <Tooltip />
              </PieChart>
            </ResponsiveContainer>
          </div>
          <div className="grid grid-cols-3 gap-4 mt-4">
            {modeBreakdown.map((mode) => (
              <div key={mode.mode} className="text-center">
                <div
                  className="h-3 w-3 rounded-full mx-auto mb-1"
                  style={{ backgroundColor: mode.color }}
                />
                <p className="text-xs text-gray-600">{mode.mode}</p>
                <p className="text-sm font-semibold">{mode.credits}</p>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    </>
  )
}
