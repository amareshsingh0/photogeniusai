import { NextResponse } from "next/server";
import Stripe from "stripe";
import { prisma } from "@/lib/db";
import {
  UserRepository,
  TransactionRepository,
} from "@photogenius/database";
import { TransactionType, TransactionStatus } from "@photogenius/database";
import { UserTier } from "@photogenius/database";
import { getCreditsAndTierForPrice, DEFAULT_CREDIT_PACK } from "@/lib/stripe-config";

const STRIPE_API_VERSION = "2023-10-16" as const;

/** In-memory rate limit: max requests per IP per window (resets on cold start). */
const RATE_LIMIT_WINDOW_MS = 60_000;
const RATE_LIMIT_MAX = 120;
const rateLimitMap = new Map<string, { count: number; resetAt: number }>();

function rateLimit(ip: string): boolean {
  const now = Date.now();
  let entry = rateLimitMap.get(ip);
  if (!entry) {
    rateLimitMap.set(ip, { count: 1, resetAt: now + RATE_LIMIT_WINDOW_MS });
    return true;
  }
  if (now >= entry.resetAt) {
    entry = { count: 1, resetAt: now + RATE_LIMIT_WINDOW_MS };
    rateLimitMap.set(ip, entry);
    return true;
  }
  entry.count++;
  return entry.count <= RATE_LIMIT_MAX;
}

/**
 * Stripe webhook: signature verification, idempotency, then event handling.
 * Events: checkout.session.completed, invoice.payment_succeeded,
 * invoice.payment_failed, customer.subscription.deleted.
 */
export async function POST(req: Request) {
  const secret = process.env.STRIPE_WEBHOOK_SECRET;
  if (!secret) {
    console.warn("STRIPE_WEBHOOK_SECRET missing; webhook skipped.");
    return NextResponse.json({ error: "Webhook not configured" }, { status: 500 });
  }

  const raw = await req.text();
  const sig = req.headers.get("stripe-signature");
  if (!sig) {
    return NextResponse.json({ error: "Missing stripe-signature" }, { status: 400 });
  }

  let event: Stripe.Event;
  try {
    const stripe = new Stripe(process.env.STRIPE_SECRET_KEY!, {
      apiVersion: STRIPE_API_VERSION,
    });
    event = stripe.webhooks.constructEvent(raw, sig, secret);
  } catch (e) {
    return NextResponse.json({ error: "Invalid signature" }, { status: 400 });
  }

  const ip =
    req.headers.get("x-forwarded-for")?.split(",")[0]?.trim() ||
    req.headers.get("x-real-ip") ||
    "unknown";
  if (!rateLimit(ip)) {
    return NextResponse.json({ error: "Too many requests" }, { status: 429 });
  }

  try {
    const existing = await prisma.stripeWebhookEvent.findUnique({
      where: { eventId: event.id },
    });
    if (existing) {
      return NextResponse.json({ received: true, duplicate: true });
    }
  } catch (e) {
    console.error("Idempotency check failed:", e);
    return NextResponse.json({ error: "Database error" }, { status: 500 });
  }

  const stripe = new Stripe(process.env.STRIPE_SECRET_KEY!, {
    apiVersion: STRIPE_API_VERSION,
  });

  const eventId = event.id;
  try {
    switch (event.type) {
      case "checkout.session.completed":
        await handleCheckoutSessionCompleted(
          stripe,
          event.data.object as Stripe.Checkout.Session,
          eventId
        );
        break;
      case "invoice.payment_succeeded":
        await handleInvoicePaymentSucceeded(
          stripe,
          event.data.object as Stripe.Invoice,
          eventId
        );
        break;
      case "invoice.payment_failed":
        await handleInvoicePaymentFailed(
          event.data.object as Stripe.Invoice,
          eventId
        );
        break;
      case "customer.subscription.deleted":
        await handleSubscriptionDeleted(
          event.data.object as Stripe.Subscription,
          eventId
        );
        break;
      default:
        break;
    }

    await prisma.stripeWebhookEvent.create({
      data: {
        eventId: event.id,
        eventType: event.type,
      },
    });
  } catch (e) {
    console.error(`Stripe webhook ${event.type} ${event.id} error:`, e);
    try {
      await prisma.auditLog.create({
        data: {
          actorType: "SYSTEM",
          action: "STRIPE_WEBHOOK_ERROR",
          resource: "webhook",
          resourceId: undefined,
          details: {
            eventId: event.id,
            eventType: event.type,
            error: e instanceof Error ? e.message : String(e),
          },
        },
      });
    } catch {
      // ignore audit failure
    }
    return NextResponse.json(
      { error: "Processing failed", message: e instanceof Error ? e.message : "Unknown error" },
      { status: 500 }
    );
  }

  return NextResponse.json({ received: true });
}

