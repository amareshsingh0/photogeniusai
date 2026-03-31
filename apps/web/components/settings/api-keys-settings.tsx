"use client"

import { useState, useEffect } from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Badge } from "@/components/ui/badge"
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
import {
  Key,
  Plus,
  Copy,
  Trash2,
  Eye,
  EyeOff,
  CheckCircle,
  AlertTriangle,
} from "lucide-react"
import { useToast } from "@/components/ui/use-toast"
import { format } from "date-fns"

interface ApiKey {
  id: string
  name: string
  key: string
  prefix: string
  createdAt: string
  lastUsed: string | null
  usageCount: number
}

export function ApiKeysSettings() {
  const { toast } = useToast()
  const [apiKeys, setApiKeys] = useState<ApiKey[]>([])

  useEffect(() => {
    try {
      const stored = localStorage.getItem("api_keys")
      if (stored) setApiKeys(JSON.parse(stored))
    } catch {}
  }, [])

  const [showKeys, setShowKeys] = useState<Set<string>>(new Set())
  const [newKeyName, setNewKeyName] = useState("")
  const [isCreatingKey, setIsCreatingKey] = useState(false)
  const [newlyCreatedKey, setNewlyCreatedKey] = useState<string | null>(null)

  const toggleKeyVisibility = (keyId: string) => {
    setShowKeys((prev) => {
      const newSet = new Set(prev)
      if (newSet.has(keyId)) {
        newSet.delete(keyId)
      } else {
        newSet.add(keyId)
      }
      return newSet
    })
  }

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text)
    toast({
      title: "Copied to clipboard",
      description: "API key has been copied to your clipboard.",
    })
  }

  const persistKeys = (keys: ApiKey[]) => {
    try { localStorage.setItem("api_keys", JSON.stringify(keys)) } catch {}
  }

  const createApiKey = async () => {
    if (!newKeyName.trim()) {
      toast({
        title: "Name required",
        description: "Please provide a name for your API key.",
        variant: "destructive",
      })
      return
    }

    setIsCreatingKey(true)
    await new Promise((resolve) => setTimeout(resolve, 600))

    const rand = () => Math.random().toString(36).substring(2)
    const fullKey = `sk_live_${rand()}${rand()}`.slice(0, 48)
    const newKey: ApiKey = {
      id: `key_${Date.now()}`,
      name: newKeyName,
      key: fullKey,
      prefix: fullKey.slice(0, 12),
      createdAt: new Date().toISOString(),
      lastUsed: null,
      usageCount: 0,
    }

    const updated = [...apiKeys, newKey]
    setApiKeys(updated)
    persistKeys(updated)
    setNewlyCreatedKey(newKey.key)
    setNewKeyName("")
    setIsCreatingKey(false)

    toast({
      title: "API key created",
      description: "Your new API key has been created successfully.",
    })
  }

  const deleteApiKey = (keyId: string) => {
    const updated = apiKeys.filter((k) => k.id !== keyId)
    setApiKeys(updated)
    persistKeys(updated)
    toast({
      title: "API key deleted",
      description: "The API key has been permanently deleted.",
    })
  }

  return (
    <div className="space-y-6">
      {/* Header Card */}
      <Card className="glass-card border-primary/30 bg-gradient-to-r from-primary/10 to-secondary/10">
        <CardContent className="pt-6">
          <div className="flex items-start space-x-3">
            <div className="h-10 w-10 rounded-lg bg-primary/20 flex items-center justify-center">
              <Key className="h-5 w-5 text-primary" />
            </div>
            <div className="flex-1">
              <h3 className="font-semibold text-foreground mb-1">
                API Keys for Developers
              </h3>
              <p className="text-sm text-muted-foreground mb-3">
                Use API keys to integrate PhotoGenius AI into your applications.
                Keep your keys secure and never share them publicly.
              </p>
              <div className="flex items-center space-x-2">
                <Button variant="outline" size="sm">
                  View Documentation
                </Button>
                <Button variant="outline" size="sm">
                  API Reference
                </Button>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Newly Created Key Alert */}
      {newlyCreatedKey && (
        <Card className="glass-card border-primary/30 bg-primary/10">
          <CardContent className="pt-6">
            <div className="flex items-start space-x-3">
              <AlertTriangle className="h-5 w-5 text-primary mt-0.5" />
              <div className="flex-1">
                <h4 className="font-semibold text-foreground mb-1">
                  Save Your API Key
                </h4>
                <p className="text-sm text-muted-foreground mb-3">
                  This is the only time you&apos;ll see this key. Copy it now and store
                  it securely.
                </p>
                <div className="flex items-center space-x-2">
                  <Input
                    value={newlyCreatedKey}
                    readOnly
                    className="font-mono text-sm"
                  />
                  <Button
                    variant="outline"
                    onClick={() => copyToClipboard(newlyCreatedKey)}
                  >
                    <Copy className="h-4 w-4" />
                  </Button>
                </div>
              </div>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setNewlyCreatedKey(null)}
              >
                Dismiss
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Create New Key */}
      <Card className="glass-card">
        <CardHeader>
          <CardTitle className="text-foreground">Create New API Key</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex space-x-2">
            <div className="flex-1">
              <Input
                placeholder="Enter a name for this key (e.g., Production API)"
                value={newKeyName}
                onChange={(e) => setNewKeyName(e.target.value)}
              />
            </div>
            <Button onClick={createApiKey} disabled={isCreatingKey}>
              <Plus className="mr-2 h-4 w-4" />
              {isCreatingKey ? "Creating..." : "Create Key"}
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Existing Keys */}
      <Card className="glass-card">
        <CardHeader>
          <CardTitle className="text-foreground">Your API Keys</CardTitle>
        </CardHeader>
        <CardContent>
          {apiKeys.length === 0 ? (
            <div className="text-center py-8">
              <Key className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
              <h3 className="text-lg font-semibold text-foreground mb-2">
                No API Keys
              </h3>
              <p className="text-muted-foreground mb-4">
                Create your first API key to get started
              </p>
            </div>
          ) : (
            <div className="space-y-4">
              {apiKeys.map((apiKey) => {
                const isVisible = showKeys.has(apiKey.id)

                return (
                  <div
                    key={apiKey.id}
                    className="p-4 rounded-lg border border-border/50 bg-muted/30"
                  >
                    <div className="flex items-start justify-between mb-3">
                      <div className="flex-1">
                        <h4 className="font-semibold text-foreground mb-1">
                          {apiKey.name}
                        </h4>
                        <div className="flex items-center space-x-4 text-sm text-muted-foreground">
                          <span>
                            Created {format(new Date(apiKey.createdAt), "PP")}
                          </span>
                          {apiKey.lastUsed ? (
                            <span>
                              Last used{" "}
                              {format(new Date(apiKey.lastUsed), "PP")}
                            </span>
                          ) : (
                            <Badge variant="outline" className="border-border/50">Never used</Badge>
                          )}
                          <Badge variant="secondary" className="border-primary/30">
                            {apiKey.usageCount.toLocaleString()} requests
                          </Badge>
                        </div>
                      </div>

                      <AlertDialog>
                        <AlertDialogTrigger asChild>
                          <Button variant="ghost" size="sm">
                            <Trash2 className="h-4 w-4 text-destructive" />
                          </Button>
                        </AlertDialogTrigger>
                        <AlertDialogContent className="glass-card">
                          <AlertDialogHeader>
                            <AlertDialogTitle className="text-foreground">Delete API Key?</AlertDialogTitle>
                            <AlertDialogDescription className="text-muted-foreground">
                              This action cannot be undone. Applications using this
                              key will stop working immediately.
                            </AlertDialogDescription>
                          </AlertDialogHeader>
                          <AlertDialogFooter>
                            <AlertDialogCancel>Cancel</AlertDialogCancel>
                            <AlertDialogAction
                              onClick={() => deleteApiKey(apiKey.id)}
                              className="bg-destructive hover:bg-destructive/90"
                            >
                              Delete Key
                            </AlertDialogAction>
                          </AlertDialogFooter>
                        </AlertDialogContent>
                      </AlertDialog>
                    </div>

                    <div className="flex items-center space-x-2">
                      <Input
                        value={
                          isVisible
                            ? apiKey.key
                            : `${apiKey.prefix}••••••••••••••••••••••••••••••••`
                        }
                        readOnly
                        className="font-mono text-sm"
                      />
                      <Button
                        variant="outline"
                        size="icon"
                        onClick={() => toggleKeyVisibility(apiKey.id)}
                      >
                        {isVisible ? (
                          <EyeOff className="h-4 w-4" />
                        ) : (
                          <Eye className="h-4 w-4" />
                        )}
                      </Button>
                      <Button
                        variant="outline"
                        size="icon"
                        onClick={() => copyToClipboard(apiKey.key)}
                      >
                        <Copy className="h-4 w-4" />
                      </Button>
                    </div>
                  </div>
                )
              })}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Security Best Practices */}
      <Card className="glass-card border-primary/30 bg-primary/10">
        <CardHeader>
          <CardTitle className="text-foreground">Security Best Practices</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2 text-sm text-muted-foreground">
          <div className="flex items-start space-x-2">
            <CheckCircle className="h-4 w-4 text-primary mt-0.5 flex-shrink-0" />
            <p>Never commit API keys to version control (Git, GitHub, etc.)</p>
          </div>
          <div className="flex items-start space-x-2">
            <CheckCircle className="h-4 w-4 text-primary mt-0.5 flex-shrink-0" />
            <p>Store keys in environment variables or secure vaults</p>
          </div>
          <div className="flex items-start space-x-2">
            <CheckCircle className="h-4 w-4 text-primary mt-0.5 flex-shrink-0" />
            <p>Use different keys for development and production</p>
          </div>
          <div className="flex items-start space-x-2">
            <CheckCircle className="h-4 w-4 text-primary mt-0.5 flex-shrink-0" />
            <p>Rotate keys regularly and delete unused keys</p>
          </div>
          <div className="flex items-start space-x-2">
            <CheckCircle className="h-4 w-4 text-primary mt-0.5 flex-shrink-0" />
            <p>Monitor usage to detect unauthorized access</p>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
