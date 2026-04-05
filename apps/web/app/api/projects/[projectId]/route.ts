import { NextRequest, NextResponse } from 'next/server'
import { prisma } from '@/lib/db'
import { getUserId } from '@/lib/auth'

// GET /api/projects/[projectId]
export async function GET(
  _req: NextRequest,
  { params }: { params: { projectId: string } },
) {
  // Local fallback project (DB unavailable)
  if (params.projectId.startsWith('local_')) {
    return NextResponse.json({ project: { id: params.projectId, canvasState: null } })
  }
  try {
    const userId = await getUserId()
    if (!userId) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })

    const project = await (prisma as any).posterProject.findFirst({
      where: { id: params.projectId, userId },
    })

    if (!project) return NextResponse.json({ error: 'Not found' }, { status: 404 })

    return NextResponse.json({ project })
  } catch (error: unknown) {
    return NextResponse.json({ error: error instanceof Error ? error.message : String(error) }, { status: 500 })
  }
}

// PATCH /api/projects/[projectId] — update canvas state / name / thumbnail
export async function PATCH(
  req: NextRequest,
  { params }: { params: { projectId: string } },
) {
  if (params.projectId.startsWith('local_')) {
    return NextResponse.json({ ok: true, updated: 0, _local: true })
  }
  try {
    const userId = await getUserId()
    if (!userId) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })

    const body = await req.json()
    const { canvasState, thumbnail, name, juryScore, juryGrade } = body

    const updateData: Record<string, unknown> = {}
    if (canvasState !== undefined) updateData.canvasState = canvasState
    if (thumbnail    !== undefined) updateData.thumbnail  = typeof thumbnail === 'string' ? thumbnail.substring(0, 2000) : thumbnail
    if (name         !== undefined) updateData.name       = name
    if (juryScore    !== undefined) updateData.juryScore  = juryScore
    if (juryGrade    !== undefined) updateData.juryGrade  = juryGrade

    const project = await (prisma as any).posterProject.updateMany({
      where: { id: params.projectId, userId },
      data:  updateData,
    })

    return NextResponse.json({ ok: true, updated: project.count })
  } catch (error: unknown) {
    return NextResponse.json({ error: error instanceof Error ? error.message : String(error) }, { status: 500 })
  }
}

// DELETE /api/projects/[projectId]
export async function DELETE(
  _req: NextRequest,
  { params }: { params: { projectId: string } },
) {
  try {
    const userId = await getUserId()
    if (!userId) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })

    await (prisma as any).posterProject.deleteMany({
      where: { id: params.projectId, userId },
    })

    return NextResponse.json({ ok: true })
  } catch (error: unknown) {
    return NextResponse.json({ error: error instanceof Error ? error.message : String(error) }, { status: 500 })
  }
}
