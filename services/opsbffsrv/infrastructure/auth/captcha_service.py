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
_IMG_WIDTH = 200
_IMG_HEIGHT = 60


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

    # 尝试使用系统字体，不可用时使用默认字体
    try:
        font = ImageFont.truetype("Arial", 32)
    except (OSError, IOError):
        font = ImageFont.load_default()

    # 绘制字符（带随机偏移和颜色）
    x_offset = 15
    for ch in answer:
        color = (random.randint(0, 150), random.randint(0, 150), random.randint(0, 150))
        y_offset = random.randint(5, 15)
        draw.text((x_offset, y_offset), ch, fill=color, font=font)
        x_offset += 28

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
