import os, shutil, zipfile

z = zipfile.ZipFile("data/猫子语料.zip")
for info in z.infolist():
    raw = info.filename
    try:
        fixed = raw.encode("cp437").decode("utf-8")  # macOS zip stores UTF-8 w/o the flag
    except Exception:
        fixed = raw
    target = os.path.join("data", "raw", fixed)
    if raw.endswith("/"):
        os.makedirs(target, exist_ok=True)
        continue
    os.makedirs(os.path.dirname(target), exist_ok=True)
    with z.open(info) as s, open(target, "wb") as d:
        shutil.copyfileobj(s, d)

n = 0
for r, _, fs in os.walk("data/猫子语料"):
    n += sum(f.endswith(".mp3") for f in fs)
print("mp3 count under data/猫子语料:", n)
