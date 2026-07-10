"""End-to-end tests for metavault_core (run headless)."""
import os, sys, io, zipfile, subprocess, tempfile, shutil, textwrap
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import strix_metavault_core as mv

WORK = tempfile.mkdtemp(prefix="mvtest_")
OUT = os.path.join(WORK, "out"); os.makedirs(OUT, exist_ok=True)
EXIFTOOL = mv.find_exiftool()
SEVENZIP = mv.find_7z()
print("tools:", {"7z": SEVENZIP, "exiftool": EXIFTOOL, "pikepdf": mv.HAVE_PIKEPDF})

fails = []
def check(name, cond, extra=""):
    print(("PASS " if cond else "FAIL ") + name + ("  " + extra if extra else ""))
    if not cond: fails.append(name)

# --------------------------------------------------------------------------- #
# Build sample files
# --------------------------------------------------------------------------- #
from PIL import Image
from PIL.PngImagePlugin import PngInfo

# JPEG with EXIF Artist + GPS injected via exiftool
jpg = os.path.join(WORK, "photo.jpg")
Image.new("RGB", (32, 32), (120, 40, 200)).save(jpg, "JPEG")
subprocess.run([EXIFTOOL, "-overwrite_original", "-q", "-q",
                "-Artist=SECRET_PERSON", "-Copyright=SECRET_ORG",
                "-GPSLatitude=41.0", "-GPSLatitudeRef=N",
                "-GPSLongitude=29.0", "-GPSLongitudeRef=E",
                "-Comment=hello", jpg], check=True)

def jpg_meta(p):
    r = subprocess.run([EXIFTOOL, "-s", "-Artist", "-Copyright",
                        "-GPSLatitude", "-Comment", p],
                       stdout=subprocess.PIPE)
    return r.stdout.decode()

before = jpg_meta(jpg)
check("jpeg seeded with EXIF/GPS", "SECRET_PERSON" in before and "41" in before)

# PNG with a tEXt chunk
png = os.path.join(WORK, "image.png")
meta = PngInfo(); meta.add_text("Author", "SECRET_PERSON"); meta.add_text("Note", "hidden")
Image.new("RGB", (20, 20), (10, 200, 10)).save(png, "PNG", pnginfo=meta)
with open(png, "rb") as f: raw = f.read()
check("png seeded with tEXt", b"SECRET_PERSON" in raw)

# PDF with docinfo + XMP
pdf = os.path.join(WORK, "doc.pdf")
import pikepdf
p = pikepdf.new()
p.add_blank_page(page_size=(200, 200))
with p.open_metadata() as m:
    m["dc:creator"] = ["SECRET_PERSON"]
    m["dc:title"] = "SECRET_TITLE"
p.docinfo["/Author"] = "SECRET_PERSON"
p.docinfo["/Title"] = "SECRET_TITLE"
p.save(pdf)
with open(pdf, "rb") as f: praw = f.read()
check("pdf seeded with author/title", b"SECRET_PERSON" in praw)

# Hand-crafted DOCX with author names in core, app, custom, comments, tracked changes
docx = os.path.join(WORK, "letter.docx")
def build_docx(path):
    parts = {
        "[Content_Types].xml":
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Default Extension="jpeg" ContentType="image/jpeg"/>'
            '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
            '<Override PartName="/word/comments.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.comments+xml"/>'
            '<Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>'
            '<Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>'
            '<Override PartName="/docProps/custom.xml" ContentType="application/vnd.openxmlformats-officedocument.custom-properties+xml"/>'
            '</Types>',
        "_rels/.rels":
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>'
            '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>'
            '<Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/>'
            '<Relationship Id="rId4" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/custom-properties" Target="docProps/custom.xml"/>'
            '<Relationship Id="rId5" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/thumbnail" Target="docProps/thumbnail.jpeg"/>'
            '</Relationships>',
        "docProps/core.xml":
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" '
            'xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/" '
            'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
            '<dc:creator>SECRET_PERSON</dc:creator><cp:lastModifiedBy>SECRET_PERSON2</cp:lastModifiedBy>'
            '<dcterms:created xsi:type="dcterms:W3CDTF">2021-01-01T00:00:00Z</dcterms:created>'
            '<dc:title>SECRET_TITLE</dc:title></cp:coreProperties>',
        "docProps/app.xml":
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties">'
            '<Company>SECRET_ORG</Company><Manager>SECRET_BOSS</Manager><Application>Microsoft Word</Application></Properties>',
        "docProps/custom.xml":
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/custom-properties" '
            'xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes">'
            '<property fmtid="{D5CDD505-2E9C-101B-9397-08002B2CF9AE}" pid="2" name="SecretField">'
            '<vt:lpwstr>SECRET_CUSTOM</vt:lpwstr></property></Properties>',
        "docProps/thumbnail.jpeg": "BINARYTHUMBNAILDATA_SECRET",
        "word/comments.xml":
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<w:comments xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
            '<w:comment w:id="1" w:author="SECRET_PERSON" w:initials="SP" w:date="2021-01-01T00:00:00Z">'
            '<w:p><w:r><w:t>a comment</w:t></w:r></w:p></w:comment></w:comments>',
        "word/document.xml":
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
            '<w:body><w:p>'
            '<w:ins w:id="2" w:author="SECRET_PERSON" w:date="2021-01-01T00:00:00Z">'
            '<w:r><w:t>inserted</w:t></w:r></w:ins>'
            '<w:r><w:t>Body text stays.</w:t></w:r>'
            '</w:p></w:body></w:document>',
    }
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        for n, data in parts.items():
            z.writestr(n, data)
