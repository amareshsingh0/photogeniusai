/**
 * Transaction Repository
 * 
 * Type-safe database operations for Transaction model with atomic operations.
 */

import { 
  prisma, 
  Transaction, 
  TransactionType, 
  TransactionStatus,
  Prisma 
} from '../index'

export class TransactionRepository {
  /**
   * Create transaction
   */
  static async create(data: {
    userId: string
    type: TransactionType
    amount: number
    currency?: string
    creditsAdded?: number
    productId?: string
    productName?: string
    stripePaymentIntentId?: string
    stripeInvoiceId?: string
    status?: TransactionStatus
    metadata?: any
  }): Promise<Transaction> {
    // Get current balance
    const user = await prisma.user.findUnique({
      where: { id: data.userId },
      select: { creditsBalance: true },
    })

    return prisma.transaction.create({
      data: {
        userId: data.userId,
        type: data.type,
        amount: data.amount,
        currency: data.currency || 'USD',
        creditsAdded: data.creditsAdded,
        creditsBefore: user?.creditsBalance,
        creditsAfter: user?.creditsBalance && data.creditsAdded 
          ? user.creditsBalance + data.creditsAdded 
          : user?.creditsBalance,
        productId: data.productId,
        productName: data.productName,
        stripePaymentIntentId: data.stripePaymentIntentId,
        stripeInvoiceId: data.stripeInvoiceId,
        metadata: data.metadata as any,
        status: data.status ?? TransactionStatus.PENDING,
      },
    })
  }

  /**
   * Find by Stripe Invoice ID (idempotency for invoice.payment_succeeded)
   */
  static async findByStripeInvoiceId(invoiceId: string): Promise<Transaction | null> {
    return prisma.transaction.findUnique({
      where: { stripeInvoiceId: invoiceId },
    })
  }

  /**
   * Mark as completed
   */
  static async markCompleted(id: string): Promise<Transaction> {
    return prisma.$transaction(async (tx) => {
      const transaction = await tx.transaction.findUnique({
        where: { id },
      })

      if (!transaction) {
        throw new Error('Transaction not found')
      }

      // Update credits if applicable
      if (transaction.creditsAdded && transaction.creditsAdded > 0) {
        await tx.user.update({
          where: { id: transaction.userId },
          data: {
            creditsBalance: { increment: transaction.creditsAdded },
          },
        })
      }

      // Update transaction
      return tx.transaction.update({
        where: { id },
        data: {
          status: TransactionStatus.COMPLETED,
          completedAt: new Date(),
        },
      })
    })
  }

  /**
   * Mark as failed
   */
  static async markFailed(
    id: string,
    reason: string
  ): Promise<Transaction> {
    return prisma.transaction.update({
      where: { id },
      data: {
        status: TransactionStatus.FAILED,
        failureReason: reason,
      },
    })
  }

  /**
   * Process refund
   */
  static async refund(id: string): Promise<Transaction> {
    return prisma.$transaction(async (tx) => {
      const transaction = await tx.transaction.findUnique({
        where: { id },
      })

      if (!transaction) {
        throw new Error('Transaction not found')
      }

      if (transaction.status !== TransactionStatus.COMPLETED) {
        throw new Error('Can only refund completed transactions')
      }

      // Deduct credits if they were added
      if (transaction.creditsAdded && transaction.creditsAdded > 0) {
        await tx.user.update({
          where: { id: transaction.userId },
          data: {
            creditsBalance: { decrement: transaction.creditsAdded },
          },
        })
      }

      // Update transaction
      return tx.transaction.update({
        where: { id },
        data: {
          status: TransactionStatus.REFUNDED,
          refundedAt: new Date(),
        },
      })
    })
  }

  /**
   * Get user's transactions
   */
  static async findByUserId(
    userId: string,
    options?: {
      limit?: number
      offset?: number
      status?: TransactionStatus
    }
  ): Promise<Transaction[]> {
    const where: Prisma.TransactionWhereInput = { userId }

    if (options?.status) {
      where.status = options.status
    }

    return prisma.transaction.findMany({
      where,
      orderBy: { createdAt: 'desc' },
      take: options?.limit || 20,
      skip: options?.offset || 0,
    })
  }

  /**
   * Find by Stripe Payment Intent ID
   */
  static async findByStripePaymentIntent(
    paymentIntentId: string
  ): Promise<Transaction | null> {
    return prisma.transaction.findUnique({
      where: { stripePaymentIntentId: paymentIntentId },
    })
  }

  /**
   * Get revenue analytics
   */
  static async getRevenueAnalytics(period: 'day' | 'week' | 'month' | 'year') {
    const now = new Date()
    const startDate = new Date()

    switch (period) {
      case 'day':
        startDate.setDate(now.getDate() - 1)
        break
      case 'week':
        startDate.setDate(now.getDate() - 7)
        break
      case 'month':
        startDate.setMonth(now.getMonth() - 1)
        break
      case 'year':
        startDate.setFullYear(now.getFullYear() - 1)
        break
    }

    const [total, byType] = await Promise.all([
      prisma.transaction.aggregate({
        where: {
          status: TransactionStatus.COMPLETED,
          createdAt: { gte: startDate },
        },
        _sum: { amount: true },
        _count: true,
      }),
      prisma.transaction.groupBy({
        by: ['type'],
        where: {
          status: TransactionStatus.COMPLETED,
          createdAt: { gte: startDate },
        },
        _sum: { amount: true },
        _count: true,
      }),
    ])

    return {
      period,
      totalRevenue: total._sum.amount || 0,
      totalTransactions: total._count,
      byType: byType.map(item => ({
        type: item.type,
        revenue: item._sum.amount || 0,
        count: item._count,
      })),
    }
  }
}
