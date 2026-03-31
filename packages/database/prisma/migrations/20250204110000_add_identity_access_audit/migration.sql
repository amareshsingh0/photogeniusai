-- Biometric compliance: audit log for identity access
CREATE TABLE IF NOT EXISTS identity_access_audit_logs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  "identityId" UUID NOT NULL,
  "userId" UUID NOT NULL,
  action VARCHAR(50) NOT NULL,
  "ipAddress" VARCHAR(45),
  "userAgent" TEXT,
  timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS identity_access_audit_identity_idx ON identity_access_audit_logs("identityId");
CREATE INDEX IF NOT EXISTS identity_access_audit_user_idx ON identity_access_audit_logs("userId");
CREATE INDEX IF NOT EXISTS identity_access_audit_timestamp_idx ON identity_access_audit_logs(timestamp);