build_docx(docx)
with zipfile.ZipFile(docx) as z:
    draw = b"".join(z.read(n) for n in z.namelist())   # decompressed content
check("docx seeded with author names", b"SECRET_PERSON" in draw and b"SECRET_ORG" in draw)

opts = mv.CleanOptions(preserve_color=True, deep_office=True)

# --------------------------------------------------------------------------- #
# 1) JPEG via lossless fallback (force exiftool=None)
# --------------------------------------------------------------------------- #
jpg2 = os.path.join(WORK, "photo_fallback.jpg"); shutil.copy2(jpg, jpg2)
mv.strip_metadata(jpg2, opts, exiftool=None)
after = jpg_meta(jpg2)
img_ok = Image.open(jpg2); img_ok.load()
check("jpeg fallback removed EXIF/GPS/Comment",
      "SECRET_PERSON" not in after and "SECRET_ORG" not in after and
      "41" not in after and "hello" not in after)
check("jpeg still decodes after fallback strip", img_ok.size == (32, 32))

# 2) JPEG via exiftool path
jpg3 = os.path.join(WORK, "photo_exif.jpg"); shutil.copy2(jpg, jpg3)
r = mv.strip_metadata(jpg3, opts, exiftool=EXIFTOOL)
check("jpeg exiftool removed EXIF/GPS", "SECRET_PERSON" not in jpg_meta(jpg3), r.method)

# 3) PNG lossless fallback
png2 = os.path.join(WORK, "image_fallback.png"); shutil.copy2(png, png2)
mv.strip_metadata(png2, opts, exiftool=None)
with open(png2, "rb") as f: praw2 = f.read()
pimg = Image.open(png2); pimg.load()
check("png fallback removed tEXt", b"SECRET_PERSON" not in praw2 and b"hidden" not in praw2)
check("png still decodes after strip", pimg.size == (20, 20))

# 4) PDF
pdf2 = os.path.join(WORK, "doc2.pdf"); shutil.copy2(pdf, pdf2)
mv.strip_metadata(pdf2, opts, exiftool=EXIFTOOL)
with open(pdf2, "rb") as f: praw3 = f.read()
reopened = pikepdf.open(pdf2)
check("pdf removed author/title", b"SECRET_PERSON" not in praw3 and b"SECRET_TITLE" not in praw3)
check("pdf still opens & has page", len(reopened.pages) == 1)

# 5) DOCX deep clean
docx2 = os.path.join(WORK, "letter2.docx"); shutil.copy2(docx, docx2)
res = mv.strip_metadata(docx2, opts, exiftool=EXIFTOOL)
with zipfile.ZipFile(docx2) as z:
    names = z.namelist()
    blob = b"".join(z.read(n) for n in names)
    rels_after = z.read("_rels/.rels")
    dates = {i.date_time for i in z.infolist()}
check("docx removed custom.xml + thumbnail",
      "docProps/custom.xml" not in names and
      all(not n.lower().startswith("docprops/thumbnail") for n in names))
