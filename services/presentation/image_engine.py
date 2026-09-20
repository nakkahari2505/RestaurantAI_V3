from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


PROJECT_ROOT = Path(__file__).resolve().parents[2]
FONTS_DIRECTORY = PROJECT_ROOT / "assets" / "fonts"

REGULAR_FONT_PATH = FONTS_DIRECTORY / "DejaVuSans.ttf"
BOLD_FONT_PATH = FONTS_DIRECTORY / "DejaVuSans-Bold.ttf"


def load_font(
    size: int,
    bold: bool = False,
) -> ImageFont.FreeTypeFont:
    """
    Load the font bundled inside the RestaurantAI project.

    This gives identical rendering locally and on Railway.
    """
    font_path = (
        BOLD_FONT_PATH
        if bold
        else REGULAR_FONT_PATH
    )

    if not font_path.exists():
        raise FileNotFoundError(
            f"Required font file was not found: {font_path}"
        )

    return ImageFont.truetype(
        str(font_path),
        size=size,
    )


def create_canvas(
    width: int,
    height: int,
    background: str = "white",
) -> tuple[
    Image.Image,
    ImageDraw.ImageDraw,
]:
    image = Image.new(
        "RGB",
        (width, height),
        background,
    )

    draw = ImageDraw.Draw(image)

    return image, draw


def get_text_width(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.FreeTypeFont,
) -> int:
    text_box = draw.textbbox(
        (0, 0),
        text,
        font=font,
    )

    return text_box[2] - text_box[0]


def draw_right_aligned_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    right_x: int,
    y: int,
    font: ImageFont.FreeTypeFont,
    fill: str,
) -> None:
    text_width = get_text_width(
        draw=draw,
        text=text,
        font=font,
    )

    draw.text(
        (
            right_x - text_width,
            y,
        ),
        text,
        font=font,
        fill=fill,
    )


def draw_centered_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    left_x: int,
    right_x: int,
    y: int,
    font: ImageFont.FreeTypeFont,
    fill: str,
) -> None:
    text_width = get_text_width(
        draw=draw,
        text=text,
        font=font,
    )

    available_width = right_x - left_x

    text_x = (
        left_x
        + (
            available_width
            - text_width
        )
        // 2
    )

    draw.text(
        (
            text_x,
            y,
        ),
        text,
        font=font,
        fill=fill,
    )


def draw_table_row(
    draw: ImageDraw.ImageDraw,
    left: int,
    top: int,
    right: int,
    bottom: int,
    background: str,
    border_colour: str,
    border_width: int = 1,
) -> None:
    draw.rectangle(
        (
            left,
            top,
            right,
            bottom,
        ),
        fill=background,
        outline=border_colour,
        width=border_width,
    )


def draw_status_box(
    draw: ImageDraw.ImageDraw,
    left: int,
    top: int,
    right: int,
    bottom: int,
    heading: str,
    message: str,
    heading_font: ImageFont.FreeTypeFont,
    message_font: ImageFont.FreeTypeFont,
    background: str,
    text_colour: str,
) -> None:
    draw.rounded_rectangle(
        (
            left,
            top,
            right,
            bottom,
        ),
        radius=20,
        fill=background,
    )

    draw.text(
        (
            left + 28,
            top + 22,
        ),
        heading,
        font=heading_font,
        fill=text_colour,
    )

    draw.text(
        (
            left + 28,
            top + 72,
        ),
        message,
        font=message_font,
        fill=text_colour,
    )


def save_png(
    image: Image.Image,
    file_path: Path,
) -> None:
    file_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    image.save(
        file_path,
        format="PNG",
        optimize=True,
    )