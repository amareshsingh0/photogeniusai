import { NextRequest, NextResponse } from 'next/server'
import { db } from '@/lib/db'
import { getCurrentUserId } from '@/lib/auth'

export async function POST(req: NextRequest) {
  try {
    const userId = await getCurrentUserId(req)
    if (!userId) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })

    const body = await req.json()
    const {
      heroUrl, adCopy, posterDesign, designBrief,
      imageUrl, width = 1080, height = 1536,
      prompt, quality, name,
    } = body

    const project = await (db as any).posterProject.create({
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
  } catch (error: any) {
    console.error('[/api/projects/create]', error)
    return NextResponse.json({ error: error.message }, { status: 500 })
  }
}
