"""자막·타이틀·배지 그림 만들기 (Pretendard, 흰 글자 + 은은한 그림자)"""
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from .paths import FONTS, run

W, H = 1920, 1080


def shadow_text(txt, font, fill=(255, 255, 255), blur=7, alpha=210, pad=34, stroke=2):
    d0 = ImageDraw.Draw(Image.new('RGBA', (1, 1)))
    b = d0.textbbox((0, 0), txt, font=font)
    im = Image.new('RGBA', (b[2] - b[0] + pad * 2, b[3] - b[1] + pad * 2), (0, 0, 0, 0))
    ImageDraw.Draw(im).text((pad - b[0] + 2, pad - b[1] + 3), txt, font=font, fill=(0, 0, 0, alpha))
    im = im.filter(ImageFilter.GaussianBlur(blur))
    ImageDraw.Draw(im).text((pad - b[0], pad - b[1]), txt, font=font, fill=fill, stroke_width=stroke, stroke_fill=(0, 0, 0, 140))
    return im


def fnt(weight, size):
    return ImageFont.truetype(str(FONTS / f'Pretendard-{weight}.otf'), size)


def overlay(path, cap=None, title=None, badge=None, endcard=None, handle=''):
    ov = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    if cap:
        t = shadow_text(cap, fnt('Bold', 58)); ov.alpha_composite(t, ((W - t.width) // 2, 880))
    if title:
        t = shadow_text(title[0], fnt('ExtraBold', 110), blur=10); ov.alpha_composite(t, ((W - t.width) // 2, 380))
        s = shadow_text(title[1], fnt('SemiBold', 48)); ov.alpha_composite(s, ((W - s.width) // 2, 540))
    if badge:
        t = shadow_text(badge, fnt('SemiBold', 40)); ov.alpha_composite(t, (70, 60))
    if endcard:
        a = shadow_text(endcard[0], fnt('SemiBold', 44)); ov.alpha_composite(a, ((W - a.width) // 2, 420))
        b = shadow_text(endcard[1], fnt('ExtraBold', 96)); ov.alpha_composite(b, ((W - b.width) // 2, 490))
        if handle:
            c = shadow_text(handle, fnt('SemiBold', 36)); ov.alpha_composite(c, ((W - c.width) // 2, 650))
    ov.save(path)


def card(path, small, big):
    im = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    a = shadow_text(small, fnt('SemiBold', 44)); im.alpha_composite(a, ((W - a.width) // 2, 430))
    b = shadow_text(big, fnt('ExtraBold', 96)); im.alpha_composite(b, ((W - b.width) // 2, 500))
    im.save(path)


def split_labels(path, labels, cap):
    ov = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    for txt, x in zip(labels, (330, 1028)):
        t = shadow_text(txt, fnt('SemiBold', 40)); ov.alpha_composite(t, (x + (562 - t.width) // 2, 996))
    if cap:
        t = shadow_text(cap, fnt('Bold', 58)); ov.alpha_composite(t, ((W - t.width) // 2, 860))
    ov.save(path)


def is_portrait(src):
    r = run(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries', 'stream_side_data=rotation', '-of', 'csv=p=0', src],
            capture_output=True, text=True).stdout.strip()
    return r in ('-90', '90', '270', '-270')


def base(src):
    """세로 영상은 흐린 배경 위 가운데, 가로 영상은 화면에 맞게 자름"""
    if is_portrait(src):
        return (f'[0:v]split[a][b];[a]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},'
                f'boxblur=40:2,eq=brightness=-0.15[bg];[b]scale=-2:{H}[fg];[bg][fg]overlay=(W-w)/2:0,setsar=1[base]')
    return f'[0:v]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},setsar=1[base]'


def ts(t):
    ms = int(round(t * 1000)); h, ms = divmod(ms, 3600000); m, ms = divmod(ms, 60000); s, ms = divmod(ms, 1000)
    return f'{h:02d}:{m:02d}:{s:02d},{ms:03d}'
