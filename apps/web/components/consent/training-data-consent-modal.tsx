"use client";

import { useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Sparkles } from "lucide-react";

const OPT_IN_CREDITS = 100;

export interface TrainingDataConsentModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onConsentRecorded?: (creditsGranted: number) => void;
}

/**
 * Modal shown after first generation: "Help improve PhotoGenius?"
 * Opt-in to let us learn from your generations; +100 free credits for opting in.
 * Granular: Allow training / Allow showcase / Neither.
 */
export function TrainingDataConsentModal({
  open,
  onOpenChange,
  onConsentRecorded,
}: TrainingDataConsentModalProps) {
  const [allowTraining, setAllowTraining] = useState(false);
  const [allowShowcase, setAllowShowcase] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch("/api/consent/record", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          version: "1.0.0",
          allowTraining,
          allowShowcase,
          text: "Training data consent (training/showcase)",
        }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        setError(data?.error ?? "Failed to save");
        return;
      }
      onConsentRecorded?.(data?.creditsGranted ?? 0);
      onOpenChange(false);
    } catch (e) {
      setError("Something went wrong");
    } finally {
      setLoading(false);
    }
  };

  const handleDecline = () => {
    onOpenChange(false);
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <div className="flex items-center gap-2">
            <Sparkles className="h-5 w-5 text-primary" />
            <DialogTitle>Help improve PhotoGenius?</DialogTitle>
          </div>
          <DialogDescription>
            Opt-in to let us learn from your generations (anonymized) to improve our models.
            You can withdraw consent anytime in settings.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-2">
          <div className="rounded-lg border border-primary/20 bg-primary/5 p-3 text-sm">
            <strong>+{OPT_IN_CREDITS} free credits</strong> when you allow training data use.
          </div>

          <div className="space-y-3">
            <label className="flex items-start gap-3 rounded-md border p-3 hover:bg-muted/50 cursor-pointer">
              <Checkbox
                checked={allowTraining}
                onCheckedChange={(v) => setAllowTraining(!!v)}
                className="mt-0.5"
              />
              <div>
                <span className="font-medium">Allow training</span>
                <p className="text-xs text-muted-foreground mt-0.5">
                  Use my prompts and results (anonymized) to improve AI models.
                </p>
              </div>
            </label>
            <label className="flex items-start gap-3 rounded-md border p-3 hover:bg-muted/50 cursor-pointer">
              <Checkbox
                checked={allowShowcase}
                onCheckedChange={(v) => setAllowShowcase(!!v)}
                className="mt-0.5"
              />
              <div>
                <span className="font-medium">Allow showcase</span>
                <p className="text-xs text-muted-foreground mt-0.5">
                  May feature my generations in marketing or public gallery (with permission).
                </p>
              </div>
            </label>
          </div>

          <p className="text-xs text-muted-foreground">
            See our Data usage policy and Privacy policy (in Settings). GDPR & CCPA: you can withdraw or request deletion anytime.
          </p>

          {error && (
            <p className="text-sm text-destructive">{error}</p>
          )}
        </div>

        <DialogFooter className="flex gap-2 sm:gap-0">
          <Button variant="ghost" onClick={handleDecline} disabled={loading}>
            Maybe later
          </Button>
          <Button onClick={handleSubmit} disabled={loading}>
            {loading ? "Saving…" : "Save preferences"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
