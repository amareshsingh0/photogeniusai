/**
 * Unified Cloud Configuration
 *
 * Project setup is AWS-only. Supports:
 * - AWS Lambda/SageMaker (default for AI/GPU workloads)
 * - FastAPI backend (single backend for generation + safety)
 * - Optional: GCP, Lightning, local
 *
 * Usage:
 *   import { getServiceUrl, CloudProvider } from "@/lib/cloud-config";
 *   const url = getServiceUrl("generation");
 */

export type CloudProvider = "modal" | "aws" | "gcp" | "lightning" | "local" | "backend";

export type ServiceName =
  | "safety"
  | "generation"
  | "refinement"
  | "training"
  | "orchestrator"
  | "quality"
  | "identity"
  | "realtime";

// Environment variable detection for cloud provider
function detectProvider(): CloudProvider {
  // Explicit provider (recommended for AWS / local FastAPI)
  const explicitProvider = process.env.CLOUD_PROVIDER?.toLowerCase();
  if (explicitProvider && ["modal", "aws", "gcp", "lightning", "local", "backend"].includes(explicitProvider)) {
    return explicitProvider as CloudProvider;
  }

  // Backend: use FastAPI at NEXT_PUBLIC_API_URL / FASTAPI_URL for generation + safety
  if (
    process.env.USE_FASTAPI_BACKEND === "true" ||
    process.env.NEXT_PUBLIC_USE_FASTAPI_BACKEND === "true" ||
    explicitProvider === "backend"
  ) {
    return "backend";
  }

  // AWS: Lambda URLs or SageMaker endpoint (Modal deprecated; do not auto-detect)
  // Prefer AWS when AWS_* or SAGEMAKER_* is set
  if (
    process.env.AWS_LAMBDA_GENERATION_URL ||
    process.env.AWS_LAMBDA_SAFETY_URL ||
    process.env.SAGEMAKER_ENDPOINT ||
    process.env.AWS_SAGEMAKER_GENERATION_ENDPOINT
  ) {
    return "aws";
  }
  if (process.env.GOOGLE_CLOUD_PROJECT || process.env.GCP_REGION) {
    return "gcp";
  }
  if (process.env.LIGHTNING_API_KEY || process.env.LIGHTNING_CLOUD_URL) {
    return "lightning";
  }

  // When no AWS URLs are set (e.g. local dev), use FastAPI backend to avoid getServiceUrl throwing
  const hasAws =
    process.env.AWS_LAMBDA_GENERATION_URL ||
    process.env.AWS_LAMBDA_SAFETY_URL ||
    process.env.AWS_API_GATEWAY_URL ||
    process.env.SAGEMAKER_ENDPOINT ||
    process.env.AWS_SAGEMAKER_GENERATION_ENDPOINT;
  if (!hasAws) {
    return "backend";
  }

  // Default: AWS when AWS env vars are present
  return "aws";
}

// Service endpoint configurations per provider
interface ServiceConfig {
  modal: string;
  aws: string;
  gcp: string;
  lightning: string;
  local: string;
}

// Build Modal URL with correct format
function buildModalUrl(appName: string, endpoint: string): string {
  const username = process.env.MODAL_USERNAME || "cn149";
  return `https://${username}--${appName}--${endpoint}.modal.run`;
}

