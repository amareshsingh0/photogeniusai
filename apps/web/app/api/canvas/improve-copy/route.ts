import { NextRequest, NextResponse } from 'next/server'

/**
 * POST /api/canvas/improve-copy
 * Uses Gemini to rewrite a text element while preserving length and tone.
 */
export async function POST(req: NextRequest) {
  try {
    const { text, context, tone, maxWords } = await req.json()

    if (!text) return NextResponse.json({ error: 'text required' }, { status: 400 })

    const geminiKey = process.env.GEMINI_API_KEY
    if (!geminiKey) {
      return NextResponse.json({ improved_text: text, skipped: 'no_gemini_key' })
    }

    const wordCount = text.split(' ').length
    const maxW = maxWords ?? Math.max(wordCount + 2, 8)

    const prompt = `You are a world-class copywriter. Improve this ad text: "${text}"

Context: ${context || 'general ad'}
Tone: ${tone || 'professional'}
Max words: ${maxW}
Keep roughly the same length. Return ONLY the improved text — no quotes, no explanation.`

    const res = await fetch(
      `https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-preview-04-17:generateContent?key=${geminiKey}`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          contents: [{ parts: [{ text: prompt }] }],
          generationConfig: { temperature: 0.8, maxOutputTokens: 100 },
        }),
      },
    )

    const data = await res.json()
    const improved = data?.candidates?.[0]?.content?.parts?.[0]?.text?.trim()

    return NextResponse.json({
      improved_text: improved || text,
      original_text: text,
    })
  } catch (error: any) {
    console.error('[/api/canvas/improve-copy]', error)
    return NextResponse.json({ error: error.message }, { status: 500 })
  }
}
