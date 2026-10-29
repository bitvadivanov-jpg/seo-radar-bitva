from PIL import Image, ImageDraw, ImageFont
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
N=1024
im=Image.new('RGB',(N,N)); pix=im.load()
for y in range(N):
    for x in range(N):
        mix=(x+y)/(2*(N-1))
        pix[x,y]=(int(15+8*mix),int(24+11*mix),int(37+14*mix))
d=ImageDraw.Draw(im)
d.rounded_rectangle((20,20,1004,1004),radius=245,outline=(68,82,101),width=19)
d.rounded_rectangle((95,100,929,925),radius=180,fill=(25,38,54))
# Radar ring and arc
d.ellipse((223,204,805,786),outline=(79,101,116),width=14)
d.arc((223,204,805,786),start=195,end=346,fill=(255,147,76),width=42)
d.arc((304,284,726,706),start=195,end=315,fill=(254,186,117),width=26)
d.line((513,505,783,323),fill=(255,172,101),width=28)
d.ellipse((475,464,550,539),fill=(255,194,133))
# Couch silhouette foreground: 2 seat panels + armrests
outer=(186,548,838,758)
d.rounded_rectangle(outer,radius=75,fill=(254,144,71))
d.rounded_rectangle((247,533,492,678),radius=47,fill=(255,174,102))
d.rounded_rectangle((528,533,773,678),radius=47,fill=(255,174,102))
d.rounded_rectangle((192,650,832,789),radius=60,fill=(255,142,63))
d.line((511,603,511,670),fill=(227,102,46),width=15)
for x in [250,724]:d.rounded_rectangle((x,760,x+49,824),radius=13,fill=(254,169,91))
for n in (192,512):
    im.resize((n,n),Image.Resampling.LANCZOS).save(ROOT/f'web/icons/icon-{n}.png',optimize=True)
