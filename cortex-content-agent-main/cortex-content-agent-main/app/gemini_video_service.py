from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
from moviepy import ImageClip, concatenate_videoclips

from .config import OUTPUT_DIR


VIDEO_WIDTH = 720
VIDEO_HEIGHT = 1280
VIDEO_DURATION = 3


def create_scene_image(
    title: str,
    subtitle: str,
    scene_number: int
):
    """
    Creates a professional vertical scene image locally.
    """

    image = Image.new(
        "RGB",
        (VIDEO_WIDTH, VIDEO_HEIGHT),
        (18, 24, 38)
    )

    draw = ImageDraw.Draw(image)

    # Large visual area
    draw.rounded_rectangle(
        (50, 120, VIDEO_WIDTH - 50, 700),
        radius=35,
        fill=(35, 48, 70)
    )

    # Scene indicator
    draw.text(
        (60, 60),
        f"SCENE {scene_number}",
        fill=(180, 190, 210)
    )

    # Main headline
    try:
        title_font = ImageFont.truetype(
            "arial.ttf",
            52
        )
    except:
        title_font = ImageFont.load_default()

    draw.multiline_text(
        (60, 780),
        title,
        font=title_font,
        fill="white",
        spacing=12
    )

    # Subtitle
    try:
        subtitle_font = ImageFont.truetype(
            "arial.ttf",
            30
        )
    except:
        subtitle_font = ImageFont.load_default()

    draw.multiline_text(
        (60, 960),
        subtitle,
        font=subtitle_font,
        fill=(190, 200, 215),
        spacing=10
    )

    # Bottom branding
    draw.text(
        (60, 1160),
        "AI-Powered Content Agent",
        font=subtitle_font,
        fill=(140, 160, 190)
    )

    filename = Path(OUTPUT_DIR) / f"scene_{scene_number}.png"

    image.save(filename)

    return filename


def generate_video(prompt: str):

    output_dir = Path(OUTPUT_DIR)
    output_dir.mkdir(
        parents=True,
        exist_ok=True
    )

    scenes = [
        (
            "Your future starts today.",
            "Small financial decisions today can create stronger protection tomorrow."
        ),
        (
            "Plan before you need it.",
            "Protection can be part of your long-term financial strategy."
        ),
        (
            "Build. Protect. Grow.",
            "Think about your goals and the people who matter to you."
        ),
        (
            "Protection is part of the plan.",
            "Make financial planning more complete with the right protection."
        ),
    ]

    clips = []

    for index, (title, subtitle) in enumerate(
        scenes,
        start=1
    ):

        image_path = create_scene_image(
            title=title,
            subtitle=subtitle,
            scene_number=index
        )

        clip = (
            ImageClip(str(image_path))
            .with_duration(VIDEO_DURATION)
        )

        clips.append(clip)

    final_video = concatenate_videoclips(
        clips,
        method="compose"
    )

    output_path = (
        output_dir /
        "cortex_generated_video.mp4"
    )

    final_video.write_videofile(
        str(output_path),
        fps=24,
        codec="libx264",
        audio=False
    )

    final_video.close()

    return output_path.name