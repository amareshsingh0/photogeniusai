'use client'

/**
 * Social Integrations Settings — /settings/integrations
 * Connect Instagram (Meta OAuth) and LinkedIn (OAuth 2.0).
 * Access tokens stored in User.preferences.integrations via API.
 */

import React, { useEffect, useState } from 'react'
import { Instagram, Linkedin, CheckCircle, XCircle, Loader2, ExternalLink, AlertTriangle } from 'lucide-react'

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8003'

interface IntegrationStatus {
  connected:   boolean
  account_name?: string
  expires_at?:  string
}

interface IntegrationsState {
  instagram: IntegrationStatus
  linkedin:  IntegrationStatus
}

export default function IntegrationsPage() {
  const [status, setStatus] = useState<IntegrationsState>({
    instagram: { connected: false },
    linkedin:  { connected: false },
  })
  const [loading, setLoading]   = useState(true)
  const [disconnecting, setDisconnecting] = useState<string | null>(null)

  useEffect(() => {
    const load = async () => {
      try {
        const res = await fetch(`${API_BASE}/api/v1/preferences/integrations`, {
          credentials: 'include',
        })
        if (res.ok) {
          const data = await res.json()
          setStatus(prev => ({
            instagram: data.instagram ? { connected: true, account_name: data.instagram.account_name, expires_at: data.instagram.expires_at } : prev.instagram,
            linkedin:  data.linkedin  ? { connected: true, account_name: data.linkedin.account_name,  expires_at: data.linkedin.expires_at  } : prev.linkedin,
          }))
        }
      } catch { /* use defaults */ }
      finally { setLoading(false) }
    }
    load()

    // Handle OAuth callback params
    const params = new URLSearchParams(window.location.search)
    const platform = params.get('connected')
    const account  = params.get('account')
    if (platform && account) {
      setStatus(prev => ({
        ...prev,
        [platform]: { connected: true, account_name: decodeURIComponent(account) },
      }))
      window.history.replaceState({}, '', window.location.pathname)
    }
  }, [])

  const handleConnect = (platform: 'instagram' | 'linkedin') => {
    // Redirect to OAuth flow — backend generates the auth URL
    const callbackBase = typeof window !== 'undefined' ? window.location.origin : ''
    const oauthUrl = `${API_BASE}/api/v1/oauth/${platform}/start?redirect_uri=${encodeURIComponent(callbackBase + '/settings/integrations')}`
    window.location.href = oauthUrl
  }

  const handleDisconnect = async (platform: 'instagram' | 'linkedin') => {
    setDisconnecting(platform)
    try {
      await fetch(`${API_BASE}/api/v1/preferences/integrations/${platform}`, {
        method: 'DELETE',
        credentials: 'include',
      })
      setStatus(prev => ({ ...prev, [platform]: { connected: false } }))
    } catch { /* silent */ }
    finally { setDisconnecting(null) }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="w-6 h-6 animate-spin text-purple-400" />
      </div>
    )
  }

  return (
    <div className="max-w-2xl space-y-8">
      <div>
        <h1 className="text-lg font-semibold text-white">Social Integrations</h1>
        <p className="text-sm text-white/40 mt-1">
          Connect your social accounts to publish scheduled content directly from PhotoGenius AI.
        </p>
      </div>

      {/* Notice */}
      <div className="flex items-start gap-3 p-4 rounded-xl bg-amber-500/5 border border-amber-500/15">
        <AlertTriangle className="w-4 h-4 text-amber-400 mt-0.5 shrink-0" />
        <p className="text-xs text-amber-200/70 leading-relaxed">
          Connecting a social account requires a Business or Creator account. Personal accounts are not supported by Meta/LinkedIn APIs.
          Your access tokens are stored encrypted and never shared.
        </p>
      </div>

      {/* Instagram */}
      <IntegrationCard
        icon={<Instagram className="w-5 h-5" />}
        name="Instagram"
        description="Publish feed posts, stories, and carousels to your Instagram Business account."
        color="from-fuchsia-600 to-pink-600"
        status={status.instagram}
        onConnect={() => handleConnect('instagram')}
        onDisconnect={() => handleDisconnect('instagram')}
        disconnecting={disconnecting === 'instagram'}
        docsUrl="https://developers.facebook.com/docs/instagram-api"
      />

      {/* LinkedIn */}
      <IntegrationCard
        icon={<Linkedin className="w-5 h-5" />}
        name="LinkedIn"
        description="Publish image posts to your LinkedIn profile or company page."
        color="from-blue-600 to-blue-700"
        status={status.linkedin}
        onConnect={() => handleConnect('linkedin')}
        onDisconnect={() => handleDisconnect('linkedin')}
        disconnecting={disconnecting === 'linkedin'}
        docsUrl="https://learn.microsoft.com/en-us/linkedin/marketing/integrations"
      />
    </div>
  )
}

// ── Card component ─────────────────────────────────────────────────────────────

interface CardProps {
  icon:          React.ReactNode
  name:          string
  description:   string
  color:         string
  status:        IntegrationStatus
  onConnect:     () => void
  onDisconnect:  () => void
  disconnecting: boolean
  docsUrl:       string
}

function IntegrationCard({
  icon, name, description, color, status,
  onConnect, onDisconnect, disconnecting, docsUrl,
}: CardProps) {
  return (
    <div className="rounded-2xl border border-white/[0.08] bg-white/[0.025] p-5 flex items-start gap-4">
      {/* Platform icon */}
      <div className={`w-10 h-10 rounded-xl bg-gradient-to-br ${color} flex items-center justify-center text-white shrink-0`}>
        {icon}
      </div>

      {/* Info */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-1">
          <span className="text-sm font-semibold text-white">{name}</span>
          {status.connected ? (
            <span className="flex items-center gap-1 text-[10px] font-medium text-emerald-400 bg-emerald-400/10 border border-emerald-400/20 px-2 py-0.5 rounded-full">
              <CheckCircle className="w-3 h-3" /> Connected
            </span>
          ) : (
            <span className="flex items-center gap-1 text-[10px] font-medium text-white/30 bg-white/5 border border-white/10 px-2 py-0.5 rounded-full">
              <XCircle className="w-3 h-3" /> Not connected
            </span>
          )}
        </div>
        <p className="text-xs text-white/40 leading-relaxed">{description}</p>
        {status.connected && status.account_name && (
          <p className="text-xs text-white/50 mt-2">
            Account: <span className="text-white/70 font-medium">{status.account_name}</span>
          </p>
        )}
      </div>

      {/* Actions */}
      <div className="flex items-center gap-2 shrink-0">
        <a
          href={docsUrl}
          target="_blank"
          rel="noopener noreferrer"
          className="p-2 rounded-lg text-white/30 hover:text-white/60 hover:bg-white/5 transition-colors"
          title="API docs"
        >
          <ExternalLink className="w-3.5 h-3.5" />
        </a>
        {status.connected ? (
          <button
            onClick={onDisconnect}
            disabled={disconnecting}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs text-red-400 hover:text-red-300 bg-red-500/5 hover:bg-red-500/10 border border-red-500/15 hover:border-red-500/30 transition-colors disabled:opacity-50"
          >
            {disconnecting ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : null}
            Disconnect
          </button>
        ) : (
          <button
            onClick={onConnect}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs text-white bg-purple-600 hover:bg-purple-500 transition-colors font-medium"
          >
            Connect
          </button>
        )}
      </div>
    </div>
  )
}
