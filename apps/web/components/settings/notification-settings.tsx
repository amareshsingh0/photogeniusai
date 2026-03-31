"use client"

import { useState, useEffect } from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Switch } from "@/components/ui/switch"
import { Label } from "@/components/ui/label"
import { useToast } from "@/components/ui/use-toast"

const DEFAULT_SETTINGS = {
  emailNotifications: {
    trainingComplete: true,
    generationComplete: true,
    creditLow: true,
    weeklyDigest: false,
    productUpdates: true,
  },
  pushNotifications: {
    trainingComplete: true,
    generationComplete: true,
    creditLow: false,
  },
}

export function NotificationSettings() {
  const { toast } = useToast()
  const [settings, setSettings] = useState(DEFAULT_SETTINGS)

  useEffect(() => {
    try {
      const stored = localStorage.getItem("notification_settings")
      if (stored) setSettings(JSON.parse(stored))
    } catch {}
  }, [])

  const handleSave = () => {
    try {
      localStorage.setItem("notification_settings", JSON.stringify(settings))
    } catch {}
    toast({
      title: "Settings saved",
      description: "Your notification preferences have been updated.",
    })
  }

  return (
    <div className="space-y-6">
      {/* Email Notifications */}
      <Card className="glass-card">
        <CardHeader>
          <CardTitle className="text-foreground">Email Notifications</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center justify-between">
            <div className="space-y-0.5">
              <Label className="text-foreground">Training Complete</Label>
              <p className="text-sm text-muted-foreground">
                Get notified when identity training is complete
              </p>
            </div>
            <Switch
              checked={settings.emailNotifications.trainingComplete}
              onCheckedChange={(checked) =>
                setSettings({
                  ...settings,
                  emailNotifications: {
                    ...settings.emailNotifications,
                    trainingComplete: checked,
                  },
                })
              }
            />
          </div>

          <div className="flex items-center justify-between">
            <div className="space-y-0.5">
              <Label className="text-foreground">Generation Complete</Label>
              <p className="text-sm text-muted-foreground">
                Get notified when image generation is complete
              </p>
            </div>
            <Switch
              checked={settings.emailNotifications.generationComplete}
              onCheckedChange={(checked) =>
                setSettings({
                  ...settings,
                  emailNotifications: {
                    ...settings.emailNotifications,
                    generationComplete: checked,
                  },
                })
              }
            />
          </div>

          <div className="flex items-center justify-between">
            <div className="space-y-0.5">
              <Label className="text-foreground">Low Credits Alert</Label>
              <p className="text-sm text-muted-foreground">
                Get notified when your credit balance is low
              </p>
            </div>
            <Switch
              checked={settings.emailNotifications.creditLow}
              onCheckedChange={(checked) =>
                setSettings({
                  ...settings,
                  emailNotifications: {
                    ...settings.emailNotifications,
                    creditLow: checked,
                  },
                })
              }
            />
          </div>

          <div className="flex items-center justify-between">
            <div className="space-y-0.5">
              <Label className="text-foreground">Weekly Digest</Label>
              <p className="text-sm text-muted-foreground">
                Receive a weekly summary of your activity
              </p>
            </div>
            <Switch
              checked={settings.emailNotifications.weeklyDigest}
              onCheckedChange={(checked) =>
                setSettings({
                  ...settings,
                  emailNotifications: {
                    ...settings.emailNotifications,
                    weeklyDigest: checked,
                  },
                })
              }
            />
          </div>

          <div className="flex items-center justify-between">
            <div className="space-y-0.5">
              <Label className="text-foreground">Product Updates</Label>
              <p className="text-sm text-muted-foreground">
                Stay updated with new features and improvements
              </p>
            </div>
            <Switch
              checked={settings.emailNotifications.productUpdates}
              onCheckedChange={(checked) =>
                setSettings({
                  ...settings,
                  emailNotifications: {
                    ...settings.emailNotifications,
                    productUpdates: checked,
                  },
                })
              }
            />
          </div>
        </CardContent>
      </Card>

      {/* Push Notifications */}
      <Card className="glass-card">
        <CardHeader>
          <CardTitle className="text-foreground">Push Notifications</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center justify-between">
            <div className="space-y-0.5">
              <Label className="text-foreground">Training Complete</Label>
              <p className="text-sm text-muted-foreground">
                Browser notification when training is complete
              </p>
            </div>
            <Switch
              checked={settings.pushNotifications.trainingComplete}
              onCheckedChange={(checked) =>
                setSettings({
                  ...settings,
                  pushNotifications: {
                    ...settings.pushNotifications,
                    trainingComplete: checked,
                  },
                })
              }
            />
          </div>

          <div className="flex items-center justify-between">
            <div className="space-y-0.5">
              <Label className="text-foreground">Generation Complete</Label>
              <p className="text-sm text-muted-foreground">
                Browser notification when generation is complete
              </p>
            </div>
            <Switch
              checked={settings.pushNotifications.generationComplete}
              onCheckedChange={(checked) =>
                setSettings({
                  ...settings,
                  pushNotifications: {
                    ...settings.pushNotifications,
                    generationComplete: checked,
                  },
                })
              }
            />
          </div>

          <div className="flex items-center justify-between">
            <div className="space-y-0.5">
              <Label className="text-foreground">Low Credits Alert</Label>
              <p className="text-sm text-muted-foreground">
                Browser notification for low credit balance
              </p>
            </div>
            <Switch
              checked={settings.pushNotifications.creditLow}
              onCheckedChange={(checked) =>
                setSettings({
                  ...settings,
                  pushNotifications: {
                    ...settings.pushNotifications,
                    creditLow: checked,
                  },
                })
              }
            />
          </div>
        </CardContent>
      </Card>

      <div className="flex justify-end">
        <Button onClick={handleSave}>Save Preferences</Button>
      </div>
    </div>
  )
}
