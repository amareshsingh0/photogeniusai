"use client"

import { Card, CardContent } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Sparkles, ImageIcon } from "lucide-react"
import Link from "next/link"

export function EmptyGallery() {
  return (
    <Card>
      <CardContent className="py-16">
        <div className="max-w-md mx-auto text-center space-y-6">
          <div className="inline-flex items-center justify-center h-20 w-20 rounded-full bg-purple-100">
            <ImageIcon className="h-10 w-10 text-purple-600" />
          </div>

          <div>
            <h2 className="text-2xl font-bold text-gray-900 mb-2">
              No Images Yet
            </h2>
            <p className="text-gray-600">
              You haven&apos;t generated any avatars yet. Start creating stunning AI images now!
            </p>
          </div>

          <Link href="/generate">
            <Button size="lg">
              <Sparkles className="mr-2 h-5 w-5" />
              Generate Your First Avatar
            </Button>
          </Link>
        </div>
      </CardContent>
    </Card>
  )
}
