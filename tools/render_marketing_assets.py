from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1] / "docs" / "assets"
MONO = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"
BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf"


def font(size: int, bold: bool = False):
    return ImageFont.truetype(BOLD if bold else MONO, size)


def screen(active="left", dialog=False):
    im = Image.new("RGB", (1280, 720), "#101214")
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((16, 16, 1264, 62), 8, fill="#24272a")
    d.text((640, 28), "mDIR — Dual Pane File Manager", font=font(22, True), fill="#e7e7e7", anchor="ma")
    panes = [(16, 72, 628, 642), (652, 72, 1264, 642)]
    for i, box in enumerate(panes):
        on = (i == 0 and active == "left") or (i == 1 and active == "right")
        d.rectangle(box, fill="#191b1d", outline="#7aa2b8" if on else "#56616a", width=2)
        d.rectangle((box[0]+1, 73, box[2]-1, 103), fill="#0d7046" if on else "#15442f")
        d.rectangle((box[0]+1, 104, box[2]-1, 134), fill="#393d40")
    d.text((28, 81), "C:\\Projects\\", font=font(17, True), fill="white")
    d.text((664, 81), "D:\\Archive\\", font=font(17, True), fill="white")
    heads = [(28, "▲ Name"), (350, "Ext"), (455, "Size"), (532, "Modified"),
             (664, "Name"), (986, "Ext"), (1091, "Size"), (1168, "Modified")]
    for x, value in heads:
        d.text((x, 109), value, font=font(17, True), fill="#e8e8e8")
    rows = [
        ("docs", "", "<DIR>", "2026-09-02", "2026", "", "<DIR>", "2026-09-02"),
        ("photos", "", "<DIR>", "2026-09-01", "backup", "", "<DIR>", "2026-09-01"),
        ("release-notes", "md", "12,804", "2026-09-02", "manual", "pdf", "3,240,882", "2026-08-31"),
        ("project-plan", "xlsx", "284,911", "2026-09-01", "screenshots", "zip", "24,891,040", "2026-08-30"),
        ("welcome", "pdf", "1,842,116", "2026-08-30", "readme", "md", "8,192", "2026-08-29"),
    ]
    selected = 0 if active == "left" else 2
    x0 = 18 if active == "left" else 654
    d.rectangle((x0, 135 + selected*29, x0+608, 160 + selected*29), fill="#197a4f")
    for index, row in enumerate(rows):
        y = 138 + index*29
        for x, val, anchor in [(28,row[0],"la"),(350,row[1],"la"),(500,row[2],"ra"),(532,row[3],"la"),
                               (664,row[4],"la"),(986,row[5],"la"),(1136,row[6],"ra"),(1168,row[7],"la")]:
            d.text((x, y), val, font=font(17, index == selected), fill="#f5f5f5", anchor=anchor)
    for x1, x2 in [(28,616),(664,1252)]:
        d.line((x1,584,x2,584), fill="#d8c766", width=2)
    d.text((28, 595), "Files: 3 / 5   Folders: 0 / 2   Capacity: 2.0 MB", font=font(16), fill="#ddd")
    d.text((664, 595), "Files: 2 / 5   Folders: 0 / 2   Capacity: 27 MB", font=font(16), fill="#ddd")
    d.rectangle((16,654,1264,704), fill="#202326")
    d.text((30,670), "Space Mark   F2 Rename   F5 Copy   F6 Move   F7 MkDir   F8 Delete   F12 AI/File", font=font(18,True), fill="#e7c85c")
    if dialog:
        veil = Image.new("RGBA", im.size, (0,0,0,150)); im = Image.alpha_composite(im.convert("RGBA"), veil); d = ImageDraw.Draw(im)
        d.rounded_rectangle((360,235,920,480),12,fill="#2b2d2f",outline="#7aa2b8",width=2)
        d.text((395,270),"Copy selected items?",font=font(25,True),fill="white")
        d.text((395,325),"Files: 3    Total: 2.0 MB",font=font(18),fill="#c9ced2")
        d.text((395,360),"Destination: D:\\Archive\\",font=font(18),fill="#c9ced2")
        d.rounded_rectangle((585,402,735,452),6,fill="#7fa2b8")
        d.text((660,427),"Copy",font=font(20,True),fill="#101214",anchor="mm")
        im = im.convert("RGB")
    return im


ROOT.mkdir(parents=True, exist_ok=True)
frames = [screen("left"), screen("right"), screen("right", True)]
frames[0].save(ROOT / "mdir-demo.png")
frames[0].save(ROOT / "mdir-demo.gif", save_all=True, append_images=frames[1:], duration=[1100,900,1400], loop=0, optimize=True)

social = Image.new("RGB", (1280,640), "#0b1110")
d = ImageDraw.Draw(social)
d.rounded_rectangle((55,58,145,148),18,fill="#14b86e")
d.text((100,103),"m",font=font(44,True),fill="white",anchor="mm")
d.text((55,185),"mDIR",font=font(64,True),fill="white")
d.text((55,275),"Fast dual-pane",font=font(30,True),fill="#d9e3df")
d.text((55,316),"file management",font=font(30,True),fill="#d9e3df")
d.text((55,385),"Windows · Ubuntu",font=font(23),fill="#93a39c")
d.text((55,428),"Free and open source",font=font(23),fill="#93a39c")
shot = frames[0].resize((640,360))
social.paste(shot,(585,158))
d.rounded_rectangle((565,138,1245,538),14,outline="#3c6f5a",width=2)
social.save(ROOT / "social-preview.png", optimize=True)