check("docx rels no longer reference removed parts",
      b"custom.xml" not in rels_after and b"thumbnail" not in rels_after)
check("docx author/company/custom scrubbed everywhere",
      b"SECRET_PERSON" not in blob and b"SECRET_ORG" not in blob and
      b"SECRET_BOSS" not in blob and b"SECRET_CUSTOM" not in blob and
      b"SECRET_TITLE" not in blob and b"SECRET_PERSON2" not in blob)
check("docx body text preserved", b"Body text stays." in blob)
check("docx zip timestamps zeroed", dates == {(1980, 1, 1, 0, 0, 0)})
# validity: reopen as zip and ensure [Content_Types].xml is first
with zipfile.ZipFile(docx2) as z:
    check("docx [Content_Types].xml is first entry",
          z.namelist()[0] == "[Content_Types].xml")

# --------------------------------------------------------------------------- #
# 5b) OOXML EMBEDDED-MEDIA metadata: a GPS/EXIF-tagged photo inside an Office
#     document must be scrubbed, and customXml data stores must be dropped.
# --------------------------------------------------------------------------- #
with open(jpg, "rb") as f:
    seeded_media = f.read()          # jpg was seeded above with Artist + GPS via exiftool
check("media seed jpg carries EXIF/GPS", b"SECRET_PERSON" in seeded_media)

docx_media = os.path.join(WORK, "with_photo.docx")
def build_docx_with_media(path, image_bytes):
    parts = {
        "[Content_Types].xml":
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Default Extension="jpg" ContentType="image/jpeg"/>'
            '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
            '</Types>',
        "_rels/.rels":
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>'
            '</Relationships>',
        "word/_rels/document.xml.rels":
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rIdImg" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="media/image1.jpg"/>'
            '<Relationship Id="rIdCx" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/customXml" Target="../customXml/item1.xml"/>'
            '</Relationships>',
        "word/document.xml":
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
            '<w:body><w:p><w:r><w:t>Has an embedded photo.</w:t></w:r></w:p></w:body></w:document>',
        "customXml/item1.xml":
            '<ds:datastoreItem xmlns:ds="http://schemas.openxmlformats.org/officeDocument/2006/customXml" '
            'ds:itemID="{SECRET_GUID_XYZ}"><ds:schemaRefs/></ds:datastoreItem>',
    }
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        for n, data in parts.items():
            z.writestr(n, data)
        z.writestr("word/media/image1.jpg", image_bytes)   # binary image with EXIF/GPS
build_docx_with_media(docx_media, seeded_media)

res_media = mv.strip_ooxml(docx_media, opts)
with zipfile.ZipFile(docx_media) as z:
    names_m = z.namelist()
    media_after = z.read("word/media/image1.jpg")
    blob_m = b"".join(z.read(n) for n in names_m)
    rels_m = z.read("word/_rels/document.xml.rels")
check("ooxml embedded-media EXIF stripped",
      b"SECRET_PERSON" not in media_after and b"SECRET_ORG" not in media_after,
      res_media.note)
# the image part is still a decodable JPEG (only metadata removed)
mimg = Image.open(io.BytesIO(media_after)); mimg.load()
check("ooxml embedded-media still decodes", mimg.size == (32, 32))
check("ooxml customXml/* dropped",
      not any(n.lower().startswith("customxml/") for n in names_m)
      and b"SECRET_GUID_XYZ" not in blob_m)
check("ooxml customXml relationship removed (no dangling ref)",
      b"customXml" not in rels_m and b"media/image1.jpg" in rels_m)
# independent confirmation via exiftool that GPS/Artist are truly gone
mtmp = os.path.join(WORK, "extracted_media.jpg")
with open(mtmp, "wb") as f: f.write(media_after)
media_meta = subprocess.run([EXIFTOOL, "-s", "-Artist", "-GPSLatitude", mtmp],
                            stdout=subprocess.PIPE).stdout.decode()
check("ooxml embedded-media GPS/Artist gone (exiftool)",
      "SECRET_PERSON" not in media_meta and "41" not in media_meta, media_meta.strip())

# --------------------------------------------------------------------------- #
# 6) Full pipeline: clean + encrypted archive with header encryption
# --------------------------------------------------------------------------- #
inputs = [jpg, png, pdf, docx]
arch = mv.ArchiveOptions(make_archive=True, encrypt_names=True, compression=5,
                         password_mode="random", password_length=20,
                         randomize_filename=True)
