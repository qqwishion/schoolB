"""Rebuild original, schematic artwork. Generated PNG files ship with the project."""
import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from PIL import Image, ImageDraw, ImageFont
from museum.demo_data import TOPICS

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'demo_assets'
OUT.mkdir(exist_ok=True)

def font(size, serif=False):
    candidates = ([r'C:\Windows\Fonts\georgia.ttf', '/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf'] if serif else [r'C:\Windows\Fonts\segoeui.ttf', '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'])
    for path in candidates:
        if Path(path).exists(): return ImageFont.truetype(path, size)
    return ImageFont.load_default(size=size)

def make(topic, kind, title, period):
    palette = [('#e2e6d5', '#65764d', '#f6f1db'), ('#e9ddce', '#8c7255', '#faf0df'), ('#dbe5e2', '#547a72', '#eff3e8')]
    bg, ink, cream = palette[topic['era']]
    im = Image.new('RGB', (1000, 750), bg)
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((170, 80, 830, 680), radius=290, outline=ink, width=2)
    d.rounded_rectangle((190, 100, 810, 660), radius=275, outline=ink, width=1)
    d.ellipse((310, 125, 690, 505), fill=cream)
    d.text((50, 35), 'КАРМАННЫЙ МУЗЕЙ / УЧЕБНАЯ СХЕМА', font=font(19), fill=ink)
    d.text((950, 690), period, anchor='ra', font=font(22), fill=ink)
    d.line((50, 662, 950, 662), fill=ink, width=1)
    d.text((50, 690), {'event':'СОБЫТИЕ', 'person':'ЧЕЛОВЕК', 'object':'ПРЕДМЕТ', 'fact':'ДЕТАЛЬ ЭПОХИ'}[kind], font=font(19), fill=ink)
    if kind == 'person':
        # A typographic commemorative plaque, deliberately not a synthetic portrait.
        initials = ''.join(w[0] for w in title.split(':')[0].split()[:2])
        if title.startswith('Земский'): initials = '+'
        d.ellipse((347, 200, 653, 506), outline=ink, width=3)
        d.ellipse((357, 210, 643, 496), outline=ink, width=1)
        d.text((500, 345), initials, anchor='mm', font=font(112, True), fill=ink)
        d.rectangle((306, 515, 694, 534), fill=ink)
        d.text((500, 583), 'ЛЮДИ И ИДЕИ', anchor='mm', font=font(22), fill=ink)
    elif topic['slug'] == 'baltic' and kind == 'object':
        d.line((500, 170, 500, 495), fill=ink, width=6)
        d.polygon([(480, 205), (480, 370), (300, 370)], fill=cream, outline=ink, width=3)
        d.polygon([(520, 225), (520, 400), (700, 400)], fill=cream, outline=ink, width=3)
        d.polygon([(270, 470), (730, 470), (650, 550), (350, 550)], fill=ink)
        for y in [575, 598]:
            for x in range(250, 750, 100): d.arc((x, y-15, x+100, y+15), 0, 180, fill=ink, width=2)
    elif topic['slug'] in ('railway','transsib') and kind == 'object':
        if topic['slug'] == 'railway':
            d.rounded_rectangle((320, 330, 700, 480), radius=35, fill=ink)
            d.rectangle((300, 255, 430, 480), fill=ink)
            d.rectangle((320, 275, 405, 345), fill=cream)
            d.rectangle((610, 255, 655, 360), fill=ink)
            d.ellipse((590, 160, 650, 210), outline=ink, width=3)
            for x in [365, 500, 635]:
                d.ellipse((x-45, 450, x+45, 540), fill=cream, outline=ink, width=9)
            d.line((365, 495, 635, 495), fill=ink, width=9)
        for y in range(550, 625, 18): d.line((235, y, 765, y), fill=ink, width=3)
        if topic['slug'] == 'transsib':
            for y in range(250, 580, 45):
                d.polygon([(390-(y-250)//3,y), (610+(y-250)//3,y), (620+(y-250)//3,y+17),(380-(y-250)//3,y+17)], fill=ink)
            d.line((445, 200, 300, 610), fill=cream, width=13)
            d.line((555, 200, 700, 610), fill=cream, width=13)
    elif topic['slug'] == 'zemstvo' and kind == 'object':
        d.rounded_rectangle((300, 335, 700, 555), radius=35, fill=ink)
        d.rounded_rectangle((420, 270, 580, 360), radius=25, outline=ink, width=12)
        d.rectangle((470, 390, 530, 510), fill=cream)
        d.rectangle((440, 420, 560, 480), fill=cream)
    elif topic['slug'] == 'war-1812' and kind == 'object':
        d.polygon([(260,280),(420,235),(580,280),(740,235),(740,540),(580,585),(420,540),(260,585)], fill=cream, outline=ink, width=3)
        d.line([(300,480),(430,370),(520,430),(670,320)], fill=ink, width=4)
        for x,y in [(300,480),(430,370),(520,430),(670,320)]: d.ellipse((x-9,y-9,x+9,y+9),fill=ink)
        d.text((300,505),'Бородино',font=font(16),fill=ink)
        d.text((580,290),'Москва',font=font(16),fill=ink)
    elif kind == 'object':
        d.polygon([(285,270),(490,295),(490,565),(285,540)],fill=cream,outline=ink,width=3)
        d.polygon([(510,295),(715,270),(715,540),(510,565)],fill=cream,outline=ink,width=3)
        for y in range(330,510,28):
            d.line((315,y,460,y+16),fill=ink,width=2)
            d.line((540,y+16,685,y),fill=ink,width=2)
        d.line((500,285,500,575),fill=ink,width=3)
    elif kind == 'event':
        d.line((230,455,770,455),fill=ink,width=3)
        for x in [260,500,740]:
            d.ellipse((x-10,445,x+10,465),fill=ink)
            d.line((x,470,x,525),fill=ink,width=1)
        year = period.split(' ')[0]
        if len(year)>8: year=str([1721,1755,1767,1812,1825,1837,1861,1864,1891][TOPICS.index(topic)])
        d.text((500,340),year,anchor='mm',font=font(100,True),fill=ink)
        d.text((500,575),'ТОЧКА НА ЛИНИИ ВРЕМЕНИ',anchor='mm',font=font(20),fill=ink)
    else:
        d.text((500,345),'?',anchor='mm',font=font(230,True),fill=ink)
        d.line((330,510,670,510),fill=ink,width=2)
        d.text((500,565),'РАССМОТРИ ПОДРОБНЕЕ',anchor='mm',font=font(21),fill=ink)
    im.save(OUT / f'{topic["slug"]}-{kind}.png', optimize=True)

for topic in TOPICS:
    for kind, card in zip(['event','person','object','fact'],topic['cards']): make(topic,kind,card[0],card[1])
print(f'Created {len(TOPICS)*4} original PNG illustrations in {OUT}')
