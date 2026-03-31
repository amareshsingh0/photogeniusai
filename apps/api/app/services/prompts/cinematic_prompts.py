"""
Cinematic Prompt Engine - Movie-quality prompt enhancement

Features:
- Film style presets (noir, action, drama, etc.)
- Camera angle keywords
- Lighting presets
- Color grading suggestions
- Director style emulation

Adapted from ai-pipeline/services/cinematic_prompts.py
"""

from typing import Dict, List, Optional
from enum import Enum


class FilmStyle(Enum):
    """Film style presets"""
    NOIR = "noir"
    ACTION = "action"
    DRAMA = "drama"
    SCI_FI = "sci_fi"
    HORROR = "horror"
    ROMANCE = "romance"
    THRILLER = "thriller"
    FANTASY = "fantasy"
    DOCUMENTARY = "documentary"


class CinematicPromptEngine:
    """
    Cinematic-quality prompt enhancement

    Creates movie-style prompts with:
    - Film terminology
    - Camera specifications
    - Lighting setups
    - Color grading
    - Director styles
    """

    # Film style presets
    FILM_STYLES = {
        FilmStyle.NOIR: {
            'lighting': 'high contrast black and white, dramatic shadows, low-key lighting, film noir',
            'camera': 'Dutch angle, dramatic framing, noir cinematography',
            'mood': 'mysterious, dark, atmospheric, moody',
            'technical': 'black and white, high contrast, chiaroscuro lighting'
        },
        FilmStyle.ACTION: {
            'lighting': 'dynamic lighting, high energy, dramatic, intense',
            'camera': 'wide angle action shot, dynamic camera movement, intense framing',
            'mood': 'adrenaline, explosive, fast-paced, energetic',
            'technical': 'motion blur, high shutter speed, dynamic composition'
        },
        FilmStyle.DRAMA: {
            'lighting': 'natural lighting, soft shadows, realistic, intimate',
            'camera': 'close-up, emotional framing, shallow depth of field',
            'mood': 'emotional, touching, human, intimate',
            'technical': 'film grain, natural colors, subtle color grading'
        },
        FilmStyle.SCI_FI: {
            'lighting': 'futuristic lighting, neon accents, volumetric fog, high-tech',
            'camera': 'wide establishing shot, sci-fi cinematography, epic scale',
            'mood': 'futuristic, otherworldly, advanced, technological',
            'technical': 'cool color palette, lens flares, digital effects'
        },
        FilmStyle.HORROR: {
            'lighting': 'ominous lighting, deep shadows, eerie, dim',
            'camera': 'unsettling angles, close-ups, horror cinematography',
            'mood': 'terrifying, ominous, suspenseful, dark',
            'technical': 'desaturated colors, grain, atmospheric fog'
        }
    }

    # Camera presets
    CAMERA_ANGLES = {
        'wide': 'wide establishing shot, expansive view, 24mm lens',
        'medium': 'medium shot, balanced framing, 50mm lens',
        'close': 'close-up shot, intimate framing, 85mm lens',
        'extreme_close': 'extreme close-up, macro detail, shallow depth of field',
        'aerial': 'aerial shot, birds eye view, drone cinematography',
        'dutch': 'Dutch angle, tilted camera, dynamic framing',
        'pov': 'POV shot, first person perspective, immersive'
    }

    # Lighting setups
    LIGHTING_SETUPS = {
        'golden_hour': 'golden hour magic light, warm rim lighting, lens flare, god rays',
        'blue_hour': 'blue hour twilight, cool tones, atmospheric lighting',
        'rembrandt': 'Rembrandt lighting, dramatic triangle, studio setup',
        'rim_light': 'rim lighting, edge light, dramatic separation',
        'volumetric': 'volumetric lighting, light rays, atmospheric, cinematic fog',
        'neon': 'neon lighting, cyberpunk, colorful glow, futuristic',
        'natural': 'natural lighting, realistic, soft shadows, outdoor'
    }

    # Director styles
    DIRECTOR_STYLES = {
        'nolan': 'Christopher Nolan style, IMAX quality, epic scale, practical effects',
        'fincher': 'David Fincher style, moody, precise composition, dark atmosphere',
        'tarantino': 'Tarantino style, saturated colors, dynamic framing, stylized',
        'wes_anderson': 'Wes Anderson style, symmetrical, pastel colors, whimsical',
        'villeneuve': 'Denis Villeneuve style, atmospheric, grand scale, minimalist'
    }

    def __init__(self):
        """Initialize cinematic engine"""
        pass

    def enhance_cinematic(
        self,
        prompt: str,
        film_style: Optional[FilmStyle] = None,
        camera_angle: str = 'medium',
        lighting: str = 'volumetric',
        director_style: Optional[str] = None
    ) -> Dict:
        """
        Enhance prompt with cinematic keywords

        Args:
            prompt: Original prompt
            film_style: Film genre style
            camera_angle: Camera framing
            lighting: Lighting setup
            director_style: Director to emulate

        Returns:
            dict: Cinematically enhanced prompt
        """
        enhanced_parts = [prompt]

        # Add film style
        if film_style and film_style in self.FILM_STYLES:
            style = self.FILM_STYLES[film_style]
            enhanced_parts.append(style['lighting'])
            enhanced_parts.append(style['camera'])
            enhanced_parts.append(style['mood'])

        # Add camera angle
        if camera_angle in self.CAMERA_ANGLES:
            enhanced_parts.append(self.CAMERA_ANGLES[camera_angle])

        # Add lighting
        if lighting in self.LIGHTING_SETUPS:
            enhanced_parts.append(self.LIGHTING_SETUPS[lighting])

        # Add director style
        if director_style and director_style in self.DIRECTOR_STYLES:
            enhanced_parts.append(self.DIRECTOR_STYLES[director_style])

        # Add base cinematic quality
        enhanced_parts.append('cinematic still, movie quality, film grain, anamorphic lens')

        enhanced_prompt = ', '.join(enhanced_parts)

        return {
            'original': prompt,
            'enhanced': enhanced_prompt,
            'film_style': film_style.value if film_style else None,
            'camera_angle': camera_angle,
            'lighting': lighting,
            'director_style': director_style,
            'enhancements': {
                'base': 'cinematic quality',
                'camera': self.CAMERA_ANGLES.get(camera_angle),
                'lighting': self.LIGHTING_SETUPS.get(lighting)
            }
        }

    def get_film_styles(self) -> List[str]:
        """Get available film styles"""
        return [style.value for style in FilmStyle]

    def get_camera_angles(self) -> List[str]:
        """Get available camera angles"""
        return list(self.CAMERA_ANGLES.keys())

    def get_lighting_setups(self) -> List[str]:
        """Get available lighting setups"""
        return list(self.LIGHTING_SETUPS.keys())

    def get_director_styles(self) -> List[str]:
        """Get available director styles"""
        return list(self.DIRECTOR_STYLES.keys())


# Singleton instance
cinematic_engine = CinematicPromptEngine()