async function auditStripeEvent(
  eventId: string,
  eventType: string,
  userId: string,
  action: string,
  details: Record<string, unknown>
) {
  try {
    await prisma.auditLog.create({
      data: {
        actorType: "SYSTEM",
        actorId: userId,
        action: `STRIPE_${action}`,
        resource: "Transaction",
        resourceId: userId,
        details: { eventId, eventType, ...details },
      },
    });
  } catch {
    // ignore
  }
}

async function handleCheckoutSessionCompleted(
  stripe: Stripe,
  session: Stripe.Checkout.Session,
  eventId: string
) {
  const customerId =
    typeof session.customer === "string" ? session.customer : session.customer?.id;
  if (!customerId) return;

  const user = await UserRepository.findByStripeCustomerId(customerId);
  if (!user) {
    console.warn("Checkout completed but no user for customer:", customerId);
    return;
  }

  if (session.mode === "subscription" && session.subscription) {
    const subId =
      typeof session.subscription === "string"
        ? session.subscription
        : session.subscription.id;
    const subscription = await stripe.subscriptions.retrieve(subId, {
      expand: ["items.data.price", "latest_invoice"],
    });
    const item = subscription.items.data[0];
    const priceId = item?.price?.id;
    if (!priceId) return;

    const config = getCreditsAndTierForPrice(priceId);
    const credits = config?.credits ?? DEFAULT_CREDIT_PACK;
    const tier = config?.tier ?? UserTier.PRO;
    const productName = config?.productName ?? "Subscription";

    const latestInvoice = subscription.latest_invoice as Stripe.Invoice | null;
    const invoiceId =
      typeof latestInvoice === "string" ? latestInvoice : latestInvoice?.id;

    await prisma.$transaction(async (tx) => {
      if (invoiceId) {
        const existing = await tx.transaction.findUnique({
          where: { stripeInvoiceId: invoiceId },
        });
        if (existing) return;
      }

      const t = await tx.transaction.create({
        data: {
          userId: user.id,
          type: TransactionType.SUBSCRIPTION,
          amount: subscription.items.data[0]?.price?.unit_amount ?? 0,
          currency: "USD",
          creditsAdded: credits,
          productId: priceId,
          productName,
          stripeInvoiceId: invoiceId ?? undefined,
          status: TransactionStatus.COMPLETED,
        },
      });
      await tx.user.update({
        where: { id: user.id },
        data: {
          creditsBalance: { increment: credits },
          tier,
          stripeSubscriptionId: subscription.id,
          subscriptionEndsAt: new Date(subscription.current_period_end * 1000),
        },
      });
      await tx.transaction.update({
        where: { id: t.id },
        data: { completedAt: new Date() },
      });
    });
    await auditStripeEvent(
      eventId,
      "checkout.session.completed",
      user.id,
      "CHECKOUT_SUBSCRIPTION",
      { credits, tier, subscriptionId: session.subscription }
    );
    return;
  }

  const paymentIntentId =
    typeof session.payment_intent === "string"
      ? session.payment_intent
      : session.payment_intent?.id;
  if (!paymentIntentId) return;

  const existing = await TransactionRepository.findByStripePaymentIntent(
    paymentIntentId
  );
  if (existing) return;

  const amountTotal = session.amount_total ?? 0;
  const config = getCreditsAndTierForPrice(
    (session as unknown as { price_id?: string }).price_id ?? ""
  );
  const credits = config?.credits ?? DEFAULT_CREDIT_PACK;
  const productName = config?.productName ?? "Credit pack";

  const t = await TransactionRepository.create({
    userId: user.id,
    type: TransactionType.CREDIT_PACK,
    amount: amountTotal,
    creditsAdded: credits,
    productName,
    stripePaymentIntentId: paymentIntentId,
  });
  await TransactionRepository.markCompleted(t.id);
  await auditStripeEvent(
    eventId,
    "checkout.session.completed",
    user.id,
    "CHECKOUT_ONE_TIME",
    { credits, transactionId: t.id }
  );
}