// Build AWS URL - API Gateway (Lambda) or direct SageMaker
function buildAwsUrl(serviceName: string): string {
  const region = process.env.AWS_REGION || "us-east-1";

  // Prefer explicit Lambda/API Gateway URLs (from SAM deploy output)
  const lambdaUrl = process.env[`AWS_LAMBDA_${serviceName.toUpperCase()}_URL`];
  if (lambdaUrl) {
    return lambdaUrl;
  }

  // Fallback: build from API Gateway base URL (from SAM deploy output)
  // Accept full URL like .../Prod/safety or base like .../Prod — normalize to base then append path
  let apiBase = (process.env.AWS_API_GATEWAY_URL || "").replace(/\/$/, "");
  if (apiBase) {
    const knownPaths = ["/safety", "/generate", "/refine", "/train"];
    for (const p of knownPaths) {
      if (apiBase.endsWith(p)) {
        apiBase = apiBase.slice(0, -p.length);
        break;
      }
    }
    const pathMap: Record<string, string> = {
      safety: "/safety",
      generation: "/generate",
      refinement: "/refine",
      training: "/train",
    };
    const path = pathMap[serviceName] || `/${serviceName}`;
    return apiBase + path;
  }

  // Direct SageMaker (requires IAM auth - use Lambda for serverless)
  const sagemakerEndpoint = process.env.SAGEMAKER_ENDPOINT || process.env.AWS_SAGEMAKER_GENERATION_ENDPOINT;
  if (sagemakerEndpoint && serviceName === "generation") {
    return `https://runtime.sagemaker.${region}.amazonaws.com/endpoints/${sagemakerEndpoint}/invocations`;
  }

  throw new Error(
    `AWS ${serviceName} URL not configured. Set AWS_LAMBDA_${serviceName.toUpperCase()}_URL or AWS_API_GATEWAY_URL`
  );
}

// Build GCP URL (Cloud Run or Vertex AI)
function buildGcpUrl(serviceName: string): string {
  const project = process.env.GOOGLE_CLOUD_PROJECT || "";
  const region = process.env.GCP_REGION || "us-central1";

  // Check for Vertex AI endpoint first
  const vertexEndpoint = process.env[`GCP_VERTEX_${serviceName.toUpperCase()}_ENDPOINT`];
  if (vertexEndpoint) {
    return `https://${region}-aiplatform.googleapis.com/v1/projects/${project}/locations/${region}/endpoints/${vertexEndpoint}:predict`;
  }

  // Fall back to Cloud Run URL
  const cloudRunUrl = process.env[`GCP_CLOUDRUN_${serviceName.toUpperCase()}_URL`];
  if (cloudRunUrl) {
    return cloudRunUrl;
  }

  // Default Cloud Run pattern
  return `https://photogenius-${serviceName}-${project}.${region}.run.app`;
}

// Build Lightning.ai URL
function buildLightningUrl(serviceName: string): string {
  const baseUrl = process.env.LIGHTNING_CLOUD_URL || "https://lightning.ai";
  const teamId = process.env.LIGHTNING_TEAM_ID || "";
  const appId = process.env.LIGHTNING_APP_ID || "photogenius";

  // Check for explicit endpoint URL
  const explicitUrl = process.env[`LIGHTNING_${serviceName.toUpperCase()}_URL`];
  if (explicitUrl) {
    return explicitUrl;
  }

  return `${baseUrl}/v1/apps/${teamId}/${appId}/${serviceName}`;
}

// Build local development URL
function buildLocalUrl(serviceName: string): string {
  const basePort = parseInt(process.env.LOCAL_AI_BASE_PORT || "8000");
  const portMap: Record<string, number> = {
    safety: basePort,
    generation: basePort + 1,
    refinement: basePort + 2,
    training: basePort + 3,
    orchestrator: basePort + 4,
    quality: basePort + 5,
    identity: basePort + 6,
    realtime: basePort + 7,
  };
  return `http://localhost:${portMap[serviceName] || basePort}`;
}

// Build FastAPI backend URL (single backend for generation + safety)
function buildBackendUrl(serviceName: string): string {
  const base =
    process.env.FASTAPI_URL ||
    process.env.NEXT_PUBLIC_API_URL ||
    "http://localhost:8000";
  const baseUrl = base.replace(/\/$/, "");
  if (serviceName === "generation") {
    return `${baseUrl}/api/v1/generation/sync`;
  }
  if (serviceName === "safety") {
    return `${baseUrl}/api/v1/safety/check`;
  }
  return `${baseUrl}/api/v1/${serviceName}`;
}