logs = []
rr = mv.run_pipeline(inputs, OUT, opts, arch, do_clean=True,
                     exiftool=EXIFTOOL, seven_zip=SEVENZIP,
                     secure_delete=True, log=logs.append)
check("pipeline ok", rr.ok, rr.error or "")
check("archive exists", rr.archive_path and os.path.isfile(rr.archive_path))
check("archive filename randomized (hex + .7z)",
      bool(rr.archive_path) and rr.archive_path.endswith(".7z")
      and all(c in "0123456789abcdef" for c in os.path.splitext(os.path.basename(rr.archive_path))[0]))
check("engine returned a generated password", bool(rr.password) and len(rr.password) == 20)
check("password never appears in logs", all(rr.password not in l for l in logs))

# Wrong password must fail (proves encryption is real)
wp = subprocess.run([SEVENZIP, "l", "-pWRONGPASS", rr.archive_path],
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE)
check("wrong password rejected", wp.returncode != 0)

# Wrong password must NOT reveal internal names (header encryption)
listing_wrong = (wp.stdout + wp.stderr).decode("utf-8", "replace")
check("file names hidden without password",
      "photo.jpg" not in listing_wrong and "letter.docx" not in listing_wrong)

# Correct password lists + extracts, and extracted content is clean
listing = subprocess.run([SEVENZIP, "l", "-p" + rr.password, rr.archive_path],
                         stdout=subprocess.PIPE).stdout.decode()
check("correct password lists names", "photo.jpg" in listing and "letter.docx" in listing)

exdir = os.path.join(WORK, "extracted")
ex = subprocess.run([SEVENZIP, "x", "-p" + rr.password, "-y", "-o" + exdir, rr.archive_path],
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE)
check("extraction succeeds", ex.returncode == 0)
# verify extracted docx is clean
exdocx = os.path.join(exdir, "letter.docx")
if os.path.isfile(exdocx):
    with zipfile.ZipFile(exdocx) as z:
        exblob = b"".join(z.read(n) for n in z.namelist())
    check("extracted docx is metadata-clean", b"SECRET_PERSON" not in exblob)
else:
    check("extracted docx present", False)

# --------------------------------------------------------------------------- #
# 7) No-archive path emits cleaned files
# --------------------------------------------------------------------------- #
arch2 = mv.ArchiveOptions(make_archive=False)
rr2 = mv.run_pipeline([jpg, docx], OUT, opts, arch2, do_clean=True,
                      exiftool=EXIFTOOL, seven_zip=SEVENZIP)
emitted = []
if rr2.output_dir_used and os.path.isdir(rr2.output_dir_used):
    for dp, _, fs in os.walk(rr2.output_dir_used):
        emitted += [os.path.join(dp, f) for f in fs]
check("no-archive emitted cleaned files", rr2.ok and len(emitted) == 2, rr2.error or "")

# 8) password generator sanity
pw = mv.gen_password(28, use_symbols=True)
check("password length honored", len(pw) == 28)
check("password has mixed classes",
      any(c.islower() for c in pw) and any(c.isupper() for c in pw)
      and any(c.isdigit() for c in pw) and any(c in mv._SAFE_SYMBOLS for c in pw))

# --------------------------------------------------------------------------- #
# SECURITY HARDENING TESTS
# --------------------------------------------------------------------------- #
print("\n--- hardening ---")

# H1) argument-injection: a filename starting with '-' must be archived as a
#     literal file, not interpreted by 7-Zip as an option (guarded by '--').
inj_dir = os.path.join(WORK, "injfolder"); os.makedirs(inj_dir, exist_ok=True)
Image.new("RGB", (8, 8), (1, 2, 3)).save(os.path.join(inj_dir, "-mx0 danger.jpg"), "JPEG")
rr_inj = mv.run_pipeline(
    [inj_dir], OUT, mv.CleanOptions(),
    mv.ArchiveOptions(make_archive=True, password_length=16),
    do_clean=True, exiftool=EXIFTOOL, seven_zip=SEVENZIP, secure_delete=True)
