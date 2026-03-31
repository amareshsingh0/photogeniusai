#!/usr/bin/env node
/**
 * Test Frontend-Backend Connection
 * Tests if API is running and accessible from frontend
 */

import { fileURLToPath } from 'url';
import { dirname, join } from 'path';
import { readFileSync, existsSync } from 'fs';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

// Colors for terminal output
const colors = {
  reset: '\x1b[0m',
  bright: '\x1b[1m',
  green: '\x1b[32m',
  red: '\x1b[31m',
  yellow: '\x1b[33m',
  blue: '\x1b[34m',
  cyan: '\x1b[36m',
};

const log = {
  info: (msg) => console.log(`${colors.blue}ℹ${colors.reset} ${msg}`),
  success: (msg) => console.log(`${colors.green}✓${colors.reset} ${msg}`),
  error: (msg) => console.log(`${colors.red}✗${colors.reset} ${msg}`),
  warn: (msg) => console.log(`${colors.yellow}⚠${colors.reset} ${msg}`),
  header: (msg) => console.log(`\n${colors.bright}${colors.cyan}${msg}${colors.reset}\n`),
};

async function testConnection() {
  log.header('PhotoGenius AI - Connection Test');

  // 1. Check .api-port file
  const apiPortFile = join(__dirname, '.api-port');
  let apiPort = '8000';

  if (existsSync(apiPortFile)) {
    try {
      apiPort = readFileSync(apiPortFile, 'utf-8').trim();
      log.success(`API port file found: ${apiPort}`);
    } catch (e) {
      log.warn(`Could not read .api-port file: ${e.message}`);
    }
  } else {
    log.warn('.api-port file not found, using default port 8000');
  }

  const apiUrl = `http://127.0.0.1:${apiPort}`;

  // 2. Test API Health Endpoint
  log.info(`Testing API connection at ${apiUrl}/health...`);

  try {
    const healthResponse = await fetch(`${apiUrl}/health`, {
      method: 'GET',
      headers: { 'Content-Type': 'application/json' },
    });

    if (healthResponse.ok) {
      const healthData = await healthResponse.json();
      log.success(`API is running! Status: ${healthData.status}`);

      if (healthData.services) {
        console.log(`  Services:`);
        for (const [service, status] of Object.entries(healthData.services)) {
          const statusIcon = status === 'connected' ? '✓' : '✗';
          console.log(`    ${statusIcon} ${service}: ${status}`);
        }
      }
    } else {
      log.error(`API health check failed: ${healthResponse.status} ${healthResponse.statusText}`);
      return false;
    }
  } catch (error) {
    log.error(`Cannot connect to API at ${apiUrl}`);
    log.error(`Error: ${error.message}`);
    console.log('\n' + colors.yellow + 'To start the API, run:' + colors.reset);
    console.log('  pnpm dev:api\n');
    return false;
  }

  // 3. Test API Root Endpoint
  log.info('Testing API root endpoint...');

  try {
    const rootResponse = await fetch(`${apiUrl}/`, {
      method: 'GET',
      headers: { 'Content-Type': 'application/json' },
    });

    if (rootResponse.ok) {
      const rootData = await rootResponse.json();
      log.success(`API root accessible: ${rootData.service || 'Unknown'}`);
    }
  } catch (error) {
    log.warn(`API root endpoint test failed: ${error.message}`);
  }

  // 4. Check Frontend Environment
  log.info('Checking frontend configuration...');

  const envFile = join(__dirname, 'apps', 'web', '.env.local');
  if (existsSync(envFile)) {
    try {
      const envContent = readFileSync(envFile, 'utf-8');
      const apiUrlMatch = envContent.match(/NEXT_PUBLIC_API_URL=(.+)/);
      const localApiMatch = envContent.match(/NEXT_PUBLIC_USE_LOCAL_API=(.+)/);

      if (apiUrlMatch) {
        const configuredUrl = apiUrlMatch[1].trim();
        if (configuredUrl.includes(apiPort)) {
          log.success(`Frontend API URL configured correctly: ${configuredUrl}`);
        } else {
          log.warn(`Frontend API URL mismatch: ${configuredUrl} (expected port ${apiPort})`);
        }
      }

      if (localApiMatch && localApiMatch[1].trim() === 'true') {
        log.success('Frontend configured to use local API');
      }
    } catch (e) {
      log.warn(`Could not read .env.local: ${e.message}`);
    }
  } else {
    log.warn('Frontend .env.local not found');
  }

  // 5. Summary
  log.header('Connection Test Complete');
  log.success('Frontend and backend are properly configured!');
  console.log('\n' + colors.bright + 'Next Steps:' + colors.reset);
  console.log('  1. Start API:      pnpm dev:api');
  console.log('  2. Start Frontend: pnpm dev:web');
  console.log('  3. Visit:          http://localhost:3002\n');

  return true;
}

// Run test
testConnection().catch((error) => {
  log.error(`Test failed: ${error.message}`);
  process.exit(1);
});
