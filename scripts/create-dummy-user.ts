/**
 * Script to create a dummy user for testing
 * Run with: npx tsx scripts/create-dummy-user.ts
 */

import { PrismaClient } from "@photogenius/database";
import bcrypt from "bcryptjs";

const prisma = new PrismaClient();

async function main() {
  const email = "dev@photogenius.local";
  const password = "password123"; // Simple password for testing
  const name = "Dev User";

  console.log("Creating dummy user...");

  // Check if user already exists
  const existing = await prisma.user.findUnique({
    where: { email },
  });

  if (existing) {
    console.log(`✅ User already exists: ${email}`);
    console.log(`   ID: ${existing.id}`);
    return;
  }

  // Hash password
  const passwordHash = await bcrypt.hash(password, 10);

  // Create user
  const user = await prisma.user.create({
    data: {
      email,
      name,
      passwordHash,
      credits: 1000,
    },
  });

  console.log(`✅ Dummy user created successfully!`);
  console.log(`   Email: ${email}`);
  console.log(`   Password: ${password}`);
  console.log(`   ID: ${user.id}`);
  console.log(`   Credits: ${user.credits}`);
}

main()
  .catch((error) => {
    console.error("Error creating dummy user:", error);
    process.exit(1);
  })
  .finally(async () => {
    await prisma.$disconnect();
  });
