/**
 * Environment validation - runs on import
 * This file is imported in next.config.js to validate env vars at build time
 */
import { env } from './env'

// Export validated env for use in config
export { env }
