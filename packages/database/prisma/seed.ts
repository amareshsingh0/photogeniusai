import { PrismaClient, UserTier, GenerationMode, TrainingStatus } from '@prisma/client'

const prisma = new PrismaClient()

async function main() {
  console.log('🌱 Seeding database...')

  // Create test users
  const users = await Promise.all([
    prisma.user.create({
      data: {
        email: 'free@test.com',
        clerkId: 'user_free_test',
        name: 'Free User',
        tier: UserTier.FREE,
        creditsBalance: 15,
      },
    }),
    prisma.user.create({
      data: {
        email: 'pro@test.com',
        clerkId: 'user_pro_test',
        name: 'Pro User',
        tier: UserTier.PRO,
        creditsBalance: 200,
        stripeCustomerId: 'cus_pro_test',
        stripeSubscriptionId: 'sub_pro_test',
      },
    }),
    prisma.user.create({
      data: {
        email: 'premium@test.com',
        clerkId: 'user_premium_test',
        name: 'Premium User',
        tier: UserTier.PREMIUM,
        creditsBalance: 1000,
        stripeCustomerId: 'cus_premium_test',
        stripeSubscriptionId: 'sub_premium_test',
      },
    }),
  ])

  console.log(`✓ Created ${users.length} test users`)

  // Create test identities
  const identities = []
  for (const user of users.slice(0, 2)) {
    const identity = await prisma.identity.create({
      data: {
        userId: user.id,
        name: `${user.name}'s Identity`,
        referencePhotoUrls: JSON.parse(JSON.stringify([
          'https://example.com/photo1.jpg',
          'https://example.com/photo2.jpg',
        ])),
        referencePhotoCount: 2,
        trainingStatus: TrainingStatus.COMPLETED,
        trainingProgress: 100,
        qualityScore: 0.92,
        faceConsistencyScore: 0.88,
        consentGiven: true,
        consentTimestamp: new Date(),
        consentIpAddress: '127.0.0.1',
        consentUserAgent: 'PhotoGenius-Seed/1.0',
        consentVersion: 'v1.0',
      },
    })
    identities.push(identity)
  }

  console.log(`✓ Created ${identities.length} test identities`)

  // Create test generations
  const modes = [GenerationMode.REALISM, GenerationMode.CREATIVE, GenerationMode.ROMANTIC]
  for (const identity of identities) {
    for (let i = 0; i < 3; i++) {
      await prisma.generation.create({
        data: {
          userId: identity.userId,
          identityId: identity.id,
          mode: modes[i % 3],
          originalPrompt: `${modes[i % 3].toLowerCase()} portrait, soft lighting, high quality`,
          enhancedPrompt: `professional ${modes[i % 3].toLowerCase()} portrait, studio lighting, 8k`,
          negativePrompt: 'blurry, low quality',
          outputUrls: JSON.parse(JSON.stringify([
            `https://example.com/gen/${identity.id}-${i}-a.jpg`,
            `https://example.com/gen/${identity.id}-${i}-b.jpg`,
          ])),
          selectedOutputUrl: `https://example.com/gen/${identity.id}-${i}-a.jpg`,
          faceMatchScore: 85 + Math.floor(Math.random() * 10),
          aestheticScore: 7 + Math.random() * 2,
          technicalScore: 88 + Math.floor(Math.random() * 8),
          overallScore: 85 + Math.random() * 10,
          preGenSafetyPassed: true,
          postGenSafetyPassed: true,
          creditsUsed: 1,
          generationTimeSeconds: 12 + Math.random() * 10,
          gpuType: 'NVIDIA RTX 4090',
        },
      })
    }
  }

  console.log(`✓ Created test generations`)

  // Create consent records
  for (const user of users) {
    await prisma.consentRecord.create({
      data: {
        userId: user.id,
        consentVersion: 'v1.0',
        checkboxesChecked: JSON.parse(JSON.stringify([true, true, true])),
        ipAddress: '192.168.1.1',
        userAgent: 'Mozilla/5.0 (PhotoGenius Demo)',
        geoLocation: 'US',
      },
    })
  }

  console.log('✓ Created consent records')

  // Create transactions
  await prisma.transaction.create({
    data: {
      userId: users[1].id,
      type: 'SUBSCRIPTION',
      status: 'COMPLETED',
      amount: 1999,
      currency: 'USD',
      creditsAdded: 200,
      creditsBefore: 0,
      creditsAfter: 200,
      stripePaymentIntentId: 'pi_pro_seed_001',
      productName: 'Pro Monthly',
    },
  })

  await prisma.transaction.create({
    data: {
      userId: users[2].id,
      type: 'SUBSCRIPTION',
      status: 'COMPLETED',
      amount: 4999,
      currency: 'USD',
      creditsAdded: 1000,
      creditsBefore: 0,
      creditsAfter: 1000,
      stripePaymentIntentId: 'pi_premium_seed_001',
      productName: 'Premium Yearly',
    },
  })

  console.log('✓ Created transactions')

  // Create system config
  await prisma.systemConfig.createMany({
    data: [
      {
        key: 'CREDIT_COSTS',
        value: JSON.parse(JSON.stringify({
          REALISM: 1,
          CREATIVE: 3,
          ROMANTIC: 3,
        })),
        description: 'Credit costs per generation mode',
        isPublic: true,
      },
      {
        key: 'SAFETY_THRESHOLDS',
        value: JSON.parse(JSON.stringify({
          REALISM: { BLOCK: 0.60, QUARANTINE: 0.40 },
          CREATIVE: { BLOCK: 0.70, QUARANTINE: 0.50 },
          ROMANTIC: { BLOCK: 0.30, QUARANTINE: 0.20 },
        })),
        description: 'NSFW safety thresholds by mode',
        isPublic: false,
      },
    ],
  })

  console.log('✓ Created system config')

  console.log('✅ Seeding complete!')
  console.log(`   - ${users.length} users`)
  console.log(`   - ${identities.length} identities`)
  console.log(`   - ${identities.length * 3} generations`)
  console.log(`   - ${users.length} consent records`)
  console.log(`   - 2 transactions`)
  console.log(`   - 2 system configs`)
}

main()
  .catch((e) => {
    console.error('❌ Seeding failed:', e)
    process.exit(1)
  })
  .finally(async () => {
    await prisma.$disconnect()
  })
