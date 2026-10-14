import { useState, useEffect } from "react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  getStoredMapApiKey,
  getStoredMapProvider,
  getStoredCustomStyleUrl,
  saveMapConfig,
  resetMapConfig,
  type MapProvider,
} from "@/lib/mapConfig";
import { Key, ShieldCheck, MapPin, ExternalLink, RotateCcw } from "lucide-react";
import { toast } from "sonner";

interface MapKeyDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function MapKeyDialog({ open, onOpenChange }: MapKeyDialogProps) {
  const [apiKey, setApiKey] = useState("");
  const [provider, setProvider] = useState<MapProvider>("carto_esri");
  const [customUrl, setCustomUrl] = useState("");
  const [envKeyActive, setEnvKeyActive] = useState(false);

  useEffect(() => {
    if (open) {
      setApiKey(getStoredMapApiKey());
      setProvider(getStoredMapProvider());
      setCustomUrl(getStoredCustomStyleUrl());

      const envKey =
        (import.meta.env["VITE_MAP_API_KEY"] as string | undefined) ??
        (import.meta.env["VITE_MAPTILER_API_KEY"] as string | undefined) ??
        (import.meta.env["VITE_MAPBOX_TOKEN"] as string | undefined);
      setEnvKeyActive(Boolean(envKey && envKey.trim()));
    }
  }, [open]);

  const handleSave = () => {
    saveMapConfig(apiKey, provider, customUrl);
    toast.success("Tactical map configuration updated");
    onOpenChange(false);
  };

  const handleReset = () => {
    resetMapConfig();
    setApiKey("");
    setProvider("carto_esri");
    setCustomUrl("");
    toast.info("Map configuration reset to default zero-cost tiles");
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md border-border bg-[#0E0E0E] text-[#E0E0E0]">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 font-mono text-sm tracking-wider uppercase text-white">
            <Key className="size-4 text-primary" />
            Tactical Map API Key & Provider
          </DialogTitle>
          <DialogDescription className="text-xs text-muted-foreground">
            Configure MapTiler, Mapbox, or custom vector/raster tile providers. If unset, DOIP uses
            the default free Carto Dark Matter + Esri World Imagery basemap.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-2 text-xs">
          <div className="space-y-1.5">
            <Label className="font-mono text-[11px] uppercase tracking-wider text-muted-foreground">
              Map Provider
            </Label>
            <div className="grid grid-cols-2 gap-2">
              {[
                { id: "carto_esri", label: "Default (Free / No Key)", desc: "Carto + Esri" },
                { id: "maptiler", label: "MapTiler", desc: "Vector + Satellite" },
                { id: "mapbox", label: "Mapbox", desc: "Dark + Satellite" },
                { id: "custom", label: "Custom Style URL", desc: "Self-hosted / Other" },
              ].map((item) => (
                <button
                  key={item.id}
                  type="button"
                  onClick={() => setProvider(item.id as MapProvider)}
                  className={`flex flex-col items-start rounded border p-2 text-left transition-colors ${
                    provider === item.id
                      ? "border-primary bg-primary/10 text-white"
                      : "border-border/60 bg-surface hover:border-border"
                  }`}
                >
                  <span className="font-mono font-medium text-[11px]">{item.label}</span>
                  <span className="text-[10px] text-muted-foreground">{item.desc}</span>
                </button>
              ))}
            </div>
          </div>

          {provider !== "carto_esri" && (
            <div className="space-y-1.5">
              <div className="flex items-center justify-between">
                <Label className="font-mono text-[11px] uppercase tracking-wider text-muted-foreground">
                  {provider === "mapbox"
                    ? "Mapbox Access Token"
                    : provider === "maptiler"
                      ? "MapTiler API Key"
                      : "API Key / Token"}
                </Label>
                {provider === "maptiler" && (
                  <a
                    href="https://cloud.maptiler.com/account/keys/"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1 font-mono text-[10px] text-primary hover:underline"
                  >
                    Get MapTiler Key <ExternalLink className="size-2.5" />
                  </a>
                )}
                {provider === "mapbox" && (
                  <a
                    href="https://account.mapbox.com/access-tokens/"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1 font-mono text-[10px] text-primary hover:underline"
                  >
                    Get Mapbox Token <ExternalLink className="size-2.5" />
                  </a>
                )}
              </div>
              <Input
                type="text"
                value={apiKey}
                onChange={(e) => setApiKey(e.target.value)}
                placeholder={
                  provider === "mapbox"
                    ? "pk.eyJ1Ijo..."
                    : provider === "maptiler"
                      ? "e.g. kA9j2..."
                      : "Enter API key"
                }
                className="font-mono text-xs bg-black/50 border-border"
              />
            </div>
          )}

          {provider === "custom" && (
            <div className="space-y-1.5">
              <Label className="font-mono text-[11px] uppercase tracking-wider text-muted-foreground">
                Custom Map Style URL
              </Label>
              <Input
                type="text"
                value={customUrl}
                onChange={(e) => setCustomUrl(e.target.value)}
                placeholder="https://.../style.json?key={key}"
                className="font-mono text-xs bg-black/50 border-border"
              />
              <p className="text-[10px] text-muted-foreground">
                You can use &#123;key&#125; placeholder in the URL for your API key.
              </p>
            </div>
          )}

          {envKeyActive && (
            <div className="flex items-center gap-1.5 rounded border border-emerald-500/30 bg-emerald-500/10 p-2 text-emerald-400">
              <ShieldCheck className="size-4 shrink-0" />
              <span className="text-[11px]">
                Environment API key detected in <code className="font-mono">.env</code>.
              </span>
            </div>
          )}
        </div>

        <DialogFooter className="flex items-center justify-between sm:justify-between border-t border-border/40 pt-3">
          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={handleReset}
            className="font-mono text-xs text-muted-foreground hover:text-white"
          >
            <RotateCcw className="mr-1.5 size-3.5" />
            Reset Default
          </Button>
          <div className="flex items-center gap-2">
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => onOpenChange(false)}
              className="font-mono text-xs"
            >
              Cancel
            </Button>
            <Button
              type="button"
              size="sm"
              onClick={handleSave}
              className="font-mono text-xs bg-primary text-black hover:bg-primary/90 font-semibold"
            >
              Save & Apply
            </Button>
          </div>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
