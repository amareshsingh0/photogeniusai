"use client";

import { useState, useEffect } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Loader2, Save, RefreshCw, CheckCircle2, AlertCircle } from "lucide-react";

interface FeatureFlag {
  key: string;
  value: string;
  category: string;
  description: string;
  type: "boolean" | "string" | "number";
  options: string[];
}

interface ConfigResponse {
  flags: FeatureFlag[];
  env_file_path: string;
  last_modified: string;
}

export default function FeatureConfigPanel() {
  const [config, setConfig] = useState<ConfigResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [restarting, setRestarting] = useState(false);
  const [changes, setChanges] = useState<Record<string, string>>({});
  const [message, setMessage] = useState<{ type: "success" | "error"; text: string } | null>(null);

  // Group flags by category
  const groupedFlags = config?.flags.reduce((acc, flag) => {
    if (!acc[flag.category]) {
      acc[flag.category] = [];
    }
    acc[flag.category].push(flag);
    return acc;
  }, {} as Record<string, FeatureFlag[]>) || {};

  // Load configuration
  useEffect(() => {
    fetchConfig();
  }, []);

  const fetchConfig = async () => {
    try {
      setLoading(true);
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || "https://api.creatives.bimoraai.com";
      const res = await fetch(`${apiUrl}/api/v1/admin/config`);
      if (!res.ok) throw new Error("Failed to load configuration");
      const data = await res.json();
      setConfig(data);
      setChanges({});
      setMessage(null);
    } catch (err) {
      setMessage({ type: "error", text: "Failed to load configuration" });
    } finally {
      setLoading(false);
    }
  };

  const handleChange = (key: string, value: string) => {
    setChanges(prev => ({ ...prev, [key]: value }));
  };

  const saveChanges = async () => {
    if (Object.keys(changes).length === 0) {
      setMessage({ type: "error", text: "No changes to save" });
      return;
    }

    try {
      setSaving(true);
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || "https://api.creatives.bimoraai.com";
      const res = await fetch(`${apiUrl}/api/v1/admin/config`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ updates: changes }),
      });

      if (!res.ok) {
        const error = await res.json();
        throw new Error(error.detail || "Failed to save configuration");
      }

      const result = await res.json();
      setMessage({
        type: "success",
        text: `✅ Saved ${Object.keys(changes).length} changes. ${result.note}`,
      });

      // Reload config
      await fetchConfig();
    } catch (err: any) {
      setMessage({ type: "error", text: err.message });
    } finally {
      setSaving(false);
    }
  };

  const restartAPI = async () => {
    if (!confirm("Restart the API to apply changes? This will cause 2-3 seconds downtime.")) {
      return;
    }

    try {
      setRestarting(true);
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || "https://api.creatives.bimoraai.com";
      const res = await fetch(`${apiUrl}/api/v1/admin/config/restart`, {
        method: "POST",
      });

      if (!res.ok) {
        const error = await res.json();
        throw new Error(error.detail || "Failed to restart API");
      }

      setMessage({ type: "success", text: "✅ API restarted successfully" });

      // Wait 3 seconds for API to restart, then reload config
      setTimeout(() => {
        fetchConfig();
      }, 3000);
    } catch (err: any) {
      setMessage({ type: "error", text: err.message });
    } finally {
      setRestarting(false);
    }
  };

  const getCurrentValue = (flag: FeatureFlag): string => {
    return changes[flag.key] ?? flag.value;
  };

  const renderControl = (flag: FeatureFlag) => {
    const currentValue = getCurrentValue(flag);
    const hasChanged = changes[flag.key] !== undefined;

    if (flag.type === "boolean") {
      return (
        <div className="flex items-center gap-3">
          <Switch
            checked={currentValue === "true"}
            onCheckedChange={(checked) =>
              handleChange(flag.key, checked ? "true" : "false")
            }
          />
          <span className={`text-sm ${hasChanged ? "text-blue-400 font-medium" : "text-zinc-400"}`}>
            {currentValue === "true" ? "Enabled" : "Disabled"}
          </span>
          {hasChanged && <span className="text-xs text-blue-400">*modified</span>}
        </div>
      );
    }

    if (flag.options && flag.options.length > 0) {
      return (
        <div className="flex items-center gap-2">
          <Select
            value={currentValue}
            onValueChange={(value) => handleChange(flag.key, value)}
          >
            <SelectTrigger className={`w-48 ${hasChanged ? "border-blue-500" : ""}`}>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {flag.options.map((option) => (
                <SelectItem key={option} value={option}>
                  {option}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          {hasChanged && <span className="text-xs text-blue-400">*modified</span>}
        </div>
      );
    }

    return (
      <div className="flex items-center gap-2">
        <input
          type="text"
          value={currentValue}
          onChange={(e) => handleChange(flag.key, e.target.value)}
          className={`px-3 py-2 border rounded-md w-48 bg-zinc-900 text-white ${
            hasChanged ? "border-blue-500" : "border-zinc-700"
          }`}
        />
        {hasChanged && <span className="text-xs text-blue-400">*modified</span>}
      </div>
    );
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-96">
        <Loader2 className="w-8 h-8 animate-spin text-zinc-400" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header Actions */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-white">Feature Configuration</h2>
          <p className="text-zinc-400 mt-1">
            Runtime feature flags. Changes write to .env — restart the API to apply.
          </p>
        </div>
        <div className="flex gap-2">
          <Button
            variant="outline"
            onClick={fetchConfig}
            disabled={loading}
            className="bg-zinc-800 border-zinc-700 hover:bg-zinc-700"
          >
            <RefreshCw className="w-4 h-4 mr-2" />
            Refresh
          </Button>
          <Button
            variant="outline"
            onClick={restartAPI}
            disabled={restarting || Object.keys(changes).length === 0}
            className="bg-zinc-800 border-zinc-700 hover:bg-zinc-700"
          >
            {restarting ? (
              <Loader2 className="w-4 h-4 mr-2 animate-spin" />
            ) : (
              <RefreshCw className="w-4 h-4 mr-2" />
            )}
            Restart API
          </Button>
          <Button
            onClick={saveChanges}
            disabled={saving || Object.keys(changes).length === 0}
            className="bg-purple-600 hover:bg-purple-700"
          >
            {saving ? (
              <Loader2 className="w-4 h-4 mr-2 animate-spin" />
            ) : (
              <Save className="w-4 h-4 mr-2" />
            )}
            Save Changes ({Object.keys(changes).length})
          </Button>
        </div>
      </div>

      {/* Message */}
      {message && (
        <Alert variant={message.type === "error" ? "destructive" : "default"} className="bg-zinc-900 border-zinc-800">
          {message.type === "success" ? (
            <CheckCircle2 className="h-4 w-4" />
          ) : (
            <AlertCircle className="h-4 w-4" />
          )}
          <AlertDescription>{message.text}</AlertDescription>
        </Alert>
      )}

      {/* Configuration Groups */}
      <div className="space-y-6">
        {Object.entries(groupedFlags).map(([category, flags]) => (
          <Card key={category} className="bg-zinc-900/50 border-zinc-800">
            <CardHeader>
              <CardTitle className="text-white">{category}</CardTitle>
              <CardDescription className="text-zinc-400">
                {flags.length} feature{flags.length !== 1 ? "s" : ""}
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {flags.map((flag) => (
                <div
                  key={flag.key}
                  className="flex items-center justify-between py-3 border-b border-zinc-800 last:border-0"
                >
                  <div className="flex-1">
                    <Label className="text-sm font-medium text-white">{flag.key}</Label>
                    <p className="text-sm text-zinc-400 mt-1">
                      {flag.description}
                    </p>
                  </div>
                  <div className="flex-shrink-0 ml-6">
                    {renderControl(flag)}
                  </div>
                </div>
              ))}
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Footer Info */}
      <Card className="bg-zinc-900/50 border-zinc-800">
        <CardContent className="pt-6">
          <div className="flex items-center justify-between text-sm text-zinc-400">
            <div>
              <strong className="text-white">Config file:</strong> {config?.env_file_path}
            </div>
            <div>
              <strong className="text-white">Last modified:</strong>{" "}
              {config?.last_modified
                ? new Date(config.last_modified).toLocaleString()
                : "Unknown"}
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