listing = ""
if rr_inj.ok and SEVENZIP:
    lr = subprocess.run([SEVENZIP, "l", "-p" + (rr_inj.password or "x"),
                         rr_inj.archive_path],
                        stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    listing = lr.stdout.decode("utf-8", "replace")
check("leading-dash filename archived safely (arg-injection guard)",
      rr_inj.ok and "-mx0 danger.jpg" in listing, rr_inj.error or "")

# H2) symlink safety: a symlink inside a selected folder must be skipped, never
#     followed (so it cannot smuggle an external file into the output).
secret = os.path.join(WORK, "OUTSIDE_SECRET.txt")
with open(secret, "w") as f: f.write("TOPSECRET-XYZ")
linkdir = os.path.join(WORK, "linkfolder"); os.makedirs(linkdir, exist_ok=True)
with open(os.path.join(linkdir, "normal.txt"), "w") as f: f.write("ok")
made_link = True
try:
    os.symlink(secret, os.path.join(linkdir, "link_to_secret.txt"))
except (OSError, NotImplementedError):
    made_link = False
rr_sym = mv.run_pipeline(
    [linkdir], OUT, mv.CleanOptions(), mv.ArchiveOptions(make_archive=False),
    do_clean=False, exiftool=None, seven_zip=None, secure_delete=True)
emitted_files = []
if rr_sym.output_dir_used and os.path.isdir(rr_sym.output_dir_used):
    for dp, _, fs in os.walk(rr_sym.output_dir_used):
        emitted_files += fs
if made_link:
    check("symlink inside folder skipped, not followed",
          rr_sym.ok and "link_to_secret.txt" not in emitted_files
          and "normal.txt" in emitted_files
          and any("symlink skipped" in w for w in rr_sym.warnings),
          str(rr_sym.warnings))
else:
    check("symlink inside folder skipped, not followed", True, "symlinks unsupported here")

# H3) zip-bomb guard: an OOXML member with an absurd compression ratio is
#     refused WITHOUT being decompressed into memory.
bomb = os.path.join(WORK, "bomb.docx")
with zipfile.ZipFile(bomb, "w", zipfile.ZIP_DEFLATED) as z:
    z.writestr("[Content_Types].xml", b"<x/>")
    z.writestr("word/huge.bin", b"\0" * (5 * 1024 * 1024))   # 5 MiB zeros -> tiny on disk
r_bomb = mv.strip_ooxml(bomb, mv.CleanOptions())
check("high-ratio OOXML member refused (zip-bomb guard)",
      (not r_bomb.stripped) and "suspicious" in r_bomb.note, r_bomb.note)

# H4) ExifTool's auto-loaded Perl config must be disabled via -config <empty>.
cfg = mv._exiftool_null_config()
a = mv._exiftool_args("exiftool", "/abs/path.jpg",
                      mv.CleanOptions(preserve_color=True), cfg)
check("exiftool disables user Perl config (-config empty file)",
      "-config" in a and a[a.index("-config") + 1] == cfg
      and os.path.isfile(cfg) and os.path.getsize(cfg) == 0)

# H5) password redaction never leaks the secret in surfaced text.
red = mv._redact("7z -pS3cr3t! failed: S3cr3t!", "S3cr3t!")
check("password redaction removes secret", "S3cr3t!" not in red and "****" in red)

# H6) generated passwords enforce an entropy floor even if a tiny length is asked.
check("generated password enforces entropy floor (>=12)", len(mv.gen_password(4)) >= 12)

# H7) member-name validator rejects traversal / absolute paths.
check("OOXML member-name validator rejects traversal/absolute",
      mv._safe_member_name("word/document.xml")
      and not mv._safe_member_name("../evil")
      and not mv._safe_member_name("/etc/passwd")
      and not mv._safe_member_name("C:\\evil"))

# H8) output_ext is validated so it cannot smuggle a path separator / '..' into
#     the output path (parallels the output_name basename sanitisation).
_oe = mv._safe_output_ext
check("output_ext validation blocks traversal",
      _oe(".7z") == ".7z" and _oe("") == ".7z"
      and all(("/" not in r and "\\" not in r and ".." not in r and r.startswith("."))
              for r in (_oe("/../evil.7z"), _oe("..\\x"), _oe(".7z/../.."))))

print("\n" + ("ALL TESTS PASSED" if not fails else f"{len(fails)} FAILURE(S): {fails}"))
shutil.rmtree(WORK, ignore_errors=True)
sys.exit(1 if fails else 0)