async function handleInvoicePaymentSucceeded(
  stripe: Stripe,
  invoice: Stripe.Invoice,
  eventId: string
) {
  if (!invoice.customer || !invoice.subscription) return;
  const customerId =
    typeof invoice.customer === "string" ? invoice.customer : invoice.customer.id;
  const user = await UserRepository.findByStripeCustomerId(customerId);
  if (!user) return;

  const existing = await TransactionRepository.findByStripeInvoiceId(invoice.id);
  if (existing) return;

  let credits = DEFAULT_CREDIT_PACK;
  let productName = "Subscription renewal";
  let tier: UserTier = UserTier.PRO;

  if (invoice.lines?.data?.[0]?.price?.id) {
    const config = getCreditsAndTierForPrice(invoice.lines.data[0].price!.id);
    if (config) {
      credits = config.credits;
      productName = config.productName;
      tier = config.tier;
    }
  }

  const subId =
    typeof invoice.subscription === "string"
      ? invoice.subscription
      : invoice.subscription?.id;
  let subscriptionEndsAt: Date | null = null;
  if (subId) {
    try {
      const sub = await stripe.subscriptions.retrieve(subId);
      subscriptionEndsAt = new Date(sub.current_period_end * 1000);
    } catch {
      // ignore
    }
  }

  await prisma.$transaction(async (tx) => {
    const t = await tx.transaction.create({
      data: {
        userId: user.id,
        type: TransactionType.SUBSCRIPTION,
        amount: invoice.amount_paid ?? 0,
        currency: (invoice.currency ?? "usd").toUpperCase(),
        creditsAdded: credits,
        productId: invoice.id,
        productName,
        stripeInvoiceId: invoice.id,
        status: TransactionStatus.COMPLETED,
        completedAt: new Date(),
      },
    });
    await tx.user.update({
      where: { id: user.id },
      data: {
        creditsBalance: { increment: credits },
        tier,
        ...(subscriptionEndsAt && {
          subscriptionEndsAt,
        }),
      },
    });
  });
  await auditStripeEvent(
    eventId,
    "invoice.payment_succeeded",
    user.id,
    "INVOICE_PAID",
    { credits, invoiceId: invoice.id }
  );
}

async function handleInvoicePaymentFailed(
  invoice: Stripe.Invoice,
  eventId: string
) {
  if (!invoice.customer) return;
  const customerId =
    typeof invoice.customer === "string" ? invoice.customer : invoice.customer.id;
  const user = await UserRepository.findByStripeCustomerId(customerId);
  if (!user) return;

  await UserRepository.clearStripeSubscription(user.id);

  await prisma.transaction.create({
    data: {
      userId: user.id,
      type: TransactionType.SUBSCRIPTION,
      amount: invoice.amount_due ?? 0,
      currency: (invoice.currency ?? "usd").toUpperCase(),
      status: TransactionStatus.FAILED,
      stripeInvoiceId: invoice.id,
      failureReason: "Stripe invoice.payment_failed",
    },
  });
  await auditStripeEvent(
    eventId,
    "invoice.payment_failed",
    user.id,
    "INVOICE_FAILED",
    { invoiceId: invoice.id }
  );
}

async function handleSubscriptionDeleted(
  subscription: Stripe.Subscription,
  eventId: string
) {
  const user = await UserRepository.findByStripeSubscriptionId(subscription.id);
  if (!user) return;
  await UserRepository.clearStripeSubscription(user.id);
  await auditStripeEvent(
    eventId,
    "customer.subscription.deleted",
    user.id,
    "SUBSCRIPTION_CANCELLED",
    { subscriptionId: subscription.id }
  );
}
