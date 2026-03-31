/**
 * User Repository
 * 
 * Type-safe database operations for User model with transaction support.
 */

import { prisma, User, UserTier, Prisma } from '../index'

export class UserRepository {
  /**
   * Find user by Clerk ID
   */
  static async findByClerkId(clerkId: string): Promise<User | null> {
    return prisma.user.findUnique({
      where: { clerkId },
      include: {
        identities: {
          where: { isDeleted: false },
          orderBy: { createdAt: 'desc' },
        },
      },
    })
  }

  /**
   * Find user by email
   */
  static async findByEmail(email: string): Promise<User | null> {
    return prisma.user.findUnique({
      where: { email },
    })
  }

  /**
   * Find user by Stripe customer ID (for webhooks)
   */
  static async findByStripeCustomerId(stripeCustomerId: string): Promise<User | null> {
    return prisma.user.findUnique({
      where: { stripeCustomerId },
    })
  }

  /**
   * Find user by Stripe subscription ID (for subscription.deleted webhook)
   */
  static async findByStripeSubscriptionId(stripeSubscriptionId: string): Promise<User | null> {
    return prisma.user.findUnique({
      where: { stripeSubscriptionId },
    })
  }

  /**
   * Create new user
   */
  static async create(data: {
    email: string
    clerkId: string
    name?: string
    profileImageUrl?: string
  }): Promise<User> {
    return prisma.user.create({
      data: {
        ...data,
        tier: UserTier.FREE,
        creditsBalance: 15, // Initial free credits
      },
    })
  }

  /**
   * Update user credits (atomic)
   */
  static async updateCredits(
    userId: string,
    amount: number
  ): Promise<User> {
    return prisma.user.update({
      where: { id: userId },
      data: {
        creditsBalance: {
          increment: amount,
        },
      },
    })
  }

  /**
   * Deduct credits with validation
   */
  static async deductCredits(
    userId: string,
    amount: number
  ): Promise<{ success: boolean; user?: User; error?: string }> {
    try {
      // Use transaction for atomicity
      const user = await prisma.$transaction(async (tx) => {
        // Get current balance
        const currentUser = await tx.user.findUnique({
          where: { id: userId },
          select: { creditsBalance: true, isBanned: true },
        })

        if (!currentUser) {
          throw new Error('User not found')
        }

        if (currentUser.isBanned) {
          throw new Error('User is banned')
        }

        if (currentUser.creditsBalance < amount) {
          throw new Error('Insufficient credits')
        }

        // Deduct credits
        return tx.user.update({
          where: { id: userId },
          data: {
            creditsBalance: {
              decrement: amount,
            },
            totalCreditsSpent: {
              increment: amount,
            },
          },
        })
      })

      return { success: true, user }
    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Unknown error',
      }
    }
  }

  /**
   * Update user information
   */
  static async update(
    userId: string,
    data: {
      email?: string
      name?: string
      profileImageUrl?: string
    }
  ): Promise<User> {
    return prisma.user.update({
      where: { id: userId },
      data: {
        ...(data.email && { email: data.email }),
        ...(data.name !== undefined && { name: data.name }),
        ...(data.profileImageUrl !== undefined && { profileImageUrl: data.profileImageUrl }),
      },
    })
  }

  /**
   * Update tier
   */
  static async updateTier(userId: string, tier: UserTier): Promise<User> {
    return prisma.user.update({
      where: { id: userId },
      data: { tier },
    })
  }

  /**
   * Set Stripe subscription (after checkout or renewal)
   */
  static async updateStripeSubscription(
    userId: string,
    data: { stripeSubscriptionId: string; subscriptionEndsAt: Date }
  ): Promise<User> {
    return prisma.user.update({
      where: { id: userId },
      data: {
        stripeSubscriptionId: data.stripeSubscriptionId,
        subscriptionEndsAt: data.subscriptionEndsAt,
      },
    })
  }

  /**
   * Clear subscription and downgrade to FREE (cancel / payment failed)
   */
  static async clearStripeSubscription(userId: string): Promise<User> {
    return prisma.user.update({
      where: { id: userId },
      data: {
        stripeSubscriptionId: null,
        subscriptionEndsAt: null,
        tier: UserTier.FREE,
      },
    })
  }

  /**
   * Add strike to user
   */
  static async addStrike(
    userId: string,
    reason: string
  ): Promise<{ user: User; banned: boolean }> {
    return prisma.$transaction(async (tx) => {
      const user = await tx.user.update({
        where: { id: userId },
        data: {
          strikes: { increment: 1 },
          lastStrikeAt: new Date(),
        },
      })

      // Auto-ban if strikes >= 3
      if (user.strikes >= 3 && !user.isBanned) {
        const bannedUser = await tx.user.update({
          where: { id: userId },
          data: {
            isBanned: true,
            banReason: `Auto-banned after ${user.strikes} strikes. Last reason: ${reason}`,
            bannedAt: new Date(),
          },
        })
        return { user: bannedUser, banned: true }
      }

      return { user, banned: false }
    })
  }

  /**
   * Ban user
   */
  static async ban(userId: string, reason: string): Promise<User> {
    return prisma.user.update({
      where: { id: userId },
      data: {
        isBanned: true,
        banReason: reason,
        bannedAt: new Date(),
      },
    })
  }

  /**
   * Unban user
   */
  static async unban(userId: string): Promise<User> {
    return prisma.user.update({
      where: { id: userId },
      data: {
        isBanned: false,
        banReason: null,
        bannedAt: null,
        strikes: 0, // Reset strikes
      },
    })
  }

  /**
   * Get user stats
   */
  static async getStats(userId: string) {
    const [user, generationCount, identityCount] = await Promise.all([
      prisma.user.findUnique({
        where: { id: userId },
        select: {
          creditsBalance: true,
          totalGenerations: true,
          totalCreditsSpent: true,
          tier: true,
        },
      }),
      prisma.generation.count({
        where: { userId, isDeleted: false },
      }),
      prisma.identity.count({
        where: { userId, isDeleted: false },
      }),
    ])

    return {
      ...user,
      generationCount,
      identityCount,
    }
  }

  /**
   * Check if user can generate
   * 
   * NOTE: Credit checks are DISABLED during development/testing phase
   */
  static async canGenerate(
    userId: string,
    requiredCredits: number
  ): Promise<{ can: boolean; reason?: string }> {
    // DEVELOPMENT MODE: Skip credit checks for testing
    const SKIP_CREDIT_CHECKS = true // Set to false to enable credit checks
    
    if (SKIP_CREDIT_CHECKS) {
      console.log(`[DEV] Credit check skipped - required: ${requiredCredits}, user: ${userId}`)
      // Still check if user exists and is not banned
      const user = await prisma.user.findUnique({
        where: { id: userId },
        select: {
          isBanned: true,
        },
      })

      if (!user) {
        return { can: false, reason: 'User not found' }
      }

      if (user.isBanned) {
        return { can: false, reason: 'Account banned' }
      }

      return { can: true }
    }

    const user = await prisma.user.findUnique({
      where: { id: userId },
      select: {
        isBanned: true,
        creditsBalance: true,
        tier: true,
      },
    })

    if (!user) {
      return { can: false, reason: 'User not found' }
    }

    if (user.isBanned) {
      return { can: false, reason: 'Account banned' }
    }

    if (user.creditsBalance < requiredCredits) {
      return { can: false, reason: 'Insufficient credits' }
    }

    return { can: true }
  }
}
