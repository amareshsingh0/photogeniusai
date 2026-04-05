import { NextRequest, NextResponse } from 'next/server'
import { prisma } from '@/lib/db'
import { getUserId } from '@/lib/auth'

export async function POST(req: NextRequest) {
  try {
    const userId = await getUserId()
    if (!userId) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })

    const body = await req.json()
    const {
      heroUrl, adCopy, posterDesign, designBrief,
      imageUrl, width = 1080, height = 1536,
      prompt, quality, name,
    } = body

    const project = await (prisma as any).posterProject.create({
      data: {
        userId,
        name:        name || (adCopy?.headline ? `${adCopy.headline}` : 'Untitled Poster'),
        designBrief: designBrief ? JSON.parse(JSON.stringify({
          ad_copy:      adCopy,
          poster_design: posterDesign,
          hero_url:     heroUrl,
          ...designBrief,
        })) : { ad_copy: adCopy, poster_design: posterDesign },
        heroUrl,
        thumbnail:   imageUrl?.startsWith('data:') ? imageUrl.substring(0, 2000) : imageUrl,
        width,
        height,
        platform:    designBrief?.triage?.platform ?? null,
        bucket:      'typography',
      },
    })

    return NextResponse.json({ projectId: project.id, project })
  } catch (error: unknown) {
    const msg = error instanceof Error ? error.message : String(error)
    console.error('[/api/projects/create]', msg)
    return NextResponse.json({ error: msg }, { status: 500 })
  }
}
