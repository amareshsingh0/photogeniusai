/**
 * Identity Repository
 * 
 * Type-safe database operations for Identity model.
 */

import { prisma, Identity, TrainingStatus, Prisma } from '../index'

export class IdentityRepository {
  /**
   * Create new identity
   */
  static async create(data: {
    userId: string
    name: string
    description?: string
    referencePhotoUrls: string[]
  }): Promise<Identity> {
    return prisma.identity.create({
      data: {
        userId: data.userId,
        name: data.name,
        description: data.description,
        referencePhotoUrls: data.referencePhotoUrls as any,
        referencePhotoCount: data.referencePhotoUrls.length,
        trainingStatus: TrainingStatus.PENDING,
      },
    })
  }

  /**
   * Get identity by ID
   */
  static async findById(id: string): Promise<Identity | null> {
    return prisma.identity.findFirst({
      where: { id, isDeleted: false },
      include: {
        user: {
          select: {
            id: true,
            email: true,
            name: true,
            tier: true,
          },
        },
      },
    })
  }

  /**
   * Get user's identities
   */
  static async findByUserId(userId: string): Promise<Identity[]> {
    return prisma.identity.findMany({
      where: { userId, isDeleted: false },
      orderBy: { createdAt: 'desc' },
    })
  }

  /**
   * Update training status
   */
  static async updateTrainingStatus(
    id: string,
    status: TrainingStatus,
    progress: number,
    error?: string
  ): Promise<Identity> {
    const updateData: Prisma.IdentityUpdateInput = {
      trainingStatus: status,
      trainingProgress: progress,
    }

    if (status === TrainingStatus.TRAINING && progress === 0) {
      updateData.trainingStartedAt = new Date()
    }

    if (status === TrainingStatus.COMPLETED) {
      updateData.trainingCompletedAt = new Date()
      updateData.trainingProgress = 100
    }

    if (status === TrainingStatus.FAILED) {
      updateData.trainingError = error
    }

    return prisma.identity.update({
      where: { id },
      data: updateData,
    })
  }

  /**
   * Save LoRA model info
   */
  static async saveLoraModel(
    id: string,
    data: {
      loraFilePath: string
      loraFileSize: number
      faceEmbedding: number[]
      qualityScore: number
      faceConsistencyScore: number
    }
  ): Promise<Identity> {
    return prisma.identity.update({
      where: { id },
      data: {
        loraFilePath: data.loraFilePath,
        loraFileSize: data.loraFileSize,
        faceEmbedding: data.faceEmbedding as any,
        qualityScore: data.qualityScore,
        faceConsistencyScore: data.faceConsistencyScore,
        trainingStatus: TrainingStatus.COMPLETED,
        trainingCompletedAt: new Date(),
      },
    })
  }

  /**
   * Record consent
   */
  static async recordConsent(
    id: string,
    ipAddress: string,
    userAgent: string
  ): Promise<Identity> {
    return prisma.identity.update({
      where: { id },
      data: {
        consentGiven: true,
        consentTimestamp: new Date(),
        consentIpAddress: ipAddress,
        consentUserAgent: userAgent,
        consentVersion: 'v1.0',
      },
    })
  }

  /**
   * Check if identity is ready for generation
   */
  static async isReady(id: string): Promise<{ ready: boolean; reason?: string }> {
    const identity = await prisma.identity.findUnique({
      where: { id },
      select: {
        trainingStatus: true,
        consentGiven: true,
        loraFilePath: true,
        isDeleted: true,
      },
    })

    if (!identity) {
      return { ready: false, reason: 'Identity not found' }
    }

    if (identity.isDeleted) {
      return { ready: false, reason: 'Identity deleted' }
    }

    if (!identity.consentGiven) {
      return { ready: false, reason: 'Consent not given' }
    }

    if (identity.trainingStatus !== TrainingStatus.COMPLETED) {
      return { ready: false, reason: 'Training not completed' }
    }

    if (!identity.loraFilePath) {
      return { ready: false, reason: 'LoRA model not available' }
    }

    return { ready: true }
  }

  /**
   * Increment usage counter
   */
  static async incrementUsage(id: string): Promise<void> {
    await prisma.identity.update({
      where: { id },
      data: {
        totalGenerations: { increment: 1 },
        lastUsedAt: new Date(),
      },
    })
  }

  /**
   * Soft delete identity
   */
  static async softDelete(id: string): Promise<Identity> {
    return prisma.identity.update({
      where: { id },
      data: {
        isDeleted: true,
        deletedAt: new Date(),
      },
    })
  }

  /**
   * Get training queue position
   */
  static async getQueuePosition(id: string): Promise<number> {
    const identity = await prisma.identity.findUnique({
      where: { id },
      select: { createdAt: true },
    })

    if (!identity) return -1

    const position = await prisma.identity.count({
      where: {
        trainingStatus: TrainingStatus.PENDING,
        createdAt: { lt: identity.createdAt },
      },
    })

    return position + 1
  }
}
