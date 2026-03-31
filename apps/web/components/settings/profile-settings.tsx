"use client"

import { useState, useEffect } from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog"
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar"
import { Upload, AlertTriangle, CheckCircle } from "lucide-react"
import { useToast } from "@/components/ui/use-toast"

export function ProfileSettings() {
  const { toast } = useToast()
  const [saving, setSaving] = useState(false)
  const [loaded, setLoaded] = useState(false)
  const [formData, setFormData] = useState({
    firstName: "",
    lastName: "",
    email: "dev@photogenius.local",
    username: "photogenius_user",
    avatar: "",
  })

  // Load real user data from localStorage on mount
  useEffect(() => {
    try {
      const stored = JSON.parse(localStorage.getItem("dev_user") ?? "{}")
      if (stored?.name) {
        const parts = (stored.name as string).split(" ")
        setFormData({
          firstName: parts[0] ?? "",
          lastName: parts.slice(1).join(" ") ?? "",
          email: stored.email ?? "dev@photogenius.local",
          username: (stored.name as string).toLowerCase().replace(/\s+/g, "_"),
          avatar: `https://api.dicebear.com/7.x/avataaars/svg?seed=${encodeURIComponent(stored.name)}`,
        })
      }
    } catch { /* ignore */ }
    setLoaded(true)
  }, [])

  const handleSave = async () => {
    setSaving(true)
    await new Promise((resolve) => setTimeout(resolve, 600))
    try {
      const stored = JSON.parse(localStorage.getItem("dev_user") ?? "{}")
      const fullName = [formData.firstName, formData.lastName].filter(Boolean).join(" ") || "User"
      localStorage.setItem("dev_user", JSON.stringify({ ...stored, name: fullName, email: formData.email }))
    } catch { /* ignore */ }
    setSaving(false)
    toast({ title: "Profile updated", description: "Your profile has been saved." })
  }

  const handleDeleteAccount = async () => {
    // API call to delete account
    toast({
      title: "Account deleted",
      description: "Your account has been permanently deleted.",
      variant: "destructive",
    })
  }

  return (
    <div className="space-y-6">
      {/* Profile Photo */}
      <Card className="glass-card">
        <CardHeader>
          <CardTitle className="text-foreground">Profile Photo</CardTitle>
        </CardHeader>
        <CardContent className="flex items-center space-x-6">
          <Avatar className="h-24 w-24">
            <AvatarImage src={formData.avatar} />
            <AvatarFallback className="bg-primary/20 text-primary">
              {formData.firstName[0]}
              {formData.lastName[0]}
            </AvatarFallback>
          </Avatar>

          <div className="flex-1">
            <Button variant="outline" className="mb-2">
              <Upload className="mr-2 h-4 w-4" />
              Upload New Photo
            </Button>
            <p className="text-sm text-muted-foreground">
              JPG, PNG or GIF. Max size 2MB.
            </p>
          </div>
        </CardContent>
      </Card>

      {/* Personal Information */}
      <Card className="glass-card">
        <CardHeader>
          <CardTitle className="text-foreground">Personal Information</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid md:grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="firstName">First Name</Label>
              <Input
                id="firstName"
                value={formData.firstName}
                onChange={(e) =>
                  setFormData({ ...formData, firstName: e.target.value })
                }
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="lastName">Last Name</Label>
              <Input
                id="lastName"
                value={formData.lastName}
                onChange={(e) =>
                  setFormData({ ...formData, lastName: e.target.value })
                }
              />
            </div>
          </div>

          <div className="space-y-2">
            <Label htmlFor="email">Email Address</Label>
            <Input
              id="email"
              type="email"
              value={formData.email}
              onChange={(e) =>
                setFormData({ ...formData, email: e.target.value })
              }
            />
            <p className="text-sm text-muted-foreground">
              This is your primary email for notifications and account recovery.
            </p>
          </div>

          <div className="space-y-2">
            <Label htmlFor="username">Username</Label>
            <Input
              id="username"
              value={formData.username}
              onChange={(e) =>
                setFormData({ ...formData, username: e.target.value })
              }
            />
          </div>

          <div className="pt-4 flex justify-end">
            <Button onClick={handleSave} disabled={saving}>
              {saving ? "Saving..." : "Save Changes"}
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Danger Zone */}
      <Card className="glass-card border-destructive/50">
        <CardHeader>
          <CardTitle className="text-destructive">Danger Zone</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="p-4 rounded-lg bg-destructive/10 border border-destructive/30">
            <div className="flex items-start space-x-3">
              <AlertTriangle className="h-5 w-5 text-destructive mt-0.5" />
              <div className="flex-1">
                <h4 className="font-semibold text-foreground mb-1">
                  Delete Account
                </h4>
                <p className="text-sm text-muted-foreground mb-4">
                  Once you delete your account, there is no going back. All your
                  data, including identities and generated images, will be
                  permanently deleted.
                </p>

                <AlertDialog>
                  <AlertDialogTrigger asChild>
                    <Button variant="destructive">Delete My Account</Button>
                  </AlertDialogTrigger>
                  <AlertDialogContent className="glass-card">
                    <AlertDialogHeader>
                      <AlertDialogTitle className="text-foreground">
                        Are you absolutely sure?
                      </AlertDialogTitle>
                      <AlertDialogDescription className="text-muted-foreground">
                        This action cannot be undone. This will permanently delete
                        your account and remove all your data from our servers.
                      </AlertDialogDescription>
                    </AlertDialogHeader>
                    <AlertDialogFooter>
                      <AlertDialogCancel>Cancel</AlertDialogCancel>
                      <AlertDialogAction
                        onClick={handleDeleteAccount}
                        className="bg-destructive hover:bg-destructive/90"
                      >
                        Delete Account
                      </AlertDialogAction>
                    </AlertDialogFooter>
                  </AlertDialogContent>
                </AlertDialog>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