// Service name to Modal app/endpoint mapping
const MODAL_SERVICE_MAP: Record<ServiceName, { app: string; endpoint: string }> = {
  safety: { app: "photogenius-safety", endpoint: "check-prompt-safety-web" },
  generation: { app: "photogenius-generation", endpoint: "generate-images-web" },
  refinement: { app: "photogenius-refinement-engine", endpoint: "refine-web" },
  training: { app: "photogenius-lora-trainer", endpoint: "train-lora-web" },
  orchestrator: { app: "photogenius-orchestrator", endpoint: "orchestrate-web" },
  quality: { app: "quality-scorer", endpoint: "score-batch-web" },
  identity: { app: "photogenius-identity-v2", endpoint: "generate-ultimate-web" },
  realtime: { app: "realtime-engine", endpoint: "generate-realtime-batch-web" },
};

/**
 * Get service URL for the current cloud provider
 * Automatically detects provider from environment variables
 *
 * @param service - The service name (safety, generation, etc.)
 * @param overrideProvider - Optional: force a specific provider
 * @returns The full URL for the service endpoint
 */
export function getServiceUrl(
  service: ServiceName,
  overrideProvider?: CloudProvider
): string {
  const provider = overrideProvider || detectProvider();

  // Check for explicit URL override first (works for any provider)
  const explicitUrl = process.env[`AI_${service.toUpperCase()}_URL`];
  if (explicitUrl) {
    return explicitUrl;
  }

  switch (provider) {
    case "modal":
      const modalConfig = MODAL_SERVICE_MAP[service];
      return buildModalUrl(modalConfig.app, modalConfig.endpoint);

    case "aws":
      return buildAwsUrl(service);

    case "gcp":
      return buildGcpUrl(service);

    case "lightning":
      return buildLightningUrl(service);

    case "local":
      return buildLocalUrl(service);

    case "backend":
      return buildBackendUrl(service);

    default:
      // Fallback to AWS (project setup is AWS-only)
      return buildAwsUrl(service);
  }
}

/**
 * Get the current cloud provider
 */
export function getCurrentProvider(): CloudProvider {
  return detectProvider();
}

/**
 * Get all service URLs for debugging/logging
 */
export function getAllServiceUrls(): Record<ServiceName, string> {
  const services: ServiceName[] = [
    "safety", "generation", "refinement", "training",
    "orchestrator", "quality", "identity", "realtime"
  ];

  return services.reduce((acc, service) => {
    acc[service] = getServiceUrl(service);
    return acc;
  }, {} as Record<ServiceName, string>);
}

/**
 * Get authentication headers for the current provider
 */
export function getAuthHeaders(): Record<string, string> {
  const provider = detectProvider();

  switch (provider) {
    case "modal":
      // Modal uses URL-based auth, no headers needed for web endpoints
      return {};

    case "aws":
      // AWS uses IAM/Cognito - headers set by SDK
      const awsToken = process.env.AWS_SESSION_TOKEN;
      if (awsToken) {
        return { "X-Amz-Security-Token": awsToken };
      }
      return {};

    case "gcp":
      // GCP uses OAuth2 bearer tokens
      const gcpToken = process.env.GCP_ACCESS_TOKEN;
      if (gcpToken) {
        return { Authorization: `Bearer ${gcpToken}` };
      }
      return {};

    case "lightning":
      const lightningKey = process.env.LIGHTNING_API_KEY;
      if (lightningKey) {
        return { "X-Api-Key": lightningKey };
      }
      return {};

    case "backend":
      // FastAPI: Clerk JWT is sent by Next.js route when calling generation/sync
      const bearer = process.env.CLERK_JWT_TOKEN || process.env.NEXT_PUBLIC_CLERK_JWT_TOKEN;
      if (bearer) {
        return { Authorization: `Bearer ${bearer}` };
      }
      return {};

    default:
      return {};
  }
}

/**
 * Fetch with automatic provider configuration
 */
export async function cloudFetch(
  service: ServiceName,
  options: RequestInit = {}
): Promise<Response> {
  const url = getServiceUrl(service);
  const authHeaders = getAuthHeaders();

  const headers = {
    "Content-Type": "application/json",
    ...authHeaders,
    ...(options.headers || {}),
  };

  return fetch(url, {
    ...options,
    headers,
  });
}

// Export provider detection for debugging
export { detectProvider };
