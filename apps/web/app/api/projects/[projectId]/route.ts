import { NextRequest, NextResponse } from 'next/server'
import { db } from '@/lib/db'
import { getCurrentUserId } from '@/lib/auth'

// GET /api/projects/[projectId]
export async function GET(
  req: NextRequest,
  { params }: { params: { projectId: string } },
) {
  try {
    const userId = await getCurrentUserId(req)
    if (!userId) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })

    const project = await (db as any).posterProject.findFirst({
      where: { id: params.projectId, userId },
    })

    if (!project) return NextResponse.json({ error: 'Not found' }, { status: 404 })

    return NextResponse.json({ project })
  } catch (error: any) {
    return NextResponse.json({ error: error.message }, { status: 500 })
  }
}

// PATCH /api/projects/[projectId] — update canvas state / name / thumbnail
export async function PATCH(
  req: NextRequest,
  { params }: { params: { projectId: string } },
) {
  try {
    const userId = await getCurrentUserId(req)
    if (!userId) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })

    const body = await req.json()
    const { canvasState, thumbnail, name, juryScore, juryGrade } = body

    const updateData: any = {}
    if (canvasState !== undefined) updateData.canvasState = canvasState
    if (thumbnail    !== undefined) updateData.thumbnail  = thumbnail?.substring?.(0, 2000)
    if (name         !== undefined) updateData.name       = name
    if (juryScore    !== undefined) updateData.juryScore  = juryScore
    if (juryGrade    !== undefined) updateData.juryGrade  = juryGrade

    const project = await (db as any).posterProject.updateMany({
      where: { id: params.projectId, userId },
      data:  updateData,
    })

    return NextResponse.json({ ok: true, updated: project.count })
  } catch (error: any) {
    return NextResponse.json({ error: error.message }, { status: 500 })
  }
}

// DELETE /api/projects/[projectId]
export async function DELETE(
  req: NextRequest,
  { params }: { params: { projectId: string } },
) {
  try {
    const userId = await getCurrentUserId(req)
    if (!userId) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })

    await (db as any).posterProject.deleteMany({
      where: { id: params.projectId, userId },
    })

    return NextResponse.json({ ok: true })
  } catch (error: any) {
    return NextResponse.json({ error: error.message }, { status: 500 })
  }
}
