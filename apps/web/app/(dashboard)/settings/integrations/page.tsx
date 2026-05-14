'use client'

/**
 * Social Integrations Settings — /settings/integrations
 * Connect Instagram (Meta OAuth) and LinkedIn (OAuth 2.0).
 * Access tokens stored in User.preferences.integrations via API.
 */

import React, { useEffect, useState } from 'react'
import { Instagram, Linkedin, Loader2, ExternalLink, AlertTriangle, Plug } from 'lucide-react'

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
      <div className="flex h-64 items-center justify-center">
        <Loader2 className="h-6 w-6 animate-spin text-white/50" />
      </div>
    )
  }

  return (
    <div className="mx-auto max-w-2xl px-4 py-8 pb-24 space-y-6">
      <div>
        <h1 className="font-display text-3xl tracking-tight sm:text-4xl">Integrations</h1>
        <p className="mt-1 text-sm text-white/50">Connect your social accounts to publish scheduled content directly from Pixium AI.</p>
      </div>

      <div className="glass-panel flex items-start gap-3 rounded-2xl p-4">
        <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-amber-400" />
        <p className="text-xs leading-relaxed text-white/50">
          Connecting a social account requires a Business or Creator account. Personal accounts are not supported by Meta/LinkedIn APIs. Your access tokens are stored encrypted and never shared.
        </p>
      </div>

      <div className="glass-panel rounded-2xl p-5 space-y-3">
        <div className="flex items-center gap-2 mb-1"><Plug className="h-4 w-4 text-white/60" /><p className="kerned text-white/40">PROVIDERS</p></div>
        <IntegrationRow
          icon={<Instagram className="h-4 w-4" />}
          name="Instagram"
          description="Publish feed posts, stories, and carousels to your Instagram Business account."
          status={status.instagram}
          onConnect={() => handleConnect('instagram')}
          onDisconnect={() => handleDisconnect('instagram')}
          disconnecting={disconnecting === 'instagram'}
          docsUrl="https://developers.facebook.com/docs/instagram-api"
        />
        <IntegrationRow
          icon={<Linkedin className="h-4 w-4" />}
          name="LinkedIn"
          description="Publish image posts to your LinkedIn profile or company page."
          status={status.linkedin}
          onConnect={() => handleConnect('linkedin')}
          onDisconnect={() => handleDisconnect('linkedin')}
          disconnecting={disconnecting === 'linkedin'}
          docsUrl="https://learn.microsoft.com/en-us/linkedin/marketing/integrations"
        />
      </div>
    </div>
  )
}

interface RowProps {
  icon:          React.ReactNode
  name:          string
  description:   string
  status:        IntegrationStatus
  onConnect:     () => void
  onDisconnect:  () => void
  disconnecting: boolean
  docsUrl:       string
}

function IntegrationRow({ icon, name, description, status, onConnect, onDisconnect, disconnecting, docsUrl }: RowProps) {
  return (
    <div className="hairline flex items-start gap-3 rounded-xl p-3">
      <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-white/5 text-white/70">{icon}</div>
      <div className="min-w-0 flex-1">
        <div className="mb-1 flex items-center gap-2">
          <span className="text-sm text-white/85">{name}</span>
          <span className="inline-flex items-center gap-1.5 rounded-full bg-white/5 px-2 py-0.5 text-[11px] text-white/70">
            <span className={`h-2 w-2 rounded-full ${status.connected ? 'bg-emerald-500/80' : 'bg-white/40'}`} />
            {status.connected ? 'Connected' : 'Not connected'}
          </span>
        </div>
        <p className="text-xs leading-relaxed text-white/50">{description}</p>
        {status.connected && status.account_name && (
          <p className="mt-2 text-xs text-white/60">Account: <span className="text-white/85">{status.account_name}</span></p>
        )}
      </div>
      <div className="flex shrink-0 items-center gap-2">
        <a href={docsUrl} target="_blank" rel="noopener noreferrer" className="rounded-lg p-2 text-white/30 hover:bg-white/5 hover:text-white/60 transition" title="API docs">
          <ExternalLink className="h-3.5 w-3.5" />
        </a>
        {status.connected ? (
          <button onClick={onDisconnect} disabled={disconnecting} className="flex items-center gap-1.5 rounded-xl border border-red-500/30 bg-red-500/10 px-3 py-1.5 text-sm text-red-200 hover:bg-red-500/15 transition disabled:opacity-50">
            {disconnecting && <Loader2 className="h-3.5 w-3.5 animate-spin" />} Disconnect
          </button>
        ) : (
          <button onClick={onConnect} className="rounded-xl border border-white/10 bg-white/5 px-3 py-1.5 text-sm hover:bg-white/10 transition">Connect</button>
        )}
      </div>
    </div>
  )
}
