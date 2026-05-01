/**
 * Stripe product/price mapping for webhooks.
 * Env: STRIPE_PRICE_PRO=price_xxx, STRIPE_CREDITS_PRO=100, STRIPE_NAME_PRO=Pro Monthly
 *      STRIPE_PRICE_PREMIUM=price_yyy, STRIPE_CREDITS_PREMIUM=500, etc.
 */

import { UserTier } from "@photogenius/database";

export interface PriceConfig {
  tier: UserTier;
  credits: number;
  productName: string;
}

let _priceMap: Record<string, PriceConfig> | null = null;

function buildPriceMap(): Record<string, PriceConfig> {
  if (_priceMap) return _priceMap;
  const map: Record<string, PriceConfig> = {};
  for (const key of Object.keys(process.env)) {
    if (!key.startsWith("STRIPE_PRICE_")) continue;
    const suffix = key.replace("STRIPE_PRICE_", "");
    const priceId = process.env[key];
    if (!priceId || !priceId.startsWith("price_")) continue;
    const creditsKey = `STRIPE_CREDITS_${suffix}`;
    const nameKey = `STRIPE_NAME_${suffix}`;
    const credits = parseInt(process.env[creditsKey] ?? "0", 10);
    const name = process.env[nameKey] ?? suffix.replace(/_/g, " ");
    const tier =
      suffix.includes("PREMIUM") ? UserTier.PREMIUM
      : suffix.includes("PRO") ? UserTier.PRO
      : suffix.includes("FAST") ? UserTier.FAST
      : UserTier.FREE;
    map[priceId] = { tier, credits: credits || 100, productName: name };
  }
  _priceMap = map;
  return map;
}

export function getCreditsAndTierForPrice(priceId: string): PriceConfig | null {
  const map = buildPriceMap();
  if (map[priceId]) return map[priceId];
  // Dev fallback: grant default credits and PRO tier for any unknown price
  if (process.env.NODE_ENV !== "production") {
    return {
      tier: UserTier.PRO,
      credits: parseInt(process.env.STRIPE_DEFAULT_CREDIT_PACK ?? "50", 10),
      productName: "Dev purchase",
    };
  }
  return null;
}

export const DEFAULT_CREDIT_PACK = parseInt(process.env.STRIPE_DEFAULT_CREDIT_PACK ?? "50", 10);
