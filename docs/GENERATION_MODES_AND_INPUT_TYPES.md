# Generation Modes & Input Types – Difference Explained

## 1. Style modes (AI pipeline types) – ek doosre se kaise alag hain

Yeh **8 style modes** hain. Har ek **output style** alag hota hai: same prompt par bhi image ka look, mood aur quality settings change ho jaate hain.

| Mode | Kya hota hai | Best for |
|------|--------------|----------|
| **Realistic** | Photorealistic, DSLR jaisa, natural lighting, sharp, professional. | Headshots, ID photos, professional portraits |
| **Creative** | Artistic, stylized, “trending on artstation” feel, vibrant, concept-art style. | Art, illustrations, stylized portraits |
| **Cinematic** | Film jaisa: anamorphic, film grain, dramatic lighting, 35mm feel. | Movie stills, dramatic portraits |
| **Fashion** | Editorial, vogue-style, studio lighting, glamour, haute couture. | Fashion shoots, glamour, editorial |
| **Romantic** | Warm, golden hour, dreamy bokeh, soft, elegant. | Romantic / couple / soft portraits |
| **Cool Edgy** | Cyberpunk, neon, moody, dark, high contrast. | Edgy / urban / futuristic looks |
| **Artistic** | Surreal, painterly, dreamlike, concept-art, stylized. | Creative / fantasy / artistic images |
| **Max Surprise** | Unconventional, bold, high creativity, unexpected. | Experimental, bold, unique looks |

**Technical difference:** Har mode ke liye alag **prompt templates**, **negative prompts**, **guidance scale**, **inference steps** aur kabhi-kabhi **resolution** (e.g. Cinematic/Fashion different aspect ratio) use hote hain – yeh sab ai-pipeline aur backend generation service me define hain.

---

## 2. Form vs Chat vs Variants – ek doosre se kaise alag hain

Yeh **3 input / flow types** hain. Style nahi, **kaise prompt daaloge aur kaise generate karoge** us par focus hai.

| Type | Kya hota hai | Kab use karein |
|------|--------------|-----------------|
| **Form** | Classic single prompt: ek text box me description likho, “Generate” dabao. Ek hi prompt se direct image generation. | Jab aapko seedha ek description se image chahiye, bina chat ya variants ke. |
| **Chat** | Chat-style flow: multiple messages, back-and-forth, refine prompt through conversation. | Jab aap prompt ko step-by-step improve karna chahte ho, ya natural conversation se describe karna chahte ho. |
| **Variants** | Pehle **6 styled variants** (Realistic, Cinematic, Cool Edgy, Artistic, Max Surprise, Personalized) generate hote hain; aap ek variant choose karte ho, uske enhanced prompt ko use karke phir **main image generation** kar sakte ho. | Jab aap pehle dekhna chahte ho ki prompt alag-alag styles me kaise dikhega, phir best style/prompt select karke final image banana chahte ho. |

**Short summary:**

- **Form** = ek prompt → direct generate  
- **Chat** = conversation se prompt refine karo → phir generate  
- **Variants** = pehle 6 style variants dekho → ek choose karo → us prompt/style se generate  

---

## 3. Commands summary (jo run kiye / ab run kar sakte ho)

- **API PostgreSQL (Alembic):**  
  `cd apps\api` then `python -m alembic upgrade head`  
  (Revision chain fix + 004 index fix + 005 enum add – done.)

- **Web app DB (Prisma):**  
  - Client update: `cd packages\database` then `npx prisma generate` (done).  
  - Agar naye enum values DB me nahi (e.g. separate DB):  
    - Local dev: `pnpm run db:migrate` (interactive terminal me).  
    - Deploy: `pnpm run db:migrate` ya `npx prisma migrate deploy` (non-interactive).

- **Prisma migrate dev** interactive hai; non-interactive (CI/deploy) me `prisma migrate deploy` use karein.
