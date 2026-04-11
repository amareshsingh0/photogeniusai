/**
 * Script to make a user an admin
 * Run with: npx tsx scripts/make-admin.ts <email>
 */

import { PrismaClient } from "@photogenius/database";

const prisma = new PrismaClient();

async function main() {
  const email = process.argv[2];

  if (!email) {
    console.error("❌ Error: Email argument required");
    console.log("Usage: npx tsx scripts/make-admin.ts <email>");
    console.log("Example: npx tsx scripts/make-admin.ts dev@photogenius.local");
    process.exit(1);
  }

  console.log(`Making ${email} an admin...`);

  // Find user
  const user = await prisma.user.findUnique({
    where: { email: email.toLowerCase() },
  });

  if (!user) {
    console.error(`❌ User not found: ${email}`);
    process.exit(1);
  }

  // Update user role to ADMIN
  const updatedUser = await prisma.user.update({
    where: { id: user.id },
    data: { role: "ADMIN" },
  });

  console.log(`✅ User ${email} is now an ADMIN!`);
  console.log(`   ID: ${updatedUser.id}`);
  console.log(`   Role: ${updatedUser.role}`);
  console.log("");
  console.log("Access admin dashboard at: http://localhost:3002/admin");
}

main()
  .catch((error) => {
    console.error("Error:", error);
    process.exit(1);
  })
  .finally(async () => {
    await prisma.$disconnect();
  });
