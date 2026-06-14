"""图形验证码生成 / Captcha image generation using Pillow."""
import base64
import io
import random
import secrets
import string

from nanoid import generate as nanoid_generate
from PIL import Image, ImageDraw, ImageFont

# 排除易混淆字符 0/O/I/1
_CHARS = "".join(c for c in string.ascii_uppercase + string.digits if c not in "OI01")
_CAPTCHA_LENGTH = 6
_IMG_WIDTH = 220
_IMG_HEIGHT = 72
_FONT_SIZE = 42


def _load_captcha_font(size: int):
    """加载验证码字体：优先 TrueType，回退到 Pillow 内置【可缩放】默认字体。
    Load a captcha font: prefer TrueType, else Pillow's scalable built-in default.

    关键 / Why: ``ImageFont.truetype("Arial", ...)`` 在 slim 容器里没有 Arial 会抛错，
    旧代码回退到 ``load_default()`` 的极小位图字体——这正是验证码又小又细的根因。
    """
    for path in (
        "DejaVuSans-Bold.ttf",
        "DejaVuSans.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/Library/Fonts/Arial.ttf",
    ):
        try:
            return ImageFont.truetype(path, size)
        except (OSError, IOError):
            continue
    try:
        return ImageFont.load_default(size=size)  # Pillow >= 10.1：可缩放默认字体
    except TypeError:  # 老版本仅有固定小字号
        return ImageFont.load_default()


def generate_captcha() -> tuple[str, str, str]:
    """生成图形验证码 / Generate a captcha: (captcha_id, answer, image_base64).

    Returns:
        captcha_id: 唯一标识符
        answer: 验证码答案（大写）
        image_base64: data URI 格式的 PNG 图片
    """
    captcha_id = nanoid_generate(size=16)
    # 验证码答案必须用 CSPRNG（不可预测），避免被预测/暴力绕过。
    # Captcha answer must use a CSPRNG so it cannot be predicted.
    # (The visual noise/jitter below stays on `random` — not security-relevant.)
    answer = "".join(secrets.choice(_CHARS) for _ in range(_CAPTCHA_LENGTH))

    image = Image.new("RGB", (_IMG_WIDTH, _IMG_HEIGHT), color=(255, 255, 255))
    draw = ImageDraw.Draw(image)

    # 底噪：先铺一层背景噪点，字符压在其上 / lay a base layer of noise under the glyphs
    for _ in range(random.randint(120, 180)):
        x, y = random.randint(0, _IMG_WIDTH - 1), random.randint(0, _IMG_HEIGHT - 1)
        color = (random.randint(150, 220), random.randint(150, 220), random.randint(150, 220))
        draw.point((x, y), fill=color)

    # 逐字符绘制：每字独立成层、随机旋转后贴回。
    # 旋转是最有效又几乎不影响人眼识别的抗 OCR 手段——字符不再水平等高，整段切分识别失效。
    # Render each glyph on its own layer, rotate it, then paste back. Per-glyph rotation is the
    # single most effective anti-OCR measure that still stays fully human-readable.
    char_gap = (_IMG_WIDTH - 24) // _CAPTCHA_LENGTH
    x_offset = 14
    for ch in answer:
        # 字号轻微抖动，破坏等宽等高规律 / jitter size to break uniform glyph metrics
        glyph_font = _load_captcha_font(_FONT_SIZE + random.randint(-4, 6))
        color = (random.randint(0, 110), random.randint(0, 110), random.randint(0, 110))

        tile = Image.new("RGBA", (_FONT_SIZE + 28, _IMG_HEIGHT), (255, 255, 255, 0))
        ImageDraw.Draw(tile).text((6, 4), ch, fill=color, font=glyph_font)
        tile = tile.rotate(random.randint(-30, 30), resample=Image.BICUBIC, expand=False)

        y_offset = random.randint(-2, 10)
        image.paste(tile, (x_offset, y_offset), tile)
        x_offset += char_gap

    # 干扰线：更多、粗细不一、贯穿字符 / more interference lines, varied width, crossing glyphs
    for _ in range(random.randint(8, 11)):
        x1, y1 = random.randint(0, _IMG_WIDTH), random.randint(0, _IMG_HEIGHT)
        x2, y2 = random.randint(0, _IMG_WIDTH), random.randint(0, _IMG_HEIGHT)
        color = (random.randint(80, 190), random.randint(80, 190), random.randint(80, 190))
        draw.line([(x1, y1), (x2, y2)], fill=color, width=random.randint(1, 3))

    # 干扰圆弧：破坏"直线滤波 + 切字"类去噪 / arcs to defeat straight-line denoising
    for _ in range(random.randint(2, 4)):
        ax1 = random.randint(-30, 40)
        ay1 = random.randint(-20, 30)
        ax2 = ax1 + random.randint(_IMG_WIDTH // 2, _IMG_WIDTH)
        ay2 = ay1 + random.randint(_IMG_HEIGHT // 2, _IMG_HEIGHT)
        start, end = random.randint(0, 150), random.randint(200, 360)
        color = (random.randint(80, 190), random.randint(80, 190), random.randint(80, 190))
        draw.arc([(ax1, ay1), (ax2, ay2)], start, end, fill=color, width=random.randint(1, 2))

    # 前景噪点：覆于字符之上，进一步打散轮廓 / dense foreground noise over the glyphs
    for _ in range(random.randint(160, 220)):
        x, y = random.randint(0, _IMG_WIDTH - 1), random.randint(0, _IMG_HEIGHT - 1)
        color = (random.randint(60, 200), random.randint(60, 200), random.randint(60, 200))
        draw.point((x, y), fill=color)

    buf = io.BytesIO()
    image.save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
    image_base64 = f"data:image/png;base64,{b64}"

    return captcha_id, answer, image_base64
