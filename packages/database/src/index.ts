import { PrismaClient } from '@prisma/client'

// Singleton pattern for Prisma Client
declare global {
  var prisma: PrismaClient | undefined
}

export const prisma = global.prisma || new PrismaClient({
  log: process.env.NODE_ENV === 'development' 
    ? ['query', 'error', 'warn'] 
    : ['error'],
})

if (process.env.NODE_ENV !== 'production') {
  global.prisma = prisma
}

// Export types
export * from '@prisma/client'

// Export repositories
export { UserRepository } from './repositories/user'
export { IdentityRepository } from './repositories/identity'
export { GenerationRepository } from './repositories/generation'
export { TransactionRepository } from './repositories/transaction'
