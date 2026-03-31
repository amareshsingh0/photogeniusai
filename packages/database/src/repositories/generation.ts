/**
 * Generation Repository
 * 
 * Type-safe database operations for Generation model.
 */

import { prisma, Generation, GenerationMode, Prisma } from '../index'

export class GenerationRepository {
  /**
   * Create generation record
   */
  static async create(data: {
    userId: string
    identityId: string
    mode: GenerationMode
    originalPrompt: string
    enhancedPrompt?: string
    negativePrompt?: string
    creditsUsed: number
    seed?: bigint
  }): Promise<Generation> {
    return prisma.generation.create({
      data: {
        userId: data.userId,
        identityId: data.identityId,
        mode: data.mode,
        originalPrompt: data.originalPrompt,
        enhancedPrompt: data.enhancedPrompt,
        negativePrompt: data.negativePrompt,
        creditsUsed: data.creditsUsed,
        seed: data.seed,
        outputUrls: [] as any,
        preGenSafetyPassed: false,
        postGenSafetyPassed: false,
      },
    })
  }

  /**
   * Update with pre-generation safety check
   */
  static async updatePreGenSafety(
    id: string,
    passed: boolean,
    violations?: any
  ): Promise<Generation> {
    return prisma.generation.update({
      where: { id },
      data: {
        preGenSafetyPassed: passed,
        preGenViolations: violations as any,
      },
    })
  }

  /**
   * Update with generation results
   */
  static async updateResults(
    id: string,
    data: {
      outputUrls: string[]
      faceMatchScore?: number
      aestheticScore?: number
      technicalScore?: number
      overallScore?: number
      generationTimeSeconds: number
      gpuType?: string
    }
  ): Promise<Generation> {
    return prisma.generation.update({
      where: { id },
      data: {
        outputUrls: data.outputUrls as any,
        faceMatchScore: data.faceMatchScore,
        aestheticScore: data.aestheticScore,
        technicalScore: data.technicalScore,
        overallScore: data.overallScore,
        generationTimeSeconds: data.generationTimeSeconds,
        gpuType: data.gpuType,
      },
    })
  }

  /**
   * Update post-generation safety
   */
  static async updatePostGenSafety(
    id: string,
    passed: boolean,
    violations?: any,
    quarantine: boolean = false,
    quarantineReason?: string
  ): Promise<Generation> {
    return prisma.generation.update({
      where: { id },
      data: {
        postGenSafetyPassed: passed,
        postGenViolations: violations as any,
        isQuarantined: quarantine,
        quarantineReason,
        quarantinedAt: quarantine ? new Date() : null,
      },
    })
  }

  /**
   * Get user's generations
   */
  static async findByUserId(
    userId: string,
    options?: {
      limit?: number
      offset?: number
      mode?: GenerationMode
      includeQuarantined?: boolean
    }
  ): Promise<Generation[]> {
    const where: Prisma.GenerationWhereInput = {
      userId,
      isDeleted: false,
    }

    if (options?.mode) {
      where.mode = options.mode
    }

    if (!options?.includeQuarantined) {
      where.isQuarantined = false
    }

    return prisma.generation.findMany({
      where,
      orderBy: { createdAt: 'desc' },
      take: options?.limit || 20,
      skip: options?.offset || 0,
      include: {
        identity: {
          select: {
            id: true,
            name: true,
          },
        },
      },
    })
  }

  /**
   * Get generation by ID
   */
  static async findById(id: string): Promise<Generation | null> {
    return prisma.generation.findFirst({
      where: { id, isDeleted: false },
      include: {
        identity: true,
        user: {
          select: {
            id: true,
            email: true,
            name: true,
          },
        },
      },
    })
  }

  /**
   * Mark as favorite
   */
  static async toggleFavorite(
    id: string,
    isFavorite: boolean
  ): Promise<Generation> {
    return prisma.generation.update({
      where: { id },
      data: { isFavorite },
    })
  }

  /**
   * Select output
   */
  static async selectOutput(
    id: string,
    url: string
  ): Promise<Generation> {
    return prisma.generation.update({
      where: { id },
      data: { selectedOutputUrl: url },
    })
  }

  /**
   * Increment download count
   */
  static async incrementDownload(id: string): Promise<void> {
    await prisma.generation.update({
      where: { id },
      data: { downloadCount: { increment: 1 } },
    })
  }

  /**
   * Get quarantined generations for review
   */
  static async getQuarantined(limit: number = 50): Promise<Generation[]> {
    return prisma.generation.findMany({
      where: {
        isQuarantined: true,
        reviewedAt: null,
      },
      orderBy: { quarantinedAt: 'desc' },
      take: limit,
      include: {
        user: {
          select: {
            id: true,
            email: true,
            strikes: true,
          },
        },
      },
    })
  }

  /**
   * Review quarantined generation
   */
  static async reviewQuarantined(
    id: string,
    reviewedBy: string,
    approved: boolean,
    notes?: string
  ): Promise<Generation> {
    return prisma.generation.update({
      where: { id },
      data: {
        reviewedBy,
        reviewedAt: new Date(),
        isQuarantined: !approved,
        // Add review notes to violations
        postGenViolations: {
          reviewNotes: notes,
          approved,
        } as any,
      },
    })
  }

  /**
   * Soft delete
   */
  static async softDelete(id: string): Promise<Generation> {
    return prisma.generation.update({
      where: { id },
      data: {
        isDeleted: true,
        deletedAt: new Date(),
      },
    })
  }

  /**
   * Get analytics
   */
  static async getAnalytics(userId: string) {
    const [total, byMode, avgScores] = await Promise.all([
      prisma.generation.count({
        where: { userId, isDeleted: false },
      }),
      prisma.generation.groupBy({
        by: ['mode'],
        where: { userId, isDeleted: false },
        _count: true,
      }),
      prisma.generation.aggregate({
        where: {
          userId,
          isDeleted: false,
          postGenSafetyPassed: true,
        },
        _avg: {
          faceMatchScore: true,
          aestheticScore: true,
          technicalScore: true,
          overallScore: true,
        },
      }),
    ])

    return {
      total,
      byMode: byMode.reduce((acc, item) => {
        acc[item.mode] = item._count
        return acc
      }, {} as Record<string, number>),
      averageScores: avgScores._avg,
    }
  }
}
