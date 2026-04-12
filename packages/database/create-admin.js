const { PrismaClient } = require("@prisma/client");
const bcrypt = require("bcryptjs");
const prisma = new PrismaClient();
async function main() {
  const hash = await bcrypt.hash("password123", 10);
  const user = await prisma.user.upsert({
    where: { email: "dev@photogenius.local" },
    update: { passwordHash: hash, role: "ADMIN", creditsBalance: 1000, name: "Admin Dev" },
    create: { email: "dev@photogenius.local", name: "Admin Dev", passwordHash: hash, role: "ADMIN", creditsBalance: 1000 }
  });
  console.log("Admin created:", user.email, "Role:", user.role, "ID:", user.id);
}
main().then(() => prisma.$disconnect()).catch(e => { console.error(e); prisma.$disconnect(); });
