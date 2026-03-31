# Database Package

Prisma schema and database management for PhotoGenius AI.

## Setup

1. **Install dependencies:**
   ```bash
   pnpm install
   ```

2. **Generate Prisma Client:**
   ```bash
   pnpm db:generate
   ```

3. **Push schema to database:**
   ```bash
   # For fresh database (development)
   pnpm db:push:force
   
   # For existing database (creates migration)
   pnpm db:migrate
   ```

4. **Seed database:**
   ```bash
   pnpm db:seed
   ```

## Available Scripts

- `db:generate` - Generate Prisma Client from schema
- `db:push` - Push schema changes to database (non-destructive)
- `db:push:force` - Force push schema (⚠️ **WARNING**: Drops all data!)
- `db:migrate` - Create and apply migration
- `db:seed` - Seed database with test data
- `db:studio` - Open Prisma Studio (database GUI)
- `db:reset` - Reset database (drops all data and runs migrations + seed)

## Environment Variables

The scripts automatically load `DATABASE_URL` from the root `.env` file.

Make sure your `.env` file contains:
```env
DATABASE_URL=postgresql://user:password@host:5432/database
```

## Troubleshooting

### Schema conflicts with existing data

If you see errors about "cannot be executed" when running `db:push`, you have two options:

1. **Development (data loss OK):**
   ```bash
   pnpm db:push:force
   ```

2. **Production (preserve data):**
   ```bash
   pnpm db:migrate
   ```
   This creates a proper migration that handles data transformation.

### DATABASE_URL not found

Make sure:
- Root `.env` file exists
- `DATABASE_URL` is set in root `.env`
- You're running commands from `packages/database` directory
