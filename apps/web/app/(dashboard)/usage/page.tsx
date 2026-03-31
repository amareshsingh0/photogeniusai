"use client"

import { useState, Suspense } from "react"
import dynamic from "next/dynamic"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Badge } from "@/components/ui/badge"
import { TrendingUp, Download, FileText } from "lucide-react"
import { Button } from "@/components/ui/button"

// Lazy load charts component
const UsageCharts = dynamic(() => import("@/components/usage/usage-charts"), { 
  ssr: false,
  loading: () => (
    <div className="grid md:grid-cols-2 gap-6">
      <div className="h-80 bg-muted/30 rounded-lg animate-pulse" />
      <div className="h-80 bg-muted/30 rounded-lg animate-pulse" />
    </div>
  )
})

const transactions = [
  {
    id: "1",
    date: "2025-01-26",
    type: "Generation",
    mode: "REALISM",
    credits: -3,
    balance: 147,
  },
  {
    id: "2",
    date: "2025-01-25",
    type: "Purchase",
    description: "Pro Pack",
    credits: +150,
    balance: 150,
    invoice: "INV-001",
  },
  {
    id: "3",
    date: "2025-01-24",
    type: "Generation",
    mode: "CREATIVE",
    credits: -5,
    balance: 0,
  },
]

export default function UsagePage() {
  const [timeRange, setTimeRange] = useState("30d")

  return (
    <div className="max-w-7xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">Usage & Billing</h1>
          <p className="mt-2 text-gray-600">
            Track your credit usage and billing history
          </p>
        </div>

        <Select value={timeRange} onValueChange={setTimeRange}>
          <SelectTrigger className="w-32">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="7d">Last 7 days</SelectItem>
            <SelectItem value="30d">Last 30 days</SelectItem>
            <SelectItem value="90d">Last 90 days</SelectItem>
            <SelectItem value="1y">Last year</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {/* Stats Cards */}
      <div className="grid md:grid-cols-4 gap-4">
        <Card>
          <CardContent className="pt-6">
            <div className="text-2xl font-bold">108</div>
            <p className="text-sm text-gray-600">Credits Used</p>
            <p className="text-xs text-green-600 mt-1">
              <TrendingUp className="inline h-3 w-3" /> +12% vs last month
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="pt-6">
            <div className="text-2xl font-bold">36</div>
            <p className="text-sm text-gray-600">Generations</p>
            <p className="text-xs text-gray-500 mt-1">
              This month
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="pt-6">
            <div className="text-2xl font-bold">$44.99</div>
            <p className="text-sm text-gray-600">Total Spent</p>
            <p className="text-xs text-gray-500 mt-1">
              Last 30 days
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="pt-6">
            <div className="text-2xl font-bold">Feb 1</div>
            <p className="text-sm text-gray-600">Next Billing</p>
            <p className="text-xs text-gray-500 mt-1">
              Pro Plan - $29/mo
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Charts */}
      <Suspense fallback={
        <div className="grid md:grid-cols-2 gap-6">
          <div className="h-80 bg-muted/30 rounded-lg animate-pulse" />
          <div className="h-80 bg-muted/30 rounded-lg animate-pulse" />
        </div>
      }>
        <UsageCharts />
      </Suspense>

      {/* Transaction History */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center justify-between">
            <span>Transaction History</span>
            <Button variant="outline" size="sm">
              <Download className="mr-2 h-4 w-4" />
              Export
            </Button>
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            {transactions.map((transaction) => (
              <div
                key={transaction.id}
                className="flex items-center justify-between p-4 rounded-lg border"
              >
                <div className="flex items-center space-x-4">
                  <div className={`h-10 w-10 rounded-lg flex items-center justify-center ${
                    transaction.credits > 0 ? "bg-green-100" : "bg-blue-100"
                  }`}>
                    {transaction.credits > 0 ? "+" : transaction.mode?.[0]}
                  </div>
                  <div>
                    <p className="font-medium text-gray-900">
                      {transaction.type}
                      {transaction.mode && (
                        <Badge variant="secondary" className="ml-2">
                          {transaction.mode}
                        </Badge>
                      )}
                    </p>
                    <p className="text-sm text-gray-600">
                      {new Date(transaction.date).toLocaleDateString()}
                      {transaction.description && ` • ${transaction.description}`}
                    </p>
                  </div>
                </div>

                <div className="text-right">
                  <p className={`font-semibold ${
                    transaction.credits > 0 ? "text-green-600" : "text-gray-900"
                  }`}>
                    {transaction.credits > 0 ? "+" : ""}
                    {transaction.credits} credits
                  </p>
                  <p className="text-sm text-gray-600">
                    Balance: {transaction.balance}
                  </p>
                  {transaction.invoice && (
                    <Button variant="link" size="sm" className="h-auto p-0 mt-1">
                      <FileText className="mr-1 h-3 w-3" />
                      {transaction.invoice}
                    </Button>
                  )}
                </div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
