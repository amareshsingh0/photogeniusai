import { NextRequest, NextResponse } from 'next/server'
import { prisma, isPrismaDbUnavailable } from '@/lib/db'
import { getUserId } from '@/lib/auth'

export async function POST(req: NextRequest) {
  try {
    const userId = await getUserId()
    if (!userId) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })

    const body = await req.json()
    const {
      heroUrl, adCopy, posterDesign, designBrief,
      imageUrl, width = 1080, height = 1536,
      name,
    } = body

    try {
      const project = await (prisma as any).posterProject.create({
        data: {
          userId,
          name:        name || (adCopy?.headline ? `${adCopy.headline}` : 'Untitled Poster'),
          designBrief: JSON.parse(JSON.stringify({
            ad_copy:       adCopy,
            poster_design: posterDesign,
            hero_url:      heroUrl,
            ...(designBrief ?? {}),
          })),
          heroUrl,
          thumbnail:   typeof imageUrl === 'string' && imageUrl.startsWith('data:')
            ? imageUrl.substring(0, 2000)
            : (imageUrl ?? null),
          width,
          height,
          platform:    designBrief?.triage?.platform ?? null,
          bucket:      'typography',
        },
      })
      return NextResponse.json({ projectId: project.id, project })
    } catch (dbErr: unknown) {
      // DB unreachable — return an in-memory project ID so the editor still opens
      if (isPrismaDbUnavailable(dbErr)) {
        const fallbackId = `local_${Date.now()}`
        console.warn('[/api/projects/create] DB unavailable — returning local project ID')
        return NextResponse.json({
          projectId: fallbackId,
          project: {
            id:      fallbackId,
            name:    name || adCopy?.headline || 'Untitled Poster',
            heroUrl, width, height,
            designBrief: { ad_copy: adCopy, poster_design: posterDesign, hero_url: heroUrl, ...(designBrief ?? {}) },
            thumbnail: typeof imageUrl === 'string' && imageUrl.startsWith('data:') ? null : (imageUrl ?? null),
          },
          _local: true,
        })
      }
      throw dbErr
    }
  } catch (error: unknown) {
    const msg = error instanceof Error ? error.message : String(error)
    console.error('[/api/projects/create]', msg)
    return NextResponse.json({ error: msg }, { status: 500 })
  }
}
