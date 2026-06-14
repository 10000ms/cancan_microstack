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

    font = _load_captcha_font(_FONT_SIZE)

    # 绘制字符（更大字号 + 均匀分布 + 随机偏移和颜色）
    # Draw the characters with a larger font, even spacing, and slight jitter.
    char_gap = (_IMG_WIDTH - 24) // _CAPTCHA_LENGTH
    x_offset = 14
    for ch in answer:
        color = (random.randint(0, 120), random.randint(0, 120), random.randint(0, 120))
        y_offset = random.randint(2, 14)
        draw.text((x_offset, y_offset), ch, fill=color, font=font)
        x_offset += char_gap

    # 绘制干扰线
    for _ in range(5):
        x1, y1 = random.randint(0, _IMG_WIDTH), random.randint(0, _IMG_HEIGHT)
        x2, y2 = random.randint(0, _IMG_WIDTH), random.randint(0, _IMG_HEIGHT)
        color = (random.randint(100, 200), random.randint(100, 200), random.randint(100, 200))
        draw.line([(x1, y1), (x2, y2)], fill=color, width=1)

    # 绘制噪点
    for _ in range(100):
        x, y = random.randint(0, _IMG_WIDTH - 1), random.randint(0, _IMG_HEIGHT - 1)
        color = (random.randint(100, 200), random.randint(100, 200), random.randint(100, 200))
        draw.point((x, y), fill=color)

    buf = io.BytesIO()
    image.save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
    image_base64 = f"data:image/png;base64,{b64}"

    return captcha_id, answer, image_base64
